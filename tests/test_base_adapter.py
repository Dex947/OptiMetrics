"""
Tests for Base Adapter

Covers:
    - Abstract base class interface
    - MetricValue and HardwareInfo dataclasses
    - Error tracking
    - Availability checks
"""

import pytest
from unittest.mock import Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.base_adapter import BaseHardwareAdapter, MetricValue, HardwareInfo


class TestMetricValue:
    """Tests for MetricValue dataclass."""
    
    def test_creation(self):
        """Test MetricValue creation."""
        metric = MetricValue(
            name="test_metric",
            value=50.0,
            unit="%",
            source="test"
        )
        assert metric.name == "test_metric"
        assert metric.value == 50.0
        assert metric.unit == "%"
        assert metric.source == "test"
    
    def test_default_source(self):
        """Test MetricValue with default source."""
        metric = MetricValue(name="test", value=1.0, unit="")
        assert metric.source == ""
    
    def test_integer_value(self):
        """Test MetricValue with integer value."""
        metric = MetricValue(name="count", value=100, unit="count")
        assert metric.value == 100
    
    def test_zero_value(self):
        """Test MetricValue with zero value."""
        metric = MetricValue(name="zero", value=0, unit="")
        assert metric.value == 0
    
    def test_negative_value(self):
        """Test MetricValue with negative value."""
        metric = MetricValue(name="temp", value=-10.5, unit="C")
        assert metric.value == -10.5
    
    def test_string_representation(self):
        """Test MetricValue string representation."""
        metric = MetricValue(name="test", value=50.0, unit="%")
        str_repr = str(metric)
        assert "test" in str_repr or "50" in str_repr


class TestHardwareInfo:
    """Tests for HardwareInfo dataclass."""
    
    def test_creation(self):
        """Test HardwareInfo creation."""
        info = HardwareInfo(
            vendor="Intel",
            model="Core i7-12700K",
            identifier="cpu_0"
        )
        assert info.vendor == "Intel"
        assert info.model == "Core i7-12700K"
        assert info.identifier == "cpu_0"
    
    def test_optional_fields(self):
        """Test HardwareInfo with basic fields."""
        info = HardwareInfo(
            vendor="NVIDIA",
            model="RTX 3080",
            identifier="gpu_0",
        )
        assert info.vendor == "NVIDIA"
        assert info.model == "RTX 3080"
    
    def test_empty_values(self):
        """Test HardwareInfo with empty values."""
        info = HardwareInfo(vendor="", model="", identifier="")
        assert info.vendor == ""
    
    def test_unicode_values(self):
        """Test HardwareInfo with unicode values."""
        info = HardwareInfo(
            vendor="Intel®",
            model="Core™ i7",
            identifier="cpu_0"
        )
        assert "Intel" in info.vendor


class ConcreteAdapter(BaseHardwareAdapter):
    """Concrete implementation for testing."""
    
    def initialize(self) -> bool:
        self._initialized = True
        return True
    
    def get_hardware_info(self) -> HardwareInfo:
        return HardwareInfo(
            vendor="Test",
            model="TestAdapter",
            identifier="test_0"
        )
    
    def collect_metrics(self) -> dict:
        return {
            "test_metric": MetricValue(
                name="test_metric",
                value=42.0,
                unit="%",
                source="test"
            )
        }
    
    def cleanup(self) -> None:
        self._initialized = False


class TestBaseHardwareAdapter:
    """Tests for BaseHardwareAdapter interface."""
    
    def test_concrete_implementation(self):
        """Test concrete adapter implementation."""
        adapter = ConcreteAdapter()
        assert adapter is not None
    
    def test_initialize(self):
        """Test adapter initialization."""
        adapter = ConcreteAdapter()
        result = adapter.initialize()
        assert result is True
        assert adapter.is_initialized
    
    def test_get_hardware_info(self):
        """Test getting hardware info."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        assert info is not None
        assert info.vendor == "Test"
    
    def test_collect_metrics(self):
        """Test collecting metrics."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert "test_metric" in metrics
        assert metrics["test_metric"].value == 42.0
    
    def test_cleanup(self):
        """Test adapter cleanup."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        adapter.cleanup()
        
        assert not adapter.is_initialized
    
    def test_context_manager(self):
        """Test adapter as context manager."""
        with ConcreteAdapter() as adapter:
            assert adapter.is_initialized
            metrics = adapter.collect_metrics()
            assert len(metrics) > 0


class TestAdapterErrorTracking:
    """Tests for error tracking functionality."""
    
    def test_initial_error_count(self):
        """Test initial error count is zero."""
        adapter = ConcreteAdapter()
        assert adapter._error_count == 0
    
    def test_record_error(self):
        """Test recording an error."""
        adapter = ConcreteAdapter()
        adapter.record_error("Test error")
        assert adapter._error_count == 1
    
    def test_multiple_errors(self):
        """Test recording multiple errors."""
        adapter = ConcreteAdapter()
        for i in range(5):
            adapter.record_error(f"Error {i}")
        assert adapter._error_count == 5
    
    def test_reset_error_count(self):
        """Test resetting error count."""
        adapter = ConcreteAdapter()
        for _ in range(5):
            adapter.record_error("Error")
        
        adapter.reset_error_count()
        assert adapter._error_count == 0
    
    def test_error_threshold(self):
        """Test error threshold for availability."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        
        # Below threshold
        for _ in range(9):
            adapter.record_error("Error")
        assert adapter.is_available() is True
        
        # At/above threshold
        for _ in range(6):
            adapter.record_error("Error")
        assert adapter.is_available() is False


class TestAdapterAvailability:
    """Tests for adapter availability."""
    
    def test_available_after_init(self):
        """Test adapter is available after initialization."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        assert adapter.is_available() is True
    
    def test_unavailable_after_errors(self):
        """Test adapter becomes unavailable after too many errors."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        
        for _ in range(15):
            adapter.record_error("Error")
        
        assert adapter.is_available() is False
    
    def test_available_after_reset(self):
        """Test adapter becomes available after error reset."""
        adapter = ConcreteAdapter()
        adapter.initialize()
        
        for _ in range(15):
            adapter.record_error("Error")
        
        adapter.reset_error_count()
        assert adapter.is_available() is True


class TestAdapterProperties:
    """Tests for adapter properties."""
    
    def test_is_initialized_property(self):
        """Test is_initialized property."""
        adapter = ConcreteAdapter()
        assert adapter.is_initialized is False
        
        adapter.initialize()
        assert adapter.is_initialized is True
    
    def test_name_property(self):
        """Test adapter class name."""
        adapter = ConcreteAdapter()
        assert type(adapter).__name__ == "ConcreteAdapter"
