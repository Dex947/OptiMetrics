"""
CPU Hardware Adapter

Collects CPU metrics including per-core utilization, frequency, temperature,
power consumption, and cache information across Windows, Linux, and macOS.
"""

import os
import sys
import platform
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import psutil

try:
    import cpuinfo
    HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

if sys.platform == "win32":
    try:
        import wmi
        import pythoncom
        HAS_WMI = True
    except ImportError:
        HAS_WMI = False
else:
    HAS_WMI = False

from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue


class CPUAdapter(BaseHardwareAdapter):
    """
    Cross-platform CPU metrics adapter.
    
    Collects:
        - Per-core utilization percentage
        - Current and base frequency per core
        - CPU temperature (where available)
        - Power consumption (where available)
        - Cache sizes (L1, L2, L3)
        - Context switches and interrupts
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._wmi_conn = None
        self._cpu_count = psutil.cpu_count(logical=True)
        self._cpu_count_physical = psutil.cpu_count(logical=False)
        self._prev_cpu_times = None
    
    def initialize(self) -> bool:
        """Initialize CPU monitoring capabilities."""
        try:
            # Test basic CPU access
            psutil.cpu_percent(interval=None, percpu=True)
            psutil.cpu_freq(percpu=True)
            
            # Initialize WMI on Windows for additional metrics
            if HAS_WMI and sys.platform == "win32":
                try:
                    pythoncom.CoInitialize()
                    self._wmi_conn = wmi.WMI(namespace="root\\wmi")
                except Exception:
                    self._wmi_conn = None
            
            self._initialized = True
            return True
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get CPU identification information."""
        if self._hardware_info:
            return self._hardware_info
        
        try:
            info_dict = {}
            
            if HAS_CPUINFO:
                cpu_data = cpuinfo.get_cpu_info()
                info_dict = {
                    "vendor": cpu_data.get("vendor_id_raw", "Unknown"),
                    "model": cpu_data.get("brand_raw", "Unknown CPU"),
                    "arch": cpu_data.get("arch", ""),
                    "bits": cpu_data.get("bits", 64),
                    "hz_advertised": cpu_data.get("hz_advertised_friendly", ""),
                    "l2_cache": cpu_data.get("l2_cache_size", ""),
                    "l3_cache": cpu_data.get("l3_cache_size", ""),
                    "flags": cpu_data.get("flags", []),
                }
            else:
                info_dict = {
                    "vendor": platform.processor() or "Unknown",
                    "model": platform.processor() or "Unknown CPU",
                    "arch": platform.machine(),
                    "bits": 64 if sys.maxsize > 2**32 else 32,
                }
            
            capabilities = []
            if "avx" in str(info_dict.get("flags", [])).lower():
                capabilities.append("AVX")
            if "avx2" in str(info_dict.get("flags", [])).lower():
                capabilities.append("AVX2")
            if "avx512" in str(info_dict.get("flags", [])).lower():
                capabilities.append("AVX-512")
            if "sse4" in str(info_dict.get("flags", [])).lower():
                capabilities.append("SSE4")
            
            self._hardware_info = HardwareInfo(
                vendor=info_dict.get("vendor", "Unknown"),
                model=info_dict.get("model", "Unknown CPU"),
                identifier=f"CPU_{self._cpu_count_physical}C_{self._cpu_count}T",
                capabilities=capabilities,
                additional_info={
                    "physical_cores": self._cpu_count_physical,
                    "logical_cores": self._cpu_count,
                    "architecture": info_dict.get("arch", ""),
                    "l2_cache": info_dict.get("l2_cache", ""),
                    "l3_cache": info_dict.get("l3_cache", ""),
                }
            )
            return self._hardware_info
            
        except Exception as e:
            self.record_error(str(e))
            return None
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """Collect current CPU metrics."""
        metrics = {}
        
        try:
            # Per-core utilization
            cpu_percents = psutil.cpu_percent(interval=None, percpu=True)
            for i, percent in enumerate(cpu_percents):
                metrics[f"core_{i}_utilization"] = MetricValue(
                    name=f"core_{i}_utilization",
                    value=round(percent, 2),
                    unit="%",
                    source="psutil"
                )
            
            # Overall CPU utilization
            metrics["total_utilization"] = MetricValue(
                name="total_utilization",
                value=round(sum(cpu_percents) / len(cpu_percents), 2),
                unit="%",
                source="psutil"
            )
            
            # CPU frequency
            freq_info = psutil.cpu_freq(percpu=True)
            if freq_info:
                if isinstance(freq_info, list):
                    for i, freq in enumerate(freq_info):
                        if freq:
                            metrics[f"core_{i}_freq_mhz"] = MetricValue(
                                name=f"core_{i}_freq_mhz",
                                value=round(freq.current, 2),
                                unit="MHz",
                                source="psutil"
                            )
                    # Average frequency
                    avg_freq = sum(f.current for f in freq_info if f) / len(freq_info)
                    metrics["avg_freq_mhz"] = MetricValue(
                        name="avg_freq_mhz",
                        value=round(avg_freq, 2),
                        unit="MHz",
                        source="psutil"
                    )
                else:
                    metrics["freq_mhz"] = MetricValue(
                        name="freq_mhz",
                        value=round(freq_info.current, 2),
                        unit="MHz",
                        source="psutil"
                    )
                    metrics["freq_min_mhz"] = MetricValue(
                        name="freq_min_mhz",
                        value=round(freq_info.min, 2),
                        unit="MHz",
                        source="psutil"
                    )
                    metrics["freq_max_mhz"] = MetricValue(
                        name="freq_max_mhz",
                        value=round(freq_info.max, 2),
                        unit="MHz",
                        source="psutil"
                    )
            
            # CPU times (for context switches, interrupts)
            cpu_stats = psutil.cpu_stats()
            metrics["context_switches"] = MetricValue(
                name="context_switches",
                value=cpu_stats.ctx_switches,
                unit="count",
                source="psutil"
            )
            metrics["interrupts"] = MetricValue(
                name="interrupts",
                value=cpu_stats.interrupts,
                unit="count",
                source="psutil"
            )
            metrics["soft_interrupts"] = MetricValue(
                name="soft_interrupts",
                value=cpu_stats.soft_interrupts,
                unit="count",
                source="psutil"
            )
            
            # CPU temperature (platform-specific)
            temps = self._get_cpu_temperature()
            if temps is not None:
                metrics["temperature"] = MetricValue(
                    name="temperature",
                    value=round(temps, 2),
                    unit="°C",
                    source="platform_specific"
                )
            
            # CPU power (Windows WMI)
            power = self._get_cpu_power()
            if power is not None:
                metrics["power_watts"] = MetricValue(
                    name="power_watts",
                    value=round(power, 2),
                    unit="W",
                    source="wmi"
                )
            
            # Load averages (Unix-like systems)
            if hasattr(psutil, "getloadavg"):
                try:
                    load1, load5, load15 = psutil.getloadavg()
                    metrics["load_avg_1m"] = MetricValue(
                        name="load_avg_1m",
                        value=round(load1, 2),
                        unit="",
                        source="psutil"
                    )
                    metrics["load_avg_5m"] = MetricValue(
                        name="load_avg_5m",
                        value=round(load5, 2),
                        unit="",
                        source="psutil"
                    )
                    metrics["load_avg_15m"] = MetricValue(
                        name="load_avg_15m",
                        value=round(load15, 2),
                        unit="",
                        source="psutil"
                    )
                except Exception:
                    pass
            
            self._last_metrics = metrics
            self.reset_error_count()
            
        except Exception as e:
            self.record_error(str(e))
        
        return metrics
    
    def _get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature using platform-specific methods."""
        try:
            # Try psutil sensors (Linux)
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    # Look for CPU temperature sensors
                    for name in ["coretemp", "k10temp", "cpu_thermal", "cpu-thermal"]:
                        if name in temps:
                            readings = temps[name]
                            if readings:
                                return sum(r.current for r in readings) / len(readings)
                    # Fallback to first available sensor
                    for sensor_readings in temps.values():
                        if sensor_readings:
                            return sensor_readings[0].current
            
            # Windows WMI method - try multiple approaches
            if HAS_WMI and sys.platform == "win32":
                try:
                    # Try root\wmi namespace for thermal zone
                    c = wmi.WMI(namespace="root\\wmi")
                    temp_data = c.MSAcpi_ThermalZoneTemperature()
                    if temp_data:
                        # Convert from tenths of Kelvin to Celsius
                        kelvin = temp_data[0].CurrentTemperature / 10.0
                        return kelvin - 273.15
                except Exception:
                    pass
                
                try:
                    # Try OpenHardwareMonitor/LibreHardwareMonitor WMI interface
                    c = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                    sensors = c.Sensor()
                    for sensor in sensors:
                        if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                            return float(sensor.Value)
                except Exception:
                    pass
                
                try:
                    # Try LibreHardwareMonitor WMI interface
                    c = wmi.WMI(namespace="root\\LibreHardwareMonitor")
                    sensors = c.Sensor()
                    for sensor in sensors:
                        if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                            return float(sensor.Value)
                except Exception:
                    pass
            
        except Exception:
            pass
        
        return None
    
    def _get_cpu_power(self) -> Optional[float]:
        """Get CPU power consumption (Windows only via WMI/RAPL)."""
        if HAS_WMI and sys.platform == "win32":
            try:
                # Try OpenHardwareMonitor WMI interface
                c = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                sensors = c.Sensor()
                for sensor in sensors:
                    if sensor.SensorType == "Power" and "CPU" in sensor.Name:
                        return float(sensor.Value)
            except Exception:
                pass
            
            try:
                # Try LibreHardwareMonitor WMI interface
                c = wmi.WMI(namespace="root\\LibreHardwareMonitor")
                sensors = c.Sensor()
                for sensor in sensors:
                    if sensor.SensorType == "Power" and "CPU" in sensor.Name:
                        return float(sensor.Value)
            except Exception:
                pass
        
        return None
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if HAS_WMI and sys.platform == "win32":
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        self._initialized = False
