"""
Intel GPU Hardware Adapter

Collects GPU metrics from Intel integrated GPUs using WMI on Windows.
Provides basic metrics for Intel Iris/UHD graphics.
"""

import sys
from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue

# Windows-only WMI support
HAS_WMI = False
if sys.platform == "win32":
    try:
        import wmi
        HAS_WMI = True
    except ImportError:
        pass


class IntelGPUAdapter(BaseHardwareAdapter):
    """
    Intel GPU metrics adapter using WMI.
    
    Collects basic metrics for Intel integrated graphics:
        - GPU name and identification
        - Basic availability status
    
    Note: Intel GPUs don't expose detailed utilization metrics via standard APIs.
    For detailed Intel GPU monitoring, Intel GPU Tools would be needed.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._gpu_name = ""
        self._gpu_info: Optional[HardwareInfo] = None
    
    def initialize(self) -> bool:
        """Initialize Intel GPU detection via WMI."""
        if not HAS_WMI:
            return False
        
        try:
            c = wmi.WMI()
            
            # Find Intel GPU
            for gpu in c.Win32_VideoController():
                name = gpu.Name or ""
                if "intel" in name.lower():
                    self._gpu_name = name
                    self._gpu_info = HardwareInfo(
                        vendor="Intel",
                        model=name,
                        identifier=f"intel_gpu_{gpu.DeviceID or '0'}"
                    )
                    self._initialized = True
                    return True
            
            return False
            
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get Intel GPU identification information."""
        return self._gpu_info
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """
        Collect Intel GPU metrics.
        
        Note: Intel integrated GPUs don't expose detailed metrics via WMI.
        This adapter primarily provides identification and basic status.
        """
        if not self._initialized:
            return {}
        
        metrics = {}
        
        # Basic presence metric
        metrics["intel_gpu_present"] = MetricValue(
            name="intel_gpu_present",
            value=1,
            unit="bool",
            source="wmi"
        )
        
        metrics["intel_gpu_name"] = MetricValue(
            name="intel_gpu_name",
            value=self._gpu_name,
            unit="",
            source="wmi"
        )
        
        return metrics
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self._initialized = False
        self._gpu_name = ""
        self._gpu_info = None
