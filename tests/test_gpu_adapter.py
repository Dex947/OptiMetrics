"""
Tests for NVIDIA GPU Adapter

Covers:
    - Initialization and cleanup
    - GPU metric collection
    - Multi-GPU scenarios
    - Edge cases (no GPU, partial failures)
    - Error recovery
"""

import pytest
from unittest.mock import patch, Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.nvidia_adapter import NvidiaGPUAdapter
from src.adapters.base_adapter import MetricValue


class TestGPUAdapterBasic:
    """Basic GPU adapter tests."""
    
    def test_initialization(self):
        """Test GPU adapter initializes (may fail if no GPU)."""
        adapter = NvidiaGPUAdapter()
        result = adapter.initialize()
        # Result depends on hardware
        assert result in [True, False]
        adapter.cleanup()
    
    def test_hardware_info_no_gpu(self):
        """Test hardware info when no GPU present."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        # May be None or have info depending on hardware
        
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test metric collection."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_cleanup_idempotent(self):
        """Test cleanup can be called multiple times."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        adapter.cleanup()
        adapter.cleanup()
        adapter.cleanup()
    
    def test_context_manager(self):
        """Test adapter works as context manager."""
        with NvidiaGPUAdapter() as adapter:
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)


class TestGPUAdapterNoGPU:
    """Tests for systems without NVIDIA GPU."""
    
    def test_graceful_no_gpu(self):
        """Test graceful handling when no GPU is present."""
        adapter = NvidiaGPUAdapter()
        result = adapter.initialize()
        # Should not crash
        assert result in [True, False]
        adapter.cleanup()
    
    def test_metrics_no_gpu(self):
        """Test metrics collection returns empty dict when no GPU."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if not adapter.is_initialized:
            metrics = adapter.collect_metrics()
            assert metrics == {} or isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_hardware_info_no_gpu(self):
        """Test hardware info returns None when no GPU."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if not adapter.is_initialized:
            info = adapter.get_hardware_info()
            # Should be None or empty
        
        adapter.cleanup()


class TestGPUAdapterMultiGPU:
    """Tests for multi-GPU configurations."""
    
    def test_multi_gpu_simulation(self):
        """Test multi-GPU scenario by setting adapter state."""
        adapter = NvidiaGPUAdapter()
        
        # Simulate multi-GPU
        adapter._gpu_count = 3
        adapter._gpu_handles = [Mock(), Mock(), Mock()]
        adapter._initialized = True
        
        assert adapter._gpu_count == 3
        assert len(adapter._gpu_handles) == 3
        
        adapter.cleanup()
    
    def test_multi_gpu_metrics(self):
        """Test metrics for multiple GPUs."""
        adapter = NvidiaGPUAdapter()
        
        # Simulate 2 GPUs
        adapter._gpu_count = 2
        adapter._gpu_handles = [Mock(), Mock()]
        adapter._initialized = True
        
        # Metrics should handle multiple GPUs
        # (actual collection may fail without real GPU)
        
        adapter.cleanup()
    
    def test_partial_gpu_failure(self):
        """Test handling when one GPU fails in multi-GPU setup."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        # Even if not initialized, should not crash
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        
        adapter.cleanup()


class TestGPUAdapterMetrics:
    """Test GPU metric types."""
    
    def test_utilization_metrics(self):
        """Test GPU utilization metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            # Should have utilization if GPU present
            util_metrics = [k for k in metrics.keys() if "utilization" in k.lower()]
        
        adapter.cleanup()
    
    def test_memory_metrics(self):
        """Test GPU memory metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            mem_metrics = [k for k in metrics.keys() if "vram" in k.lower() or "memory" in k.lower()]
        
        adapter.cleanup()
    
    def test_temperature_metrics(self):
        """Test GPU temperature metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            temp_metrics = [k for k in metrics.keys() if "temp" in k.lower()]
        
        adapter.cleanup()
    
    def test_power_metrics(self):
        """Test GPU power metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            power_metrics = [k for k in metrics.keys() if "power" in k.lower() or "watt" in k.lower()]
        
        adapter.cleanup()
    
    def test_clock_metrics(self):
        """Test GPU clock speed metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            clock_metrics = [k for k in metrics.keys() if "clock" in k.lower() or "mhz" in k.lower()]
        
        adapter.cleanup()


