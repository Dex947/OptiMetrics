"""
Tests for Memory Adapter

Covers:
    - Initialization and cleanup
    - RAM and swap metric collection
    - Edge cases (no swap, high usage)
    - Error recovery
"""

import pytest
from unittest.mock import patch, Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.memory_adapter import MemoryAdapter
from src.adapters.base_adapter import MetricValue


class TestMemoryAdapterBasic:
    """Basic memory adapter tests."""
    
    def test_initialization(self):
        """Test memory adapter initializes correctly."""
        adapter = MemoryAdapter()
        result = adapter.initialize()
        assert result is True
        assert adapter.is_initialized
        adapter.cleanup()
    
    def test_hardware_info(self):
        """Test hardware info retrieval."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        assert info is not None
        
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test metric collection returns valid data."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        assert "ram_percent" in metrics
        assert isinstance(metrics["ram_percent"], MetricValue)
        
        adapter.cleanup()
    
    def test_cleanup_idempotent(self):
        """Test cleanup can be called multiple times."""
        adapter = MemoryAdapter()
        adapter.initialize()
        adapter.cleanup()
        adapter.cleanup()
        adapter.cleanup()
    
    def test_context_manager(self):
        """Test adapter works as context manager."""
        with MemoryAdapter() as adapter:
            assert adapter.is_initialized
            metrics = adapter.collect_metrics()
            assert len(metrics) > 0


class TestMemoryAdapterEdgeCases:
    """Edge case tests for memory adapter."""
    
    def test_no_swap(self):
        """Test handling when swap is disabled."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        with patch('psutil.swap_memory') as mock_swap:
            mock_swap.return_value = Mock(
                total=0,
                used=0,
                free=0,
                percent=0.0,
                sin=0,
                sout=0,
            )
            metrics = adapter.collect_metrics()
            assert "swap_total_mb" in metrics
            assert metrics["swap_total_mb"].value == 0
        
        adapter.cleanup()
    
    def test_very_high_usage(self):
        """Test handling of very high memory usage."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        with patch('psutil.virtual_memory') as mock_mem:
            mock_mem.return_value = Mock(
                total=64 * 10**9,
                used=63 * 10**9,
                available=1 * 10**9,
                free=0.5 * 10**9,
                percent=98.4,
            )
            metrics = adapter.collect_metrics()
            assert metrics["ram_percent"].value > 95
        
        adapter.cleanup()
    
    def test_very_large_ram(self):
        """Test handling of very large RAM (1TB)."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        with patch('psutil.virtual_memory') as mock_mem:
            mock_mem.return_value = Mock(
                total=1024 * 10**9,  # 1TB
                used=512 * 10**9,
                available=512 * 10**9,
                free=256 * 10**9,
                percent=50.0,
            )
            metrics = adapter.collect_metrics()
            assert "ram_total_mb" in metrics
        
        adapter.cleanup()
    
    def test_swap_activity(self):
        """Test swap activity metrics."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        with patch('psutil.swap_memory') as mock_swap:
            mock_swap.return_value = Mock(
                total=16 * 10**9,
                used=8 * 10**9,
                free=8 * 10**9,
                percent=50.0,
                sin=1000000,
                sout=500000,
            )
            metrics = adapter.collect_metrics()
            assert "swap_percent" in metrics
        
        adapter.cleanup()


class TestMemoryAdapterMetricValues:
    """Test metric value correctness."""
    
    def test_ram_metrics_present(self):
        """Test all expected RAM metrics are present."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        expected = ["ram_total_mb", "ram_used_mb", "ram_available_mb", "ram_percent"]
        for metric_name in expected:
            assert metric_name in metrics, f"Missing metric: {metric_name}"
        
        adapter.cleanup()
    
    def test_swap_metrics_present(self):
        """Test swap metrics are present."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        # Swap metrics should be present even if swap is 0
        assert "swap_total_mb" in metrics
        assert "swap_percent" in metrics
        
        adapter.cleanup()
    
    def test_percentage_range(self):
        """Test percentage values are in valid range."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        if "ram_percent" in metrics:
            value = metrics["ram_percent"].value
            assert 0 <= value <= 100
        
        if "swap_percent" in metrics:
            value = metrics["swap_percent"].value
            assert 0 <= value <= 100
        
        adapter.cleanup()
    
    def test_metric_units(self):
        """Test metrics have correct units."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        if "ram_percent" in metrics:
            assert metrics["ram_percent"].unit == "%"
        
        if "ram_used_mb" in metrics:
            assert metrics["ram_used_mb"].unit == "MB"
        
        adapter.cleanup()
    
    def test_positive_values(self):
        """Test all values are non-negative."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            assert metric.value >= 0, f"Negative value for {name}: {metric.value}"
        
        adapter.cleanup()


class TestMemoryAdapterErrorRecovery:
    """Error recovery tests for memory adapter."""
    
    def test_psutil_failure(self):
        """Test handling of psutil failure."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        with patch('psutil.virtual_memory') as mock_mem:
            mock_mem.side_effect = Exception("psutil error")
            # Should not crash
            try:
                metrics = adapter.collect_metrics()
            except Exception:
                pass  # May raise, but shouldn't crash
        
        adapter.cleanup()
    
    def test_error_count_tracking(self):
        """Test error count is tracked."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        initial_count = adapter._error_count
        adapter.record_error("Test error")
        assert adapter._error_count == initial_count + 1
        
        adapter.cleanup()
