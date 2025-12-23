"""
OptiMetrics Hardware Logger

Main automated logging script that collects hardware metrics at configurable
intervals and writes them to CSV files with rolling daily logs.

Features:
    - Per-second resolution logging
    - Rolling daily log files
    - Delta filtering to reduce file size
    - Automatic session classification
    - Auto-resume after reboot
    - Optional cloud upload
    - Minimal memory footprint

Usage:
    python hardware_logger.py [--config path/to/config.yaml]
"""

import os
import sys
import csv
import time
import signal
import argparse
import threading
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import OrderedDict
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    load_config,
    get_default_config,
    setup_logging,
    get_log_file_path,
    get_cached_hardware_id,
    get_system_info,
    SessionClassifier,
    save_session_state,
    load_session_state,
    SessionState,
)

# Import data management and cloud sync
try:
    from src.data_manager import DeviceDataManager
    from src.cloud_sync import CloudSyncManager, HAS_GDRIVE
except ImportError:
    HAS_GDRIVE = False
    DeviceDataManager = None
    CloudSyncManager = None

from src.adapters import (
    CPUAdapter,
    NvidiaGPUAdapter,
    MemoryAdapter,
    DiskAdapter,
    NetworkAdapter,
)
from src.adapters.base_adapter import MetricValue

# Module logger
logger = logging.getLogger("optimetrics.logger")


