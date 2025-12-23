"""
OptiMetrics Data Manager

Handles structured data storage with:
- Per-device folders (using hardware_id)
- Separate CSV files per hardware type
- Incremental uploads that append to existing cloud files
- Accurate UTC timestamps with timezone info
"""

import csv
import json
import gzip
import shutil
import logging
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger("optimetrics.data_manager")


@dataclass
class HardwareFile:
    """Represents a hardware-specific CSV file."""
    hardware_type: str  # cpu, gpu_nvidia, gpu_intel, memory, disk, network
    local_path: Path
    cloud_file_id: Optional[str] = None
    last_row_uploaded: int = 0
    total_rows: int = 0
    last_modified: Optional[str] = None


class DeviceDataManager:
    """
    Manages data storage for a single device.
    
    Structure:
        logs/
            {hardware_id}/
                cpu.csv
                gpu_nvidia.csv
                gpu_intel.csv
                memory.csv
                disk.csv
                network.csv
                device_info.json
                sync_state.json
    """
    
    HARDWARE_TYPES = [
        "cpu",
        "gpu_nvidia", 
        "gpu_intel",
        "memory",
        "disk",
        "network"
    ]
    
    # Column definitions for each hardware type
    COLUMNS = {
        "cpu": [
            "timestamp", "hardware_id",
            "cpu_percent_total", "cpu_percent_per_core",
            "cpu_freq_current_mhz", "cpu_freq_max_mhz",
            "cpu_ctx_switches", "cpu_interrupts",
            "cpu_temp_celsius", "cpu_load_1min", "cpu_load_5min", "cpu_load_15min"
        ],
        "gpu_nvidia": [
            "timestamp", "hardware_id", "gpu_index", "gpu_name",
            "gpu_utilization_percent", "gpu_memory_used_mb", "gpu_memory_total_mb",
            "gpu_memory_percent", "gpu_temp_celsius", "gpu_power_watts",
            "gpu_fan_speed_percent", "gpu_clock_graphics_mhz", "gpu_clock_memory_mhz",
            "gpu_encoder_util_percent", "gpu_decoder_util_percent"
        ],
        "gpu_intel": [
            "timestamp", "hardware_id", "gpu_index", "gpu_name",
            "gpu_present", "gpu_driver_version"
        ],
        "memory": [
            "timestamp", "hardware_id",
            "ram_total_gb", "ram_available_gb", "ram_used_gb", "ram_percent",
            "swap_total_gb", "swap_used_gb", "swap_percent"
        ],
        "disk": [
            "timestamp", "hardware_id",
            "disk_read_bytes", "disk_write_bytes",
            "disk_read_count", "disk_write_count",
            "disk_read_time_ms", "disk_write_time_ms",
            "disk_usage_percent", "disk_free_gb"
        ],
        "network": [
            "timestamp", "hardware_id",
            "net_bytes_sent", "net_bytes_recv",
            "net_packets_sent", "net_packets_recv",
            "net_errors_in", "net_errors_out",
            "net_drop_in", "net_drop_out"
        ]
    }
    
    def __init__(self, hardware_id: str, base_dir: Optional[Path] = None):
        """
        Initialize device data manager.
        
        Args:
            hardware_id: Unique device identifier
            base_dir: Base directory for logs (default: project_root/logs)
        """
        self.hardware_id = hardware_id
        
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "logs"
        
        self.device_dir = base_dir / hardware_id
        self.device_dir.mkdir(parents=True, exist_ok=True)
        
        self._files: Dict[str, HardwareFile] = {}
        self._file_handles: Dict[str, Any] = {}
        self._csv_writers: Dict[str, csv.DictWriter] = {}
        self._lock = threading.Lock()
        
        # Load or create sync state
        self._sync_state_path = self.device_dir / "sync_state.json"
        self._sync_state = self._load_sync_state()
        
        # Initialize hardware files
        self._init_files()
        
        # Save device info
        self._save_device_info()
    
    def _load_sync_state(self) -> Dict[str, Any]:
        """Load sync state from disk."""
        if self._sync_state_path.exists():
            try:
                with open(self._sync_state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Failed to load sync state, starting fresh")
        
        return {
            "files": {},
            "last_sync": None,
            "device_folder_id": None
        }
    
    def _save_sync_state(self) -> None:
        """Save sync state to disk."""
        try:
            with open(self._sync_state_path, "w", encoding="utf-8") as f:
                json.dump(self._sync_state, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save sync state: {e}")
    
    def _save_device_info(self) -> None:
        """Save device information."""
        info_path = self.device_dir / "device_info.json"
        
        try:
            import platform
            info = {
                "hardware_id": self.hardware_id,
                "platform": platform.system(),
                "platform_version": platform.version(),
                "processor": platform.processor(),
                "machine": platform.machine(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Only update if file doesn't exist
            if not info_path.exists():
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save device info: {e}")
    
    def _init_files(self) -> None:
        """Initialize CSV files for each hardware type."""
        for hw_type in self.HARDWARE_TYPES:
            file_path = self.device_dir / f"{hw_type}.csv"
            
            # Get existing row count
            row_count = 0
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        row_count = sum(1 for _ in f) - 1  # Subtract header
                        if row_count < 0:
                            row_count = 0
                except IOError:
                    pass
            
            # Load sync state for this file
            file_state = self._sync_state.get("files", {}).get(hw_type, {})
            
            self._files[hw_type] = HardwareFile(
                hardware_type=hw_type,
                local_path=file_path,
                cloud_file_id=file_state.get("cloud_file_id"),
                last_row_uploaded=file_state.get("last_row_uploaded", 0),
                total_rows=row_count,
                last_modified=file_state.get("last_modified")
            )
    
    def _get_writer(self, hw_type: str, record: Dict[str, Any]) -> csv.DictWriter:
        """Get or create CSV writer for hardware type."""
        file_info = self._files[hw_type]
        file_exists = file_info.local_path.exists() and file_info.local_path.stat().st_size > 0
        
        # Get columns from record keys (dynamic schema)
        record_columns = list(record.keys())
        
        # Check if we need to recreate writer (new columns detected)
        if hw_type in self._csv_writers and self._file_handles.get(hw_type) is not None:
            existing_columns = getattr(self._csv_writers[hw_type], 'fieldnames', [])
            new_columns = [c for c in record_columns if c not in existing_columns]
            if not new_columns:
                return self._csv_writers[hw_type]
            # New columns detected - need to handle schema evolution
            # For now, just use extrasaction="ignore" and continue
        
        if hw_type not in self._csv_writers or self._file_handles.get(hw_type) is None:
            # Close existing handle if any
            if hw_type in self._file_handles and self._file_handles[hw_type]:
                try:
                    self._file_handles[hw_type].close()
                except:
                    pass
            
            # Read existing headers if file exists
            if file_exists:
                try:
                    with open(file_info.local_path, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        existing_headers = next(reader, [])
                        # Merge with new columns
                        for col in record_columns:
                            if col not in existing_headers:
                                existing_headers.append(col)
                        record_columns = existing_headers
                except:
                    pass
            
            # Open file in append mode
            self._file_handles[hw_type] = open(
                file_info.local_path, "a", newline="", encoding="utf-8"
            )
            
            self._csv_writers[hw_type] = csv.DictWriter(
                self._file_handles[hw_type],
                fieldnames=record_columns,
                extrasaction="ignore"
            )
            
            # Write header if new file
            if not file_exists:
                self._csv_writers[hw_type].writeheader()
                self._file_handles[hw_type].flush()
        
        return self._csv_writers[hw_type]
    
    def _get_utc_timestamp(self) -> str:
        """Get accurate UTC timestamp with timezone."""
        return datetime.now(timezone.utc).isoformat()
    
    def write_metrics(self, metrics: Dict[str, Any]) -> Dict[str, int]:
        """
        Write metrics to appropriate hardware files.
        
        Args:
            metrics: Dictionary of all collected metrics
        
        Returns:
            Dictionary of rows written per hardware type
        """
        timestamp = self._get_utc_timestamp()
        rows_written = {}
        
        with self._lock:
            # Categorize metrics by hardware type
            categorized = self._categorize_metrics(metrics, timestamp)
            
            for hw_type, records in categorized.items():
                if not records:
                    continue
                
                for record in records:
                    writer = self._get_writer(hw_type, record)
                    writer.writerow(record)
                    self._files[hw_type].total_rows += 1
                
                if hw_type in self._file_handles and self._file_handles[hw_type]:
                    self._file_handles[hw_type].flush()
                self._files[hw_type].last_modified = timestamp
                rows_written[hw_type] = len(records)
        
        return rows_written
    
    def _categorize_metrics(
        self, 
        metrics: Dict[str, Any], 
        timestamp: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize metrics into hardware-specific records."""
        categorized: Dict[str, List[Dict[str, Any]]] = {
            hw_type: [] for hw_type in self.HARDWARE_TYPES
        }
        
        base_record = {
            "timestamp": timestamp,
            "hardware_id": self.hardware_id
        }
        
        # CPU metrics - detect by key patterns from CPUAdapter
        # Keys: core_*_utilization, core_*_freq_mhz, total_utilization, avg_freq_mhz,
        # context_switches, interrupts, soft_interrupts, temperature, power_watts, load_avg_*
        cpu_keys = [
            "core_", "total_utilization", "avg_freq", "freq_mhz", "freq_min", "freq_max",
            "context_switches", "interrupts", "soft_interrupts", "temperature", "power_watts",
            "syscalls", "load_avg", "load_1", "load_5", "load_15"
        ]
        # CPU-specific keys that should NOT go to GPU even if they match
        cpu_specific = ["core_0", "core_1", "core_2", "core_3", "core_4", "core_5", 
                       "core_6", "core_7", "core_8", "core_9", "core_10", "core_11",
                       "core_12", "core_13", "core_14", "core_15", "core_16", "core_17",
                       "core_18", "core_19", "total_utilization", "avg_freq", "context_switches",
                       "soft_interrupts", "load_avg", "interrupts"]
        
        cpu_record = base_record.copy()
        cpu_has_data = False
        for key, value in metrics.items():
            if any(key.startswith(p) or key == p for p in cpu_keys):
                cpu_record[f"cpu_{key}"] = value
                cpu_has_data = True
        if cpu_has_data:
            categorized["cpu"].append(cpu_record)
        
        # GPU NVIDIA metrics - detect by key patterns from NvidiaGPUAdapter
        # Keys: utilization, memory_utilization, vram_*, temperature, power_watts, 
        # *_clock_mhz, fan_speed, pcie_*, encoder_*, decoder_*, compute_processes, etc.
        nvidia_keys = [
            "utilization", "vram_", "temperature", "power_watts", "power_limit",
            "core_clock", "memory_clock", "sm_clock", "fan_speed", 
            "pcie_tx", "pcie_rx", "encoder_", "decoder_", 
            "compute_processes", "graphics_processes", "performance_state"
        ]
        
        gpu_record = base_record.copy()
        gpu_has_data = False
        for key, value in metrics.items():
            # Skip if it's a CPU-specific key
            if any(cpu_key in key for cpu_key in cpu_specific):
                continue
            # Skip memory/disk/network keys
            if any(key.startswith(p) for p in ["ram_", "swap_", "disk_", "net_"]):
                continue
            if "intel" in key.lower():
                continue
            # Check if key matches nvidia patterns
            if any(p in key.lower() for p in nvidia_keys):
                gpu_record[f"gpu_{key}"] = value
                gpu_has_data = True
        if gpu_has_data:
            gpu_record["gpu_index"] = 0
            categorized["gpu_nvidia"].append(gpu_record)
        
        # GPU Intel metrics
        intel_record = base_record.copy()
        intel_has_data = False
        for key, value in metrics.items():
            if "intel" in key.lower():
                intel_record[key] = value
                intel_has_data = True
        if intel_has_data:
            intel_record["gpu_index"] = 0
            categorized["gpu_intel"].append(intel_record)
        
        # Memory metrics - detect by key patterns from MemoryAdapter
        mem_keys = ["ram_", "swap_", "memory_"]
        mem_record = base_record.copy()
        mem_has_data = False
        for key, value in metrics.items():
            if any(key.startswith(p) for p in mem_keys):
                mem_record[key] = value
                mem_has_data = True
        if mem_has_data:
            categorized["memory"].append(mem_record)
        
        # Disk metrics - detect by key patterns from DiskAdapter
        disk_keys = ["disk_", "read_bytes", "write_bytes", "read_count", "write_count", "io_"]
        disk_record = base_record.copy()
        disk_has_data = False
        for key, value in metrics.items():
            if any(key.startswith(p) or p in key.lower() for p in disk_keys):
                if not any(key.startswith(m) for m in mem_keys):  # Exclude memory keys
                    disk_record[key] = value
                    disk_has_data = True
        if disk_has_data:
            categorized["disk"].append(disk_record)
        
        # Network metrics - detect by key patterns from NetworkAdapter
        net_keys = ["net_", "bytes_sent", "bytes_recv", "packets_", "errors_", "drop_"]
        net_record = base_record.copy()
        net_has_data = False
        for key, value in metrics.items():
            if any(key.startswith(p) or p in key.lower() for p in net_keys):
                net_record[key] = value
                net_has_data = True
        if net_has_data:
            categorized["network"].append(net_record)
        
        return categorized
    
    def get_pending_uploads(self) -> List[Tuple[str, Path, int, int]]:
        """
        Get files with rows pending upload.
        
        Returns:
            List of (hw_type, file_path, start_row, end_row) tuples
        """
        pending = []
        for hw_type, file_info in self._files.items():
            if file_info.total_rows > file_info.last_row_uploaded:
                pending.append((
                    hw_type,
                    file_info.local_path,
                    file_info.last_row_uploaded,
                    file_info.total_rows
                ))
        return pending
    
    def mark_uploaded(self, hw_type: str, rows_uploaded: int, cloud_file_id: str) -> None:
        """Mark rows as uploaded for a hardware type."""
        with self._lock:
            if hw_type in self._files:
                self._files[hw_type].last_row_uploaded = rows_uploaded
                self._files[hw_type].cloud_file_id = cloud_file_id
                
                # Update sync state
                if "files" not in self._sync_state:
                    self._sync_state["files"] = {}
                
                self._sync_state["files"][hw_type] = {
                    "cloud_file_id": cloud_file_id,
                    "last_row_uploaded": rows_uploaded,
                    "last_modified": datetime.now(timezone.utc).isoformat()
                }
                self._sync_state["last_sync"] = datetime.now(timezone.utc).isoformat()
                self._save_sync_state()
    
    def set_device_folder_id(self, folder_id: str) -> None:
        """Set the cloud folder ID for this device."""
        self._sync_state["device_folder_id"] = folder_id
        self._save_sync_state()
    
    def get_device_folder_id(self) -> Optional[str]:
        """Get the cloud folder ID for this device."""
        return self._sync_state.get("device_folder_id")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about data collection."""
        stats = {
            "hardware_id": self.hardware_id,
            "device_dir": str(self.device_dir),
            "files": {}
        }
        
        for hw_type, file_info in self._files.items():
            stats["files"][hw_type] = {
                "total_rows": file_info.total_rows,
                "rows_uploaded": file_info.last_row_uploaded,
                "pending_rows": file_info.total_rows - file_info.last_row_uploaded,
                "cloud_file_id": file_info.cloud_file_id,
                "file_size_kb": (
                    file_info.local_path.stat().st_size / 1024 
                    if file_info.local_path.exists() else 0
                )
            }
        
        return stats
    
    def close(self) -> None:
        """Close all file handles."""
        with self._lock:
            for hw_type, handle in self._file_handles.items():
                if handle:
                    try:
                        handle.close()
                    except Exception:
                        pass
            self._file_handles.clear()
            self._csv_writers.clear()
            self._save_sync_state()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def extract_rows_from_csv(
    file_path: Path, 
    start_row: int, 
    end_row: Optional[int] = None
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Extract specific rows from a CSV file.
    
    Args:
        file_path: Path to CSV file
        start_row: Starting row (0-indexed, excluding header)
        end_row: Ending row (exclusive), None for all remaining
    
    Returns:
        Tuple of (headers, rows)
    """
    headers = []
    rows = []
    
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        
        for i, row in enumerate(reader):
            if i < start_row:
                continue
            if end_row is not None and i >= end_row:
                break
            rows.append(row)
    
    return headers, rows


def rows_to_csv_string(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    """Convert rows to CSV string for upload."""
    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
