"""
Tests for CPU Adapter

Covers:
    - Initialization and cleanup
    - Metric collection
    - Edge cases (single core, many cores, missing features)
    - Error recovery
"""

import pytest
from unittest.mock import patch, Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.cpu_adapter import CPUAdapter
from src.adapters.base_adapter import MetricValue


class TestCPUAdapterBasic:
    """Basic CPU adapter tests."""
    
    def test_initialization(self):
        """Test CPU adapter initializes correctly."""
        adapter = CPUAdapter()
        result = adapter.initialize()
        assert result is True
        assert adapter.is_initialized
        adapter.cleanup()
    
    def test_hardware_info(self):
        """Test hardware info retrieval."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        assert info is not None
        assert info.vendor is not None
        assert info.model is not None
        
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test metric collection returns valid data."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        assert "total_utilization" in metrics
        assert isinstance(metrics["total_utilization"], MetricValue)
        assert 0 <= metrics["total_utilization"].value <= 100
        
        adapter.cleanup()
    
    def test_cleanup_idempotent(self):
        """Test cleanup can be called multiple times."""
        adapter = CPUAdapter()
        adapter.initialize()
        adapter.cleanup()
        adapter.cleanup()  # Should not raise
        adapter.cleanup()  # Should not raise
    
    def test_context_manager(self):
        """Test adapter works as context manager."""
        with CPUAdapter() as adapter:
            assert adapter.is_initialized
            metrics = adapter.collect_metrics()
            assert len(metrics) > 0


class TestCPUAdapterEdgeCases:
    """Edge case tests for CPU adapter."""
    
    def test_single_core_cpu(self):
        """Test handling of single-core CPU."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch('psutil.cpu_count') as mock_count:
            mock_count.return_value = 1
            metrics = adapter.collect_metrics()
            assert "total_utilization" in metrics
        
        adapter.cleanup()
    
    def test_many_core_cpu(self):
        """Test handling of many-core CPU (128 cores)."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch('psutil.cpu_percent') as mock_percent:
            mock_percent.return_value = [50.0] * 128
            metrics = adapter.collect_metrics()
            assert "total_utilization" in metrics
        
        adapter.cleanup()
    
    def test_frequency_unavailable(self):
        """Test handling when CPU frequency is unavailable."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch('psutil.cpu_freq') as mock_freq:
            mock_freq.return_value = None
            metrics = adapter.collect_metrics()
            assert "total_utilization" in metrics
        
        adapter.cleanup()
    
    def test_temperature_unavailable(self):
        """Test handling when temperature sensors are unavailable."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch.object(adapter, '_get_cpu_temperature') as mock_temp:
            mock_temp.return_value = None
            metrics = adapter.collect_metrics()
            assert "total_utilization" in metrics
        
        adapter.cleanup()
    
    def test_per_core_metrics(self):
        """Test per-core metric collection."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        # Should have at least one core metric
        core_metrics = [k for k in metrics.keys() if k.startswith("core_")]
        assert len(core_metrics) > 0
        
        adapter.cleanup()
    
    def test_context_switches(self):
        """Test context switch metric collection."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        if "context_switches" in metrics:
            assert metrics["context_switches"].value >= 0
        
        adapter.cleanup()


class TestCPUAdapterErrorRecovery:
    """Error recovery tests for CPU adapter."""
    
    def test_error_count_threshold(self):
        """Test adapter becomes unavailable after too many errors."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        for _ in range(15):
            adapter.record_error("Test error")
        
        assert adapter.is_available() is False
        
        adapter.reset_error_count()
        assert adapter.is_available() is True
        
        adapter.cleanup()
    
    def test_double_initialization(self):
        """Test double initialization is handled."""
        adapter = CPUAdapter()
        result1 = adapter.initialize()
        result2 = adapter.initialize()
        
        assert result1 is True
        assert result2 is True  # Should be idempotent
        
        adapter.cleanup()
    
    def test_collect_without_init(self):
        """Test collecting metrics without initialization."""
        adapter = CPUAdapter()
        # Don't initialize
        metrics = adapter.collect_metrics()
        # Should return empty or handle gracefully
        assert isinstance(metrics, dict)
        adapter.cleanup()


class TestCPUAdapterMetricValues:
    """Test metric value correctness."""
    
    def test_utilization_range(self):
        """Test utilization values are in valid range."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        for _ in range(5):
            metrics = adapter.collect_metrics()
            if "total_utilization" in metrics:
                value = metrics["total_utilization"].value
                assert 0 <= value <= 100, f"Utilization {value} out of range"
        
        adapter.cleanup()
    
    def test_metric_units(self):
        """Test metrics have correct units."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        if "total_utilization" in metrics:
            assert metrics["total_utilization"].unit == "%"
        
        adapter.cleanup()
    
    def test_metric_source(self):
        """Test metrics have a source."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            # Source should be set (may vary by implementation)
            assert metric.source is not None
        
        adapter.cleanup()
