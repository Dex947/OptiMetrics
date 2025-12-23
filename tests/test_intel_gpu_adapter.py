"""
Tests for Intel GPU Adapter

Covers:
    - Basic initialization
    - GPU detection on Windows
    - Metric collection
    - Error handling
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.intel_gpu_adapter import IntelGPUAdapter


class TestIntelGPUAdapterBasic:
    """Basic Intel GPU adapter tests."""
    
    def test_initialization(self):
        """Test adapter initializes."""
        adapter = IntelGPUAdapter()
        assert adapter is not None
    
    def test_cleanup_idempotent(self):
        """Test cleanup can be called multiple times."""
        adapter = IntelGPUAdapter()
        adapter.cleanup()
        adapter.cleanup()
    
    def test_collect_without_init(self):
        """Test collecting without initialization returns empty."""
        adapter = IntelGPUAdapter()
        metrics = adapter.collect_metrics()
        assert metrics == {}


class TestIntelGPUAdapterDetection:
    """Tests for Intel GPU detection."""
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_detection_on_windows(self):
        """Test GPU detection on Windows."""
        adapter = IntelGPUAdapter()
        # May or may not find Intel GPU depending on system
        result = adapter.initialize()
        assert isinstance(result, bool)
        adapter.cleanup()
    
    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows only")
    def test_no_detection_on_non_windows(self):
        """Test no detection on non-Windows systems."""
        adapter = IntelGPUAdapter()
        result = adapter.initialize()
        assert result is False


class TestIntelGPUAdapterMetrics:
    """Tests for Intel GPU metrics collection."""
    
    def test_metrics_when_initialized(self):
        """Test metrics collection when initialized."""
        adapter = IntelGPUAdapter()
        
        # Mock initialization
        adapter._initialized = True
        adapter._gpu_name = "Intel Iris Xe Graphics"
        
        metrics = adapter.collect_metrics()
        
        assert "intel_gpu_present" in metrics
        assert metrics["intel_gpu_present"].value == 1
        assert "intel_gpu_name" in metrics
        
        adapter.cleanup()
    
    def test_metrics_have_source(self):
        """Test metrics have source field."""
        adapter = IntelGPUAdapter()
        adapter._initialized = True
        adapter._gpu_name = "Intel UHD Graphics"
        
        metrics = adapter.collect_metrics()
        
        for metric in metrics.values():
            assert metric.source == "wmi"
        
        adapter.cleanup()


class TestIntelGPUAdapterHardwareInfo:
    """Tests for hardware info."""
    
    def test_hardware_info_when_not_initialized(self):
        """Test hardware info returns None when not initialized."""
        adapter = IntelGPUAdapter()
        info = adapter.get_hardware_info()
        assert info is None
    
    def test_hardware_info_when_initialized(self):
        """Test hardware info when initialized."""
        adapter = IntelGPUAdapter()
        
        # Mock initialization
        from src.adapters.base_adapter import HardwareInfo
        adapter._initialized = True
        adapter._gpu_info = HardwareInfo(
            vendor="Intel",
            model="Intel Iris Xe Graphics",
            identifier="intel_gpu_0"
        )
        
        info = adapter.get_hardware_info()
        
        assert info is not None
        assert info.vendor == "Intel"
        assert "Intel" in info.model
        
        adapter.cleanup()


class TestIntelGPUAdapterErrorHandling:
    """Tests for error handling."""
    
    def test_error_count_tracking(self):
        """Test error count is tracked."""
        adapter = IntelGPUAdapter()
        
        initial = adapter._error_count
        adapter.record_error("Test error")
        
        assert adapter._error_count == initial + 1
    
    def test_error_reset(self):
        """Test error count can be reset."""
        adapter = IntelGPUAdapter()
        
        for _ in range(5):
            adapter.record_error("Error")
        
        adapter.reset_error_count()
        assert adapter._error_count == 0
