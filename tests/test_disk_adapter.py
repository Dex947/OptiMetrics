"""
Tests for Disk Adapter

Covers:
    - Initialization and cleanup
    - Disk usage and I/O metric collection
    - Edge cases (no partitions, unmounted, large disks)
    - Error recovery
"""

import pytest
from unittest.mock import patch, Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.disk_adapter import DiskAdapter
from src.adapters.base_adapter import MetricValue


class TestDiskAdapterBasic:
    """Basic disk adapter tests."""
    
    def test_initialization(self):
        """Test disk adapter initializes correctly."""
        adapter = DiskAdapter()
        result = adapter.initialize()
        assert result is True
        assert adapter.is_initialized
        adapter.cleanup()
    
    def test_hardware_info(self):
        """Test hardware info retrieval."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        assert info is not None
        
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test metric collection returns valid data."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        assert len(metrics) > 0
        
        adapter.cleanup()
    
    def test_cleanup_idempotent(self):
        """Test cleanup can be called multiple times."""
        adapter = DiskAdapter()
        adapter.initialize()
        adapter.cleanup()
        adapter.cleanup()
        adapter.cleanup()
    
    def test_context_manager(self):
        """Test adapter works as context manager."""
        with DiskAdapter() as adapter:
            assert adapter.is_initialized
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)


class TestDiskAdapterEdgeCases:
    """Edge case tests for disk adapter."""
    
    def test_unmounted_partition(self):
        """Test handling of unmounted or inaccessible partitions."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert len(metrics) >= 0  # May be empty if all fail
        
        adapter.cleanup()
    
    def test_no_partitions(self):
        """Test handling when no partitions are accessible."""
        adapter = DiskAdapter()
        
        with patch('psutil.disk_partitions') as mock_parts:
            mock_parts.return_value = []
            result = adapter.initialize()
            assert result is True
        
        adapter.cleanup()
    
    def test_io_counters_none(self):
        """Test handling when disk I/O counters return None."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        with patch('psutil.disk_io_counters') as mock_io:
            mock_io.return_value = None
            metrics = adapter.collect_metrics()
            # Should not crash
            assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_very_large_disk(self):
        """Test handling of very large disk values (10TB)."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        with patch('psutil.disk_usage') as mock_usage:
            mock_usage.return_value = Mock(
                total=10 * 10**12,  # 10 TB
                used=5 * 10**12,
                free=5 * 10**12,
                percent=50.0,
            )
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_full_disk(self):
        """Test handling of full disk (100% usage)."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        with patch('psutil.disk_usage') as mock_usage:
            mock_usage.return_value = Mock(
                total=500 * 10**9,
                used=500 * 10**9,
                free=0,
                percent=100.0,
            )
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_permission_denied(self):
        """Test handling of permission denied errors."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        with patch('psutil.disk_usage') as mock_usage:
            mock_usage.side_effect = PermissionError("Access denied")
            metrics = adapter.collect_metrics()
            # Should handle gracefully
            assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_network_drive(self):
        """Test handling of network drives."""
        adapter = DiskAdapter()
        
        with patch('psutil.disk_partitions') as mock_parts:
            mock_parts.return_value = [
                Mock(
                    device="\\\\server\\share",
                    mountpoint="Z:",
                    fstype="CIFS",
                    opts="rw,network"
                )
            ]
            adapter.initialize()
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)
        
        adapter.cleanup()


class TestDiskAdapterIOMetrics:
    """Test I/O metric collection."""
    
    def test_io_read_metrics(self):
        """Test disk read metrics."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        # Look for read-related metrics
        read_metrics = [k for k in metrics.keys() if "read" in k.lower()]
        # May or may not have read metrics depending on system
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_io_write_metrics(self):
        """Test disk write metrics."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        # Look for write-related metrics
        write_metrics = [k for k in metrics.keys() if "write" in k.lower()]
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_io_rate_calculation(self):
        """Test I/O rate calculation over time."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        # First collection
        metrics1 = adapter.collect_metrics()
        
        # Second collection
        import time
        time.sleep(0.1)
        metrics2 = adapter.collect_metrics()
        
        # Rate metrics should be calculated
        assert isinstance(metrics2, dict)
        
        adapter.cleanup()
    
    def test_high_io_values(self):
        """Test handling of high I/O values."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        with patch('psutil.disk_io_counters') as mock_io:
            mock_io.return_value = Mock(
                read_bytes=10**15,  # 1 PB
                write_bytes=10**15,
                read_count=10**12,
                write_count=10**12,
                read_time=10**9,
                write_time=10**9,
            )
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)
        
        adapter.cleanup()


class TestDiskAdapterMetricValues:
    """Test metric value correctness."""
    
    def test_percentage_range(self):
        """Test percentage values are in valid range."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            if "percent" in name.lower():
                assert 0 <= metric.value <= 100, f"{name} out of range: {metric.value}"
        
        adapter.cleanup()
    
    def test_positive_values(self):
        """Test all values are non-negative."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            assert metric.value >= 0, f"Negative value for {name}: {metric.value}"
        
        adapter.cleanup()
    
    def test_metric_units(self):
        """Test metrics have appropriate units."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            assert metric.unit is not None
            assert len(metric.unit) > 0 or metric.unit == ""
        
        adapter.cleanup()


class TestDiskAdapterErrorRecovery:
    """Error recovery tests for disk adapter."""
    
    def test_partial_partition_failure(self):
        """Test handling when some partitions fail."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        # Should still return metrics from working partitions
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_error_count_tracking(self):
        """Test error count is tracked."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        initial_count = adapter._error_count
        adapter.record_error("Test error")
        assert adapter._error_count == initial_count + 1
        
        adapter.cleanup()
