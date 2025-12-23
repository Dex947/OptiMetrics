"""
Hardware Adapters Module

This module contains modular adapters for different hardware vendors and platforms.
Contributors can add new adapters by implementing the base adapter interface.

Available Adapters:
    - nvidia_adapter: NVIDIA GPU metrics via pynvml
    - amd_adapter: AMD GPU metrics (placeholder for ROCm integration)
    - intel_adapter: Intel GPU and CPU-specific metrics
    - cpu_adapter: Cross-platform CPU metrics
    - disk_adapter: Storage device metrics
    - network_adapter: Network interface metrics
"""

from .base_adapter import BaseHardwareAdapter
from .cpu_adapter import CPUAdapter
from .nvidia_adapter import NvidiaGPUAdapter
from .memory_adapter import MemoryAdapter
from .disk_adapter import DiskAdapter
from .network_adapter import NetworkAdapter

__all__ = [
    "BaseHardwareAdapter",
    "CPUAdapter", 
    "NvidiaGPUAdapter",
    "MemoryAdapter",
    "DiskAdapter",
    "NetworkAdapter",
]