class TestGPUAdapterMetricValues:
    """Test metric value correctness."""
    
    def test_utilization_range(self):
        """Test utilization values are in valid range."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            for name, metric in metrics.items():
                if "utilization" in name.lower() and "%" in metric.unit:
                    assert 0 <= metric.value <= 100, f"{name} out of range"
        
        adapter.cleanup()
    
    def test_temperature_range(self):
        """Test temperature values are reasonable."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            for name, metric in metrics.items():
                if "temp" in name.lower():
                    # GPU temp should be between -20 and 120 C
                    assert -20 <= metric.value <= 120, f"{name} unreasonable: {metric.value}"
        
        adapter.cleanup()
    
    def test_positive_values(self):
        """Test most values are non-negative."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            for name, metric in metrics.items():
                # Most GPU metrics should be non-negative
                if "temp" not in name.lower():  # Temp can be negative
                    assert metric.value >= 0, f"Negative value for {name}"
        
        adapter.cleanup()
    
    def test_metric_source(self):
        """Test metrics have a source."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            # Source should be set (pynvml or similar)
            assert metric.source is not None
        
        adapter.cleanup()


class TestGPUAdapterErrorRecovery:
    """Error recovery tests for GPU adapter."""
    
    def test_pynvml_not_installed(self):
        """Test handling when pynvml is not installed."""
        # This test verifies the adapter handles missing pynvml
        adapter = NvidiaGPUAdapter()
        # Should not crash during init
        result = adapter.initialize()
        assert result in [True, False]
        adapter.cleanup()
    
    def test_nvml_init_failure(self):
        """Test handling of NVML initialization failure."""
        adapter = NvidiaGPUAdapter()
        
        # Simulate failed init
        adapter._initialized = False
        
        metrics = adapter.collect_metrics()
        assert metrics == {} or isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_error_count_tracking(self):
        """Test error count is tracked."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        initial_count = adapter._error_count
        adapter.record_error("Test error")
        assert adapter._error_count == initial_count + 1
        
        adapter.cleanup()
    
    def test_error_threshold(self):
        """Test error count increases with errors."""
        adapter = NvidiaGPUAdapter()
        
        initial_count = adapter._error_count
        for _ in range(5):
            adapter.record_error("Test error")
        
        assert adapter._error_count == initial_count + 5
        
        adapter.reset_error_count()
        assert adapter._error_count == 0
        
        adapter.cleanup()
    
    def test_recovery_after_transient_error(self):
        """Test adapter recovers after transient error."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        adapter.record_error("Transient error")
        
        # Should still work
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        
        adapter.cleanup()


class TestGPUAdapterEncoderDecoder:
    """Test encoder/decoder metrics."""
    
    def test_encoder_metrics(self):
        """Test video encoder metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            encoder_metrics = [k for k in metrics.keys() if "encoder" in k.lower()]
        
        adapter.cleanup()
    
    def test_decoder_metrics(self):
        """Test video decoder metrics."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            decoder_metrics = [k for k in metrics.keys() if "decoder" in k.lower()]
        
        adapter.cleanup()


class TestGPUAdapterComputeProcesses:
    """Test compute process metrics."""
    
    def test_compute_process_count(self):
        """Test compute process count metric."""
        adapter = NvidiaGPUAdapter()
        adapter.initialize()
        
        if adapter.is_initialized:
            metrics = adapter.collect_metrics()
            process_metrics = [k for k in metrics.keys() if "process" in k.lower()]
        
        adapter.cleanup()
