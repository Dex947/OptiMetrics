"""
Disk/Storage Hardware Adapter

Collects disk metrics including I/O statistics, usage, and performance
for all mounted storage devices.
"""

import sys
from typing import Dict, Any, Optional, List
import psutil

from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue


class DiskAdapter(BaseHardwareAdapter):
    """
    Disk/Storage metrics adapter.
    
    Collects:
        - Disk usage (total, used, free) per partition
        - Disk I/O statistics (read/write bytes, counts, time)
        - I/O throughput rates
        - Disk queue depth (where available)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._partitions: List[Any] = []
        self._prev_io_counters: Optional[Dict[str, Any]] = None
        self._prev_timestamp: Optional[float] = None
    
    def initialize(self) -> bool:
        """Initialize disk monitoring."""
        try:
            self._partitions = psutil.disk_partitions(all=False)
            self._prev_io_counters = psutil.disk_io_counters(perdisk=True)
            import time
            self._prev_timestamp = time.time()
            self._initialized = True
            return True
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get disk hardware information."""
        if self._hardware_info:
            return self._hardware_info
        
        try:
            disk_info = []
            total_size_gb = 0.0
            
            for partition in self._partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    size_gb = round(usage.total / (1024**3), 2)
                    total_size_gb += size_gb
                    disk_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "size_gb": size_gb,
                    })
                except (PermissionError, OSError):
                    continue
            
            self._hardware_info = HardwareInfo(
                vendor="System",
                model=f"Storage {round(total_size_gb, 0)} GB",
                identifier=f"DISK_{len(disk_info)}drives_{round(total_size_gb)}GB",
                additional_info={
                    "total_storage_gb": round(total_size_gb, 2),
                    "partition_count": len(disk_info),
                    "partitions": disk_info,
                }
            )
            return self._hardware_info
            
        except Exception as e:
            self.record_error(str(e))
            return None
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """Collect current disk metrics."""
        import time
        metrics = {}
        
        try:
            current_time = time.time()
            
            # Disk Usage per partition
            for partition in self._partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    # Create safe partition name for metric key
                    if sys.platform == "win32":
                        # Windows: C:\ -> c_drive
                        part_name = partition.device[0].lower() + "_drive"
                    else:
                        # Unix: /dev/sda1 -> sda1
                        part_name = partition.device.split("/")[-1]
                    
                    metrics[f"disk_{part_name}_total_gb"] = MetricValue(
                        name=f"disk_{part_name}_total_gb",
                        value=round(usage.total / (1024**3), 2),
                        unit="GB",
                        source="psutil"
                    )
                    metrics[f"disk_{part_name}_used_gb"] = MetricValue(
                        name=f"disk_{part_name}_used_gb",
                        value=round(usage.used / (1024**3), 2),
                        unit="GB",
                        source="psutil"
                    )
                    metrics[f"disk_{part_name}_free_gb"] = MetricValue(
                        name=f"disk_{part_name}_free_gb",
                        value=round(usage.free / (1024**3), 2),
                        unit="GB",
                        source="psutil"
                    )
                    metrics[f"disk_{part_name}_percent"] = MetricValue(
                        name=f"disk_{part_name}_percent",
                        value=round(usage.percent, 2),
                        unit="%",
                        source="psutil"
                    )
                except (PermissionError, OSError):
                    continue
            
            # Disk I/O Statistics
            io_counters = psutil.disk_io_counters(perdisk=False)
            if io_counters:
                metrics["disk_read_bytes"] = MetricValue(
                    name="disk_read_bytes",
                    value=io_counters.read_bytes,
                    unit="bytes",
                    source="psutil"
                )
                metrics["disk_write_bytes"] = MetricValue(
                    name="disk_write_bytes",
                    value=io_counters.write_bytes,
                    unit="bytes",
                    source="psutil"
                )
                metrics["disk_read_count"] = MetricValue(
                    name="disk_read_count",
                    value=io_counters.read_count,
                    unit="count",
                    source="psutil"
                )
                metrics["disk_write_count"] = MetricValue(
                    name="disk_write_count",
                    value=io_counters.write_count,
                    unit="count",
                    source="psutil"
                )
                metrics["disk_read_time_ms"] = MetricValue(
                    name="disk_read_time_ms",
                    value=io_counters.read_time,
                    unit="ms",
                    source="psutil"
                )
                metrics["disk_write_time_ms"] = MetricValue(
                    name="disk_write_time_ms",
                    value=io_counters.write_time,
                    unit="ms",
                    source="psutil"
                )
                
                # Calculate I/O rates if we have previous measurements
                if self._prev_io_counters and self._prev_timestamp:
                    time_delta = current_time - self._prev_timestamp
                    if time_delta > 0:
                        # Get previous total counters
                        prev_total = psutil.disk_io_counters(perdisk=False)
                        if prev_total and hasattr(self, "_prev_total_io"):
                            read_rate = (io_counters.read_bytes - self._prev_total_io.read_bytes) / time_delta
                            write_rate = (io_counters.write_bytes - self._prev_total_io.write_bytes) / time_delta
                            
                            metrics["disk_read_rate_mbps"] = MetricValue(
                                name="disk_read_rate_mbps",
                                value=round(read_rate / (1024**2), 2),
                                unit="MB/s",
                                source="psutil"
                            )
                            metrics["disk_write_rate_mbps"] = MetricValue(
                                name="disk_write_rate_mbps",
                                value=round(write_rate / (1024**2), 2),
                                unit="MB/s",
                                source="psutil"
                            )
                
                # Store current values for next rate calculation
                self._prev_total_io = io_counters
            
            # Per-disk I/O (for detailed monitoring)
            io_per_disk = psutil.disk_io_counters(perdisk=True)
            if io_per_disk:
                for disk_name, counters in io_per_disk.items():
                    # Skip loop devices and other virtual disks
                    if disk_name.startswith("loop") or disk_name.startswith("ram"):
                        continue
                    
                    safe_name = disk_name.replace(":", "").replace("/", "_")
                    
                    metrics[f"disk_{safe_name}_read_mb"] = MetricValue(
                        name=f"disk_{safe_name}_read_mb",
                        value=round(counters.read_bytes / (1024**2), 2),
                        unit="MB",
                        source="psutil"
                    )
                    metrics[f"disk_{safe_name}_write_mb"] = MetricValue(
                        name=f"disk_{safe_name}_write_mb",
                        value=round(counters.write_bytes / (1024**2), 2),
                        unit="MB",
                        source="psutil"
                    )
            
            self._prev_io_counters = io_per_disk
            self._prev_timestamp = current_time
            self._last_metrics = metrics
            self.reset_error_count()
            
        except Exception as e:
            self.record_error(str(e))
        
        return metrics
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._initialized = False
        self._prev_io_counters = None
        self._prev_timestamp = None
