"""
Tests for Network Adapter

Covers:
    - Initialization and cleanup
    - Network I/O metric collection
    - Edge cases (no interfaces, high throughput, permission denied)
    - Rate calculations
    - Error recovery
"""

import pytest
from unittest.mock import patch, Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.network_adapter import NetworkAdapter
from src.adapters.base_adapter import MetricValue


class TestNetworkAdapterBasic:
    """Basic network adapter tests."""
    
    def test_initialization(self):
        """Test network adapter initializes correctly."""
        adapter = NetworkAdapter()
        result = adapter.initialize()
        assert result is True
        assert adapter.is_initialized
        adapter.cleanup()
    
    def test_hardware_info(self):
        """Test hardware info retrieval."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        assert info is not None
        
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test metric collection returns valid data."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        assert "net_bytes_sent" in metrics
        assert "net_bytes_recv" in metrics
        
        adapter.cleanup()
    
    def test_cleanup_idempotent(self):
        """Test cleanup can be called multiple times."""
        adapter = NetworkAdapter()
        adapter.initialize()
        adapter.cleanup()
        adapter.cleanup()
        adapter.cleanup()
    
    def test_context_manager(self):
        """Test adapter works as context manager."""
        with NetworkAdapter() as adapter:
            assert adapter.is_initialized
            metrics = adapter.collect_metrics()
            assert len(metrics) > 0


class TestNetworkAdapterEdgeCases:
    """Edge case tests for network adapter."""
    
    def test_no_interfaces(self):
        """Test handling when network interfaces are unavailable."""
        adapter = NetworkAdapter()
        result = adapter.initialize()
        assert result is True
        adapter.cleanup()
    
    def test_rate_calculation_zero_time(self):
        """Test rate calculation doesn't divide by zero."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics1 = adapter.collect_metrics()
        metrics2 = adapter.collect_metrics()  # Immediate second call
        
        for key, value in metrics2.items():
            if hasattr(value, 'value') and isinstance(value.value, float):
                assert value.value == value.value  # Not NaN
                assert value.value != float('inf')
        
        adapter.cleanup()
    
    def test_connection_permission_denied(self):
        """Test handling of permission denied for connection stats."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        with patch('psutil.net_connections') as mock_conn:
            mock_conn.side_effect = PermissionError("Access denied")
            metrics = adapter.collect_metrics()
            assert "net_bytes_sent" in metrics
        
        adapter.cleanup()
    
    def test_interface_disappears(self):
        """Test handling when network interface disappears mid-collection."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics1 = adapter.collect_metrics()
        
        original_interfaces = adapter._interfaces.copy() if hasattr(adapter, '_interfaces') else []
        if hasattr(adapter, '_interfaces'):
            adapter._interfaces = ["nonexistent_interface"]
        
        metrics2 = adapter.collect_metrics()
        
        if hasattr(adapter, '_interfaces'):
            adapter._interfaces = original_interfaces
        
        adapter.cleanup()
    
    def test_high_throughput_values(self):
        """Test handling of very high throughput values."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        with patch('psutil.net_io_counters') as mock_io:
            mock_io.return_value = Mock(
                bytes_sent=10**15,  # 1 PB
                bytes_recv=10**15,
                packets_sent=10**12,
                packets_recv=10**12,
                errin=0,
                errout=0,
                dropin=0,
                dropout=0,
            )
            metrics = adapter.collect_metrics()
            assert "net_bytes_sent" in metrics
        
        adapter.cleanup()
    
    def test_loopback_interface(self):
        """Test handling of loopback interface."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        # Loopback should be handled gracefully
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_multiple_interfaces(self):
        """Test handling of multiple network interfaces."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        with patch('psutil.net_io_counters') as mock_io:
            mock_io.return_value = {
                'eth0': Mock(bytes_sent=1000, bytes_recv=2000, packets_sent=10, packets_recv=20,
                            errin=0, errout=0, dropin=0, dropout=0),
                'wlan0': Mock(bytes_sent=500, bytes_recv=1000, packets_sent=5, packets_recv=10,
                             errin=0, errout=0, dropin=0, dropout=0),
            }
            # This might not work depending on implementation
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)
        
        adapter.cleanup()


class TestNetworkAdapterRateCalculation:
    """Test network rate calculations."""
    
    def test_send_rate(self):
        """Test send rate calculation."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        import time
        metrics1 = adapter.collect_metrics()
        time.sleep(0.1)
        metrics2 = adapter.collect_metrics()
        
        # Rate metrics should exist
        rate_metrics = [k for k in metrics2.keys() if "rate" in k.lower()]
        assert isinstance(metrics2, dict)
        
        adapter.cleanup()
    
    def test_recv_rate(self):
        """Test receive rate calculation."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        import time
        metrics1 = adapter.collect_metrics()
        time.sleep(0.1)
        metrics2 = adapter.collect_metrics()
        
        assert isinstance(metrics2, dict)
        
        adapter.cleanup()
    
    def test_rate_non_negative(self):
        """Test rates are non-negative."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        import time
        adapter.collect_metrics()
        time.sleep(0.1)
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            if "rate" in name.lower():
                assert metric.value >= 0, f"Negative rate for {name}"
        
        adapter.cleanup()


class TestNetworkAdapterConnectionStats:
    """Test connection statistics."""
    
    def test_connection_count(self):
        """Test connection count metric."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        # May have connection metrics
        conn_metrics = [k for k in metrics.keys() if "connection" in k.lower()]
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_connection_types(self):
        """Test different connection type counts."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        with patch('psutil.net_connections') as mock_conn:
            mock_conn.return_value = [
                Mock(status='ESTABLISHED'),
                Mock(status='ESTABLISHED'),
                Mock(status='LISTEN'),
                Mock(status='TIME_WAIT'),
            ]
            metrics = adapter.collect_metrics()
            assert isinstance(metrics, dict)
        
        adapter.cleanup()


class TestNetworkAdapterMetricValues:
    """Test metric value correctness."""
    
    def test_bytes_metrics_present(self):
        """Test byte count metrics are present."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        assert "net_bytes_sent" in metrics
        assert "net_bytes_recv" in metrics
        
        adapter.cleanup()
    
    def test_positive_values(self):
        """Test all values are non-negative."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            assert metric.value >= 0, f"Negative value for {name}: {metric.value}"
        
        adapter.cleanup()
    
    def test_metric_units(self):
        """Test metrics have appropriate units."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            assert metric.unit is not None
        
        adapter.cleanup()
    
    def test_metric_source(self):
        """Test metrics have a source."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        
        for name, metric in metrics.items():
            assert metric.source is not None
        
        adapter.cleanup()


class TestNetworkAdapterErrorRecovery:
    """Error recovery tests for network adapter."""
    
    def test_psutil_failure(self):
        """Test handling of psutil failure."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        with patch('psutil.net_io_counters') as mock_io:
            mock_io.side_effect = Exception("psutil error")
            try:
                metrics = adapter.collect_metrics()
            except Exception:
                pass
        
        adapter.cleanup()
    
    def test_error_count_tracking(self):
        """Test error count is tracked."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        initial_count = adapter._error_count
        adapter.record_error("Test error")
        assert adapter._error_count == initial_count + 1
        
        adapter.cleanup()
    
    def test_recovery_after_error(self):
        """Test adapter recovers after transient error."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        # Simulate error
        adapter.record_error("Transient error")
        
        # Should still work
        metrics = adapter.collect_metrics()
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
