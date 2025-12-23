"""
NVIDIA GPU Hardware Adapter

Collects GPU metrics from NVIDIA GPUs using pynvml (NVIDIA Management Library).
Supports multiple GPUs and provides detailed metrics including utilization,
memory, temperature, power, and clock speeds.
"""

import sys
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue


class NvidiaGPUAdapter(BaseHardwareAdapter):
    """
    NVIDIA GPU metrics adapter using pynvml.
    
    Collects:
        - GPU utilization percentage
        - Memory utilization and usage (used/total VRAM)
        - GPU temperature
        - Power consumption and limit
        - Core clock and memory clock speeds
        - Fan speed
        - PCIe throughput
        - Encoder/decoder utilization
        - Process count on GPU
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._gpu_count = 0
        self._gpu_handles: List[Any] = []
        self._gpu_infos: List[HardwareInfo] = []
    
    def initialize(self) -> bool:
        """Initialize NVIDIA GPU monitoring via pynvml."""
        if not HAS_PYNVML:
            return False
        
        try:
            pynvml.nvmlInit()
            self._gpu_count = pynvml.nvmlDeviceGetCount()
            
            if self._gpu_count == 0:
                return False
            
            # Get handles for all GPUs
            self._gpu_handles = []
            for i in range(self._gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                self._gpu_handles.append(handle)
            
            self._initialized = True
            return True
            
        except pynvml.NVMLError as e:
            self.record_error(str(e))
            return False
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get GPU identification information for all detected GPUs."""
        if not self._initialized or not self._gpu_handles:
            return None
        
        if self._hardware_info:
            return self._hardware_info
        
        try:
            # Get info for primary GPU (index 0)
            handle = self._gpu_handles[0]
            
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            
            # Get driver version
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver_version, bytes):
                driver_version = driver_version.decode("utf-8")
            
            # Get CUDA version
            try:
                cuda_version = pynvml.nvmlSystemGetCudaDriverVersion_v2()
                cuda_major = cuda_version // 1000
                cuda_minor = (cuda_version % 1000) // 10
                cuda_str = f"{cuda_major}.{cuda_minor}"
            except Exception:
                cuda_str = "Unknown"
            
            # Get memory info
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_vram_gb = round(mem_info.total / (1024**3), 2)
            
            # Get compute capability
            try:
                major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                compute_cap = f"{major}.{minor}"
            except Exception:
                compute_cap = "Unknown"
            
            # Get PCIe info
            try:
                pcie_gen = pynvml.nvmlDeviceGetCurrPcieLinkGeneration(handle)
                pcie_width = pynvml.nvmlDeviceGetCurrPcieLinkWidth(handle)
                pcie_info = f"Gen{pcie_gen} x{pcie_width}"
            except Exception:
                pcie_info = "Unknown"
            
            capabilities = ["CUDA", f"Compute {compute_cap}"]
            
            # Check for tensor cores (Volta and newer)
            if compute_cap != "Unknown":
                major = int(compute_cap.split(".")[0])
                if major >= 7:
                    capabilities.append("Tensor Cores")
                if major >= 8:
                    capabilities.append("RT Cores")
            
            self._hardware_info = HardwareInfo(
                vendor="NVIDIA",
                model=name,
                identifier=f"NVIDIA_{name.replace(' ', '_')}_{total_vram_gb}GB",
                driver_version=driver_version,
                capabilities=capabilities,
                additional_info={
                    "gpu_count": self._gpu_count,
                    "total_vram_gb": total_vram_gb,
                    "cuda_version": cuda_str,
                    "compute_capability": compute_cap,
                    "pcie": pcie_info,
                }
            )
            
            return self._hardware_info
            
        except Exception as e:
            self.record_error(str(e))
            return None
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """Collect current GPU metrics for all detected GPUs."""
        metrics = {}
        
        if not self._initialized:
            return metrics
        
        try:
            for gpu_idx, handle in enumerate(self._gpu_handles):
                prefix = f"gpu{gpu_idx}_" if self._gpu_count > 1 else ""
                
                # GPU Utilization
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    metrics[f"{prefix}utilization"] = MetricValue(
                        name=f"{prefix}utilization",
                        value=util.gpu,
                        unit="%",
                        source="pynvml"
                    )
                    metrics[f"{prefix}memory_utilization"] = MetricValue(
                        name=f"{prefix}memory_utilization",
                        value=util.memory,
                        unit="%",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Memory Usage
                try:
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    metrics[f"{prefix}vram_used_mb"] = MetricValue(
                        name=f"{prefix}vram_used_mb",
                        value=round(mem.used / (1024**2), 2),
                        unit="MB",
                        source="pynvml"
                    )
                    metrics[f"{prefix}vram_total_mb"] = MetricValue(
                        name=f"{prefix}vram_total_mb",
                        value=round(mem.total / (1024**2), 2),
                        unit="MB",
                        source="pynvml"
                    )
                    metrics[f"{prefix}vram_free_mb"] = MetricValue(
                        name=f"{prefix}vram_free_mb",
                        value=round(mem.free / (1024**2), 2),
                        unit="MB",
                        source="pynvml"
                    )
                    metrics[f"{prefix}vram_percent"] = MetricValue(
                        name=f"{prefix}vram_percent",
                        value=round((mem.used / mem.total) * 100, 2),
                        unit="%",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Temperature
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                    metrics[f"{prefix}temperature"] = MetricValue(
                        name=f"{prefix}temperature",
                        value=temp,
                        unit="°C",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Power
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W
                    metrics[f"{prefix}power_watts"] = MetricValue(
                        name=f"{prefix}power_watts",
                        value=round(power, 2),
                        unit="W",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                try:
                    power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
                    metrics[f"{prefix}power_limit_watts"] = MetricValue(
                        name=f"{prefix}power_limit_watts",
                        value=round(power_limit, 2),
                        unit="W",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Clock Speeds
                try:
                    graphics_clock = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_GRAPHICS
                    )
                    metrics[f"{prefix}core_clock_mhz"] = MetricValue(
                        name=f"{prefix}core_clock_mhz",
                        value=graphics_clock,
                        unit="MHz",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                try:
                    mem_clock = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_MEM
                    )
                    metrics[f"{prefix}memory_clock_mhz"] = MetricValue(
                        name=f"{prefix}memory_clock_mhz",
                        value=mem_clock,
                        unit="MHz",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                try:
                    sm_clock = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_SM
                    )
                    metrics[f"{prefix}sm_clock_mhz"] = MetricValue(
                        name=f"{prefix}sm_clock_mhz",
                        value=sm_clock,
                        unit="MHz",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Fan Speed
                try:
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                    metrics[f"{prefix}fan_speed"] = MetricValue(
                        name=f"{prefix}fan_speed",
                        value=fan_speed,
                        unit="%",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # PCIe Throughput
                try:
                    pcie_tx = pynvml.nvmlDeviceGetPcieThroughput(
                        handle, pynvml.NVML_PCIE_UTIL_TX_BYTES
                    )
                    pcie_rx = pynvml.nvmlDeviceGetPcieThroughput(
                        handle, pynvml.NVML_PCIE_UTIL_RX_BYTES
                    )
                    metrics[f"{prefix}pcie_tx_kbps"] = MetricValue(
                        name=f"{prefix}pcie_tx_kbps",
                        value=pcie_tx,
                        unit="KB/s",
                        source="pynvml"
                    )
                    metrics[f"{prefix}pcie_rx_kbps"] = MetricValue(
                        name=f"{prefix}pcie_rx_kbps",
                        value=pcie_rx,
                        unit="KB/s",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Encoder/Decoder Utilization
                try:
                    enc_util, _ = pynvml.nvmlDeviceGetEncoderUtilization(handle)
                    metrics[f"{prefix}encoder_utilization"] = MetricValue(
                        name=f"{prefix}encoder_utilization",
                        value=enc_util,
                        unit="%",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                try:
                    dec_util, _ = pynvml.nvmlDeviceGetDecoderUtilization(handle)
                    metrics[f"{prefix}decoder_utilization"] = MetricValue(
                        name=f"{prefix}decoder_utilization",
                        value=dec_util,
                        unit="%",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Process Count on GPU
                try:
                    processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                    metrics[f"{prefix}compute_processes"] = MetricValue(
                        name=f"{prefix}compute_processes",
                        value=len(processes),
                        unit="count",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                try:
                    graphics_processes = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
                    metrics[f"{prefix}graphics_processes"] = MetricValue(
                        name=f"{prefix}graphics_processes",
                        value=len(graphics_processes),
                        unit="count",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
                
                # Performance State
                try:
                    pstate = pynvml.nvmlDeviceGetPerformanceState(handle)
                    metrics[f"{prefix}performance_state"] = MetricValue(
                        name=f"{prefix}performance_state",
                        value=pstate,
                        unit="P-state",
                        source="pynvml"
                    )
                except pynvml.NVMLError:
                    pass
            
            self._last_metrics = metrics
            self.reset_error_count()
            
        except Exception as e:
            self.record_error(str(e))
        
        return metrics
    
    def cleanup(self) -> None:
        """Shutdown pynvml."""
        if HAS_PYNVML and self._initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
        self._initialized = False
        self._gpu_handles = []
