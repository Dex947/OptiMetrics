"""
Base Hardware Adapter Interface

All hardware adapters must inherit from BaseHardwareAdapter and implement
the required methods. This ensures consistent behavior across different
hardware types and vendors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricValue:
    """Represents a single metric measurement."""
    name: str
    value: Any
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    is_available: bool = True
    error_message: Optional[str] = None


@dataclass
class HardwareInfo:
    """Represents hardware identification information."""
    vendor: str
    model: str
    identifier: str
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)


class BaseHardwareAdapter(ABC):
    """
    Abstract base class for all hardware adapters.
    
    Contributors should inherit from this class and implement all abstract
    methods to add support for new hardware types or vendors.
    
    Example:
        class MyCustomAdapter(BaseHardwareAdapter):
            def initialize(self) -> bool:
                # Initialize hardware access
                return True
            
            def get_hardware_info(self) -> HardwareInfo:
                # Return hardware identification
                pass
            
            def collect_metrics(self) -> Dict[str, MetricValue]:
                # Collect and return current metrics
                pass
            
            def cleanup(self) -> None:
                # Release resources
                pass
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the adapter with optional configuration.
        
        Args:
            config: Optional dictionary containing adapter-specific settings
        """
        self.config = config or {}
        self._initialized = False
        self._hardware_info: Optional[HardwareInfo] = None
        self._last_metrics: Dict[str, MetricValue] = {}
        self._error_count = 0
        self._max_errors = 10
    
    @property
    def is_initialized(self) -> bool:
        """Check if the adapter has been successfully initialized."""
        return self._initialized
    
    @property
    def adapter_name(self) -> str:
        """Return the name of this adapter."""
        return self.__class__.__name__
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the hardware adapter.
        
        This method should:
        - Check if the hardware is present
        - Initialize any required libraries or drivers
        - Verify access permissions
        
        Returns:
            True if initialization was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """
        Get hardware identification information.
        
        Returns:
            HardwareInfo object containing vendor, model, and capabilities,
            or None if hardware info cannot be retrieved
        """
        pass
    
    @abstractmethod
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """
        Collect current hardware metrics.
        
        Returns:
            Dictionary mapping metric names to MetricValue objects
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """
        Clean up resources and close connections.
        
        This method should release any held resources, close file handles,
        and perform any necessary cleanup operations.
        """
        pass
    
    def get_metric_names(self) -> List[str]:
        """
        Get list of metric names this adapter can collect.
        
        Returns:
            List of metric name strings
        """
        if self._last_metrics:
            return list(self._last_metrics.keys())
        return []
    
    def is_available(self) -> bool:
        """
        Check if the hardware is currently available.
        
        Returns:
            True if hardware is accessible, False otherwise
        """
        return self._initialized and self._error_count < self._max_errors
    
    def record_error(self, error_message: str) -> None:
        """
        Record an error occurrence.
        
        Args:
            error_message: Description of the error
        """
        self._error_count += 1
    
    def reset_error_count(self) -> None:
        """Reset the error counter after successful operations."""
        self._error_count = 0
    
    def get_csv_headers(self) -> List[str]:
        """
        Get CSV column headers for this adapter's metrics.
        
        Returns:
            List of column header strings
        """
        return [f"{self.adapter_name}_{name}" for name in self.get_metric_names()]
    
    def get_csv_values(self) -> List[Any]:
        """
        Get current metric values formatted for CSV output.
        
        Returns:
            List of values corresponding to CSV headers
        """
        return [
            m.value if m.is_available else None 
            for m in self._last_metrics.values()
        ]
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False
