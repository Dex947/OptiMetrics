"""
Memory (RAM) Hardware Adapter

Collects system memory metrics including RAM usage, swap/page file usage,
and memory allocation patterns.
"""

from typing import Dict, Any, Optional
import psutil

from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue


class MemoryAdapter(BaseHardwareAdapter):
    """
    System memory metrics adapter.
    
    Collects:
        - Total, used, available, and free RAM
        - RAM utilization percentage
        - Swap/page file usage
        - Memory buffers and cache (Linux)
        - Shared memory usage
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._total_ram_gb = 0.0
    
    def initialize(self) -> bool:
        """Initialize memory monitoring."""
        try:
            mem = psutil.virtual_memory()
            self._total_ram_gb = round(mem.total / (1024**3), 2)
            self._initialized = True
            return True
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get memory hardware information."""
        if self._hardware_info:
            return self._hardware_info
        
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            self._hardware_info = HardwareInfo(
                vendor="System",
                model=f"RAM {self._total_ram_gb} GB",
                identifier=f"RAM_{self._total_ram_gb}GB",
                additional_info={
                    "total_ram_gb": self._total_ram_gb,
                    "total_swap_gb": round(swap.total / (1024**3), 2),
                }
            )
            return self._hardware_info
            
        except Exception as e:
            self.record_error(str(e))
            return None
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """Collect current memory metrics."""
        metrics = {}
        
        try:
            # Virtual Memory (RAM)
            mem = psutil.virtual_memory()
            
            metrics["ram_total_mb"] = MetricValue(
                name="ram_total_mb",
                value=round(mem.total / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["ram_used_mb"] = MetricValue(
                name="ram_used_mb",
                value=round(mem.used / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["ram_available_mb"] = MetricValue(
                name="ram_available_mb",
                value=round(mem.available / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["ram_free_mb"] = MetricValue(
                name="ram_free_mb",
                value=round(mem.free / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["ram_percent"] = MetricValue(
                name="ram_percent",
                value=round(mem.percent, 2),
                unit="%",
                source="psutil"
            )
            
            # Platform-specific memory metrics
            if hasattr(mem, "buffers"):
                metrics["ram_buffers_mb"] = MetricValue(
                    name="ram_buffers_mb",
                    value=round(mem.buffers / (1024**2), 2),
                    unit="MB",
                    source="psutil"
                )
            
            if hasattr(mem, "cached"):
                metrics["ram_cached_mb"] = MetricValue(
                    name="ram_cached_mb",
                    value=round(mem.cached / (1024**2), 2),
                    unit="MB",
                    source="psutil"
                )
            
            if hasattr(mem, "shared"):
                metrics["ram_shared_mb"] = MetricValue(
                    name="ram_shared_mb",
                    value=round(mem.shared / (1024**2), 2),
                    unit="MB",
                    source="psutil"
                )
            
            # Swap Memory
            swap = psutil.swap_memory()
            
            metrics["swap_total_mb"] = MetricValue(
                name="swap_total_mb",
                value=round(swap.total / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["swap_used_mb"] = MetricValue(
                name="swap_used_mb",
                value=round(swap.used / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["swap_free_mb"] = MetricValue(
                name="swap_free_mb",
                value=round(swap.free / (1024**2), 2),
                unit="MB",
                source="psutil"
            )
            metrics["swap_percent"] = MetricValue(
                name="swap_percent",
                value=round(swap.percent, 2),
                unit="%",
                source="psutil"
            )
            
            # Swap I/O counters (if available)
            if hasattr(swap, "sin") and hasattr(swap, "sout"):
                metrics["swap_in_mb"] = MetricValue(
                    name="swap_in_mb",
                    value=round(swap.sin / (1024**2), 2),
                    unit="MB",
                    source="psutil"
                )
                metrics["swap_out_mb"] = MetricValue(
                    name="swap_out_mb",
                    value=round(swap.sout / (1024**2), 2),
                    unit="MB",
                    source="psutil"
                )
            
            self._last_metrics = metrics
            self.reset_error_count()
            
        except Exception as e:
            self.record_error(str(e))
        
        return metrics
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._initialized = False