class MetricsBuffer:
    """
    Efficient buffer for metrics before writing to CSV.
    
    Implements delta filtering to reduce file size by only logging
    when metrics change significantly.
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        batch_size: int = 60
    ):
        self.config = config or get_default_config()
        logging_config = self.config.get("logging", {})
        
        self.batch_size = batch_size
        self.enable_delta = logging_config.get("enable_delta_filtering", True)
        self.delta_threshold = logging_config.get("delta_threshold_percent", 2.0)
        
        self._buffer: List[Dict[str, Any]] = []
        self._last_values: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def add(self, metrics: Dict[str, Any]) -> bool:
        """
        Add metrics to buffer, applying delta filtering.
        
        Returns:
            True if metrics were added (passed delta filter)
        """
        with self._lock:
            if self.enable_delta and self._last_values:
                # Check if any metric changed significantly
                significant_change = False
                for key, value in metrics.items():
                    if key in ["timestamp", "session_category"]:
                        continue
                    
                    if isinstance(value, (int, float)):
                        last_val = self._last_values.get(key)
                        if last_val is not None and last_val != 0:
                            change_pct = abs(value - last_val) / abs(last_val) * 100
                            if change_pct >= self.delta_threshold:
                                significant_change = True
                                break
                        elif last_val is None or (last_val == 0 and value != 0):
                            significant_change = True
                            break
                
                if not significant_change:
                    return False
            
            # Update last values
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    self._last_values[key] = value
            
            self._buffer.append(metrics)
            return True
    
    def get_batch(self) -> List[Dict[str, Any]]:
        """Get and clear the current buffer."""
        with self._lock:
            batch = self._buffer.copy()
            self._buffer.clear()
            return batch
    
    def is_full(self) -> bool:
        """Check if buffer has reached batch size."""
        return len(self._buffer) >= self.batch_size
    
    def size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)


class CSVWriter:
    """
    Efficient CSV writer with rolling file support.
    
    Features:
        - Automatic header management
        - Rolling daily files
        - File size limits
        - Old file compression
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_default_config()
        logging_config = self.config.get("logging", {})
        
        self.max_file_size_mb = logging_config.get("max_file_size_mb", 50)
        self.compress_old = logging_config.get("compress_old_logs", True)
        self.compress_after_days = logging_config.get("compress_after_days", 1)
        
        self._current_file: Optional[Path] = None
        self._current_date: Optional[str] = None
        self._headers: Optional[List[str]] = None
        self._file_handle = None
        self._csv_writer = None
        self._lock = threading.Lock()
        self._file_counter = 0
    
    def _get_file_path(self) -> Path:
        """Get current log file path, handling date changes and size limits."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check for date change
        if self._current_date != today:
            self._close_file()
            self._current_date = today
            self._file_counter = 0
        
        # Check file size
        if self._current_file and self._current_file.exists():
            size_mb = self._current_file.stat().st_size / (1024 * 1024)
            if size_mb >= self.max_file_size_mb:
                self._close_file()
                self._file_counter += 1
        
        # Generate file path
        base_path = get_log_file_path(self.config)
        if self._file_counter > 0:
            stem = base_path.stem
            suffix = base_path.suffix
            base_path = base_path.parent / f"{stem}_{self._file_counter}{suffix}"
        
        return base_path
    
    def _open_file(self, file_path: Path) -> None:
        """Open file for writing, creating headers if needed."""
        file_exists = file_path.exists() and file_path.stat().st_size > 0
        
        self._file_handle = open(file_path, "a", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(
            self._file_handle,
            fieldnames=self._headers,
            extrasaction="ignore"
        )
        
        if not file_exists and self._headers:
            self._csv_writer.writeheader()
        
        self._current_file = file_path
    
    def _close_file(self) -> None:
        """Close current file handle."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
            self._csv_writer = None
    
    def write_batch(self, records: List[Dict[str, Any]]) -> int:
        """
        Write a batch of records to CSV.
        
        Args:
            records: List of metric dictionaries
        
        Returns:
            Number of records written
        """
        if not records:
            return 0
        
        with self._lock:
            # Update headers if needed
            if self._headers is None:
                self._headers = list(records[0].keys())
            else:
                # Check for new columns
                for record in records:
                    for key in record.keys():
                        if key not in self._headers:
                            self._headers.append(key)
            
            # Get/open file
            file_path = self._get_file_path()
            if self._current_file != file_path or self._file_handle is None:
                self._close_file()
                self._open_file(file_path)
            
            # Write records
            for record in records:
                self._csv_writer.writerow(record)
            
            self._file_handle.flush()
            
            return len(records)
    
    def compress_old_files(self) -> int:
        """
        Compress log files older than threshold.
        
        Returns:
            Number of files compressed
        """
        if not self.compress_old:
            return 0
        
        compressed = 0
        log_dir = get_log_file_path(self.config).parent
        cutoff = datetime.now() - timedelta(days=self.compress_after_days)
        
        for csv_file in log_dir.glob("*.csv"):
            # Skip current file
            if csv_file == self._current_file:
                continue
            
            # Check file age
            mtime = datetime.fromtimestamp(csv_file.stat().st_mtime)
            if mtime < cutoff:
                gz_path = csv_file.with_suffix(".csv.gz")
                if not gz_path.exists():
                    try:
                        with open(csv_file, "rb") as f_in:
                            with gzip.open(gz_path, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        csv_file.unlink()
                        compressed += 1
                        logger.info(f"Compressed {csv_file.name}")
                    except Exception as e:
                        logger.error(f"Failed to compress {csv_file}: {e}")
        
        return compressed
    
    def close(self) -> None:
        """Close the writer and release resources."""
        with self._lock:
            self._close_file()


class HardwareLogger:
    """
    Main hardware metrics logger.
    
    Orchestrates metric collection from all adapters, session classification,
    buffering, and CSV writing with optional cloud upload.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the hardware logger.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = setup_logging(self.config)
        
        general_config = self.config.get("general", {})
        self.interval = general_config.get("logging_interval", 1)
        
        # Initialize components
        self._adapters: List[Any] = []
        self._buffer = MetricsBuffer(self.config)
        self._writer = CSVWriter(self.config)  # Legacy writer for backwards compat
        self._classifier: Optional[SessionClassifier] = None
        self._data_manager: Optional[DeviceDataManager] = None
        self._cloud_sync: Optional[CloudSyncManager] = None
        
        # State
        self._running = False
        self._paused = False
        self._metrics_count = 0
        self._session_start = datetime.now()
        self._hardware_id = get_cached_hardware_id()
        
        # Threads
        self._collect_thread: Optional[threading.Thread] = None
        self._write_thread: Optional[threading.Thread] = None
        self._upload_thread: Optional[threading.Thread] = None
        
        # Initialize adapters based on config
        self._init_adapters()
        
        # Session classifier disabled - unreliable without process information
        # if general_config.get("enable_session_classification", False):
        #     self._classifier = SessionClassifier(self.config)
        
        # Initialize new data manager (per-device, per-hardware structure)
        if DeviceDataManager:
            try:
                self._data_manager = DeviceDataManager(self._hardware_id)
                logger.info(f"Data manager initialized: {self._data_manager.device_dir}")
            except Exception as e:
                logger.warning(f"Failed to initialize data manager: {e}")
                self._data_manager = None
        
        # Initialize cloud sync (incremental uploads)
        cloud_config = self.config.get("cloud", {})
        if cloud_config.get("enabled", False) and HAS_GDRIVE and CloudSyncManager and self._data_manager:
            try:
                self._cloud_sync = CloudSyncManager(self._data_manager)
                if self._cloud_sync.authenticate():
                    logger.info("Cloud sync enabled - metrics will be uploaded automatically")
                else:
                    logger.warning("Cloud sync authentication failed - running in local-only mode")
                    self._cloud_sync = None
            except Exception as e:
                logger.warning(f"Failed to initialize cloud sync: {e}")
                self._cloud_sync = None
    
    def _init_adapters(self) -> None:
        """Initialize hardware adapters based on configuration."""
        general_config = self.config.get("general", {})
        
        # CPU Adapter
        if general_config.get("collect_cpu", True):
            adapter = CPUAdapter(self.config)
            if adapter.initialize():
                self._adapters.append(adapter)
                logger.info("CPU adapter initialized")
            else:
                logger.warning("Failed to initialize CPU adapter")
        
        # GPU Adapters (NVIDIA and Intel)
        if general_config.get("collect_gpu", True):
            # NVIDIA GPU
            nvidia_adapter = NvidiaGPUAdapter(self.config)
            if nvidia_adapter.initialize():
                self._adapters.append(nvidia_adapter)
                logger.info("NVIDIA GPU adapter initialized")
            else:
                logger.debug("No NVIDIA GPU detected or pynvml not available")
            
            # Intel GPU
            from src.adapters import IntelGPUAdapter
            intel_adapter = IntelGPUAdapter(self.config)
            if intel_adapter.initialize():
                self._adapters.append(intel_adapter)
                logger.info("Intel GPU adapter initialized")
        
        # Memory Adapter
        if general_config.get("collect_ram", True):
            adapter = MemoryAdapter(self.config)
            if adapter.initialize():
                self._adapters.append(adapter)
                logger.info("Memory adapter initialized")
        
        # Disk Adapter
        if general_config.get("collect_disk", True):
            adapter = DiskAdapter(self.config)
            if adapter.initialize():
                self._adapters.append(adapter)
                logger.info("Disk adapter initialized")
        
        # Network Adapter
        if general_config.get("collect_network", True):
            adapter = NetworkAdapter(self.config)
            if adapter.initialize():
                self._adapters.append(adapter)
                logger.info("Network adapter initialized")
    
    def _collect_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all adapters."""
        metrics = OrderedDict()
        
        # Timestamp and hardware ID
        metrics["timestamp"] = datetime.now().isoformat()
        metrics["hardware_id"] = self._hardware_id
        
        # Collect from each adapter
        for adapter in self._adapters:
            if adapter.is_available():
                try:
                    adapter_metrics = adapter.collect_metrics()
                    for name, metric in adapter_metrics.items():
                        if isinstance(metric, MetricValue):
                            metrics[name] = metric.value
                        else:
                            metrics[name] = metric
                except Exception as e:
                    logger.debug(f"Error collecting from {adapter.adapter_name}: {e}")
                    adapter.record_error(str(e))
        
        return metrics
    
    def _collection_loop(self) -> None:
        """Main collection loop running in separate thread."""
        logger.info("Collection loop started")
        
        # Initial CPU percent call (first call returns 0)
        import psutil
        psutil.cpu_percent(interval=None, percpu=True)
        time.sleep(0.1)
        
        while self._running:
            if self._paused:
                time.sleep(0.5)
                continue
            
            start_time = time.time()
            
            try:
                metrics = self._collect_metrics()
                if self._buffer.add(metrics):
                    self._metrics_count += 1
                
                # Check if buffer is full
                if self._buffer.is_full():
                    self._flush_buffer()
                    
            except Exception as e:
                logger.error(f"Collection error: {e}")
            
            # Sleep for remaining interval time
            elapsed = time.time() - start_time
            sleep_time = max(0, self.interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.info("Collection loop stopped")
    
    def _flush_buffer(self) -> None:
        """Flush buffer to CSV files."""
        batch = self._buffer.get_batch()
        if batch:
            # Write to new per-hardware structure
            if self._data_manager:
                for metrics in batch:
                    rows_written = self._data_manager.write_metrics(metrics)
                    if rows_written:
                        total = sum(rows_written.values())
                        logger.debug(f"Wrote metrics to {len(rows_written)} hardware files")
            else:
                # Fallback to legacy writer
                written = self._writer.write_batch(batch)
                logger.debug(f"Wrote {written} records to CSV (legacy)")
    
    def _upload_loop(self) -> None:
        """Background upload loop for incremental sync."""
        if not self._cloud_sync:
            return
        
        cloud_config = self.config.get("cloud", {})
        interval_minutes = cloud_config.get("upload_interval_minutes", 5)  # More frequent for incremental
        
        # Initial sync after startup delay
        time.sleep(30)  # Wait 30 seconds before first sync
        
        while self._running:
            try:
                synced = self._cloud_sync.sync()
                if synced:
                    total_rows = sum(synced.values())
                    logger.info(f"Synced {total_rows} rows to cloud ({len(synced)} files)")
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            # Sleep in small increments for responsive shutdown
            for _ in range(interval_minutes * 60):
                if not self._running:
                    return
                time.sleep(1)
    
    def start(self) -> None:
        """Start the logging process."""
        if self._running:
            logger.warning("Logger already running")
            return
        
        self._running = True
        self._session_start = datetime.now()
        
        # Log system info
        system_info = get_system_info(self.config)
        logger.info(f"Starting OptiMetrics Logger")
        logger.info(f"Hardware ID: {self._hardware_id}")
        logger.info(f"CPU: {system_info.cpu_model}")
        logger.info(f"GPU: {', '.join(system_info.gpu_names)}")
        logger.info(f"RAM: {system_info.ram_total_gb} GB")
        logger.info(f"Logging interval: {self.interval}s")
        
        # Start collection thread
        self._collect_thread = threading.Thread(
            target=self._collection_loop,
            name="MetricsCollector",
            daemon=True
        )
        self._collect_thread.start()
        
        # Start upload thread if enabled
        if self._cloud_sync:
            self._upload_thread = threading.Thread(
                target=self._upload_loop,
                name="CloudSync",
                daemon=True
            )
            self._upload_thread.start()
        
        logger.info("Logger started successfully")
    
    def stop(self) -> None:
        """Stop the logging process."""
        if not self._running:
            return
        
        logger.info("Stopping logger...")
        self._running = False
        
        # Wait for threads
        if self._collect_thread:
            self._collect_thread.join(timeout=5)
        
        # Flush remaining buffer
        self._flush_buffer()
        
        # Close writer
        self._writer.close()
        
        # Close data manager
        if self._data_manager:
            self._data_manager.close()
        
        # Final sync before shutdown
        if self._cloud_sync:
            try:
                self._cloud_sync.sync()
            except Exception as e:
                logger.warning(f"Final sync failed: {e}")
        
        # Compress old files
        self._writer.compress_old_files()
        
        # Save session state
        state = SessionState(
            last_timestamp=datetime.now().isoformat(),
            last_log_file=str(get_log_file_path(self.config)),
            hardware_id=self._hardware_id,
            session_start=self._session_start.isoformat(),
            metrics_count=self._metrics_count,
        )
        save_session_state(state)
        
        # Cleanup adapters
        for adapter in self._adapters:
            try:
                adapter.cleanup()
            except Exception:
                pass
        
        logger.info(f"Logger stopped. Total metrics collected: {self._metrics_count}")
    
    def pause(self) -> None:
        """Pause metric collection."""
        self._paused = True
        logger.info("Logger paused")
    
    def resume(self) -> None:
        """Resume metric collection."""
        self._paused = False
        logger.info("Logger resumed")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current logger status."""
        status = {
            "running": self._running,
            "paused": self._paused,
            "metrics_count": self._metrics_count,
            "buffer_size": self._buffer.size(),
            "session_start": self._session_start.isoformat(),
            "hardware_id": self._hardware_id,
            "adapters": [a.adapter_name for a in self._adapters],
            "current_category": (
                self._classifier.get_current_category().name
                if self._classifier and self._classifier.get_current_category()
                else None
            ),
        }
        
        # Add data manager stats
        if self._data_manager:
            status["data_stats"] = self._data_manager.get_stats()
        
        # Add cloud sync stats
        if self._cloud_sync:
            status["cloud_stats"] = self._cloud_sync.get_sync_stats()
        
        return status


def main():
    """Main entry point for the hardware logger."""
    parser = argparse.ArgumentParser(
        description="OptiMetrics Hardware Logger - Automated hardware metrics collection"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file",
        default=None
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (collect for 10 seconds then exit)"
    )
    
    args = parser.parse_args()
    
    # Override verbose setting
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Create logger instance
    hw_logger = HardwareLogger(config_path=args.config)
    
    # Signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nShutdown signal received...")
        hw_logger.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start logging
    hw_logger.start()
    
    if args.test:
        # Test mode: run for 10 seconds
        print("Running in test mode for 10 seconds...")
        time.sleep(10)
        status = hw_logger.get_status()
        print(f"\nTest Results:")
        print(f"  Metrics collected: {status['metrics_count']}")
        print(f"  Adapters active: {', '.join(status['adapters'])}")
        print(f"  Current category: {status['current_category']}")
        hw_logger.stop()
    else:
        # Normal mode: run until interrupted
        print("OptiMetrics Logger running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(60)
                # Periodic status update
                status = hw_logger.get_status()
                logger.info(
                    f"Status: {status['metrics_count']} metrics, "
                    f"category: {status['current_category']}"
                )
        except KeyboardInterrupt:
            pass
        finally:
            hw_logger.stop()


if __name__ == "__main__":
    main()
