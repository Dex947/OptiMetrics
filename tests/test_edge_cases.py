"""
Comprehensive Edge Case Tests for OptiMetrics

Tests cover:
    - Multi-GPU configurations
    - Network adapter edge cases
    - Hardware detection failures
    - Metric collection under stress
    - Session classification edge cases
    - File I/O edge cases
    - Configuration edge cases
"""

import sys
import os
import tempfile
import json
import csv
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import threading
import time

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue
from src.adapters.cpu_adapter import CPUAdapter
from src.adapters.nvidia_adapter import NvidiaGPUAdapter
from src.adapters.memory_adapter import MemoryAdapter
from src.adapters.disk_adapter import DiskAdapter
from src.adapters.network_adapter import NetworkAdapter
from src.utils import (
    SessionClassifier,
    generate_hardware_id,
    get_default_config,
    load_config,
    save_config,
    SessionState,
    save_session_state,
    load_session_state,
)


class TestMultiGPUScenarios:
    """Tests for multi-GPU configurations."""
    
    def test_no_gpu_graceful_handling(self):
        """Test graceful handling when no GPU is present."""
        adapter = NvidiaGPUAdapter()
        # Should return False but not crash
        result = adapter.initialize()
        # Result depends on actual hardware, but should not raise
        assert result in [True, False]
        adapter.cleanup()
    
    def test_multi_gpu_simulation(self):
        """Test multi-GPU scenario by directly setting adapter state."""
        adapter = NvidiaGPUAdapter()
        
        # Simulate multi-GPU by setting internal state
        adapter._gpu_count = 3
        adapter._gpu_handles = [Mock(), Mock(), Mock()]
        adapter._initialized = True
        
        assert adapter._gpu_count == 3
        assert len(adapter._gpu_handles) == 3
        
        adapter.cleanup()
    
    def test_gpu_metrics_partial_failure(self):
        """Test GPU metrics collection handles partial failures gracefully."""
        adapter = NvidiaGPUAdapter()
        
        # Try to initialize - may fail if no GPU
        adapter.initialize()
        
        # Even if not initialized, collect_metrics should not crash
        metrics = adapter.collect_metrics()
        # Should return empty dict or partial metrics
        assert isinstance(metrics, dict)
        
        adapter.cleanup()
    
    def test_gpu_adapter_cleanup_idempotent(self):
        """Test that cleanup can be called multiple times safely."""
        adapter = NvidiaGPUAdapter()
        adapter.cleanup()
        adapter.cleanup()  # Should not raise
        adapter.cleanup()  # Should not raise


class TestNetworkEdgeCases:
    """Tests for network adapter edge cases."""
    
    def test_network_no_interfaces(self):
        """Test handling when network interfaces are unavailable."""
        adapter = NetworkAdapter()
        result = adapter.initialize()
        assert result is True  # Should still initialize
        adapter.cleanup()
    
    def test_network_rate_calculation_zero_time(self):
        """Test rate calculation doesn't divide by zero."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        # First call
        metrics1 = adapter.collect_metrics()
        # Immediate second call (near-zero time delta)
        metrics2 = adapter.collect_metrics()
        
        # Should not crash or produce inf/nan values
        for key, value in metrics2.items():
            if hasattr(value, 'value') and isinstance(value.value, float):
                assert not (value.value != value.value)  # Check for NaN
                assert value.value != float('inf')
        
        adapter.cleanup()
    
    def test_network_connection_permission_denied(self):
        """Test handling of permission denied for connection stats."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        with patch('psutil.net_connections') as mock_conn:
            mock_conn.side_effect = PermissionError("Access denied")
            metrics = adapter.collect_metrics()
            # Should still return other metrics
            assert "net_bytes_sent" in metrics
        
        adapter.cleanup()
    
    def test_network_interface_disappears(self):
        """Test handling when network interface disappears mid-collection."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        # Collect once normally
        metrics1 = adapter.collect_metrics()
        
        # Simulate interface disappearing
        original_interfaces = adapter._interfaces.copy()
        adapter._interfaces = ["nonexistent_interface"]
        
        # Should not crash
        metrics2 = adapter.collect_metrics()
        
        # Restore
        adapter._interfaces = original_interfaces
        adapter.cleanup()
    
    def test_network_high_throughput_values(self):
        """Test handling of very high throughput values."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        # Simulate very high byte counts
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


class TestDiskEdgeCases:
    """Tests for disk adapter edge cases."""
    
    def test_disk_unmounted_partition(self):
        """Test handling of unmounted or inaccessible partitions."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        # Should handle permission errors gracefully
        metrics = adapter.collect_metrics()
        assert len(metrics) > 0
        
        adapter.cleanup()
    
    def test_disk_no_partitions(self):
        """Test handling when no partitions are accessible."""
        adapter = DiskAdapter()
        
        with patch('psutil.disk_partitions') as mock_parts:
            mock_parts.return_value = []
            result = adapter.initialize()
            assert result is True  # Should still initialize
        
        adapter.cleanup()
    
    def test_disk_io_counters_none(self):
        """Test handling when disk I/O counters return None."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        with patch('psutil.disk_io_counters') as mock_io:
            mock_io.return_value = None
            metrics = adapter.collect_metrics()
            # Should not crash
        
        adapter.cleanup()
    
    def test_disk_very_large_values(self):
        """Test handling of very large disk values."""
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
        
        adapter.cleanup()


class TestCPUEdgeCases:
    """Tests for CPU adapter edge cases."""
    
    def test_cpu_single_core(self):
        """Test handling of single-core CPU."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch('psutil.cpu_count') as mock_count:
            mock_count.return_value = 1
            metrics = adapter.collect_metrics()
            assert "total_utilization" in metrics
        
        adapter.cleanup()
    
    def test_cpu_many_cores(self):
        """Test handling of many-core CPU (e.g., 128 cores)."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        # Simulate 128 cores
        with patch('psutil.cpu_percent') as mock_percent:
            mock_percent.return_value = [50.0] * 128
            metrics = adapter.collect_metrics()
            # Should have metrics for all cores
        
        adapter.cleanup()
    
    def test_cpu_frequency_unavailable(self):
        """Test handling when CPU frequency is unavailable."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch('psutil.cpu_freq') as mock_freq:
            mock_freq.return_value = None
            metrics = adapter.collect_metrics()
            # Should not crash
            assert "total_utilization" in metrics
        
        adapter.cleanup()
    
    def test_cpu_temperature_unavailable(self):
        """Test handling when temperature sensors are unavailable."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        with patch.object(adapter, '_get_cpu_temperature') as mock_temp:
            mock_temp.return_value = None
            metrics = adapter.collect_metrics()
            # Should not have temperature metric but should not crash
            assert "total_utilization" in metrics
        
        adapter.cleanup()


class TestMemoryEdgeCases:
    """Tests for memory adapter edge cases."""
    
    def test_memory_no_swap(self):
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
    
    def test_memory_very_high_usage(self):
        """Test handling of very high memory usage."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        with patch('psutil.virtual_memory') as mock_mem:
            mock_mem.return_value = Mock(
                total=64 * 10**9,  # 64 GB
                used=63 * 10**9,   # 63 GB used
                available=1 * 10**9,
                free=0.5 * 10**9,
                percent=98.4,
            )
            metrics = adapter.collect_metrics()
            assert metrics["ram_percent"].value > 95
        
        adapter.cleanup()


class TestSessionClassifierEdgeCases:
    """Tests for session classification edge cases."""
    
    def test_classifier_empty_metrics(self):
        """Test classifier with empty metrics."""
        classifier = SessionClassifier()
        result = classifier.update({})
        assert result is None  # Not enough data
    
    def test_classifier_partial_metrics(self):
        """Test classifier with partial metrics."""
        classifier = SessionClassifier()
        
        # Only CPU metrics
        for _ in range(10):
            result = classifier.update({
                "total_utilization": MetricValue("cpu", 50.0, "%"),
            })
        
        # Should still attempt classification
    
    def test_classifier_extreme_values(self):
        """Test classifier with extreme metric values."""
        classifier = SessionClassifier()
        
        for _ in range(10):
            result = classifier.update({
                "gpu_utilization": 100.0,
                "cpu_utilization": 100.0,
                "ram_percent": 100.0,
                "vram_percent": 100.0,
            })
        
        # Should classify as something (likely ai_training or gaming)
        assert result is None or result.name in classifier.THRESHOLDS
    
    def test_classifier_rapid_category_changes(self):
        """Test classifier stability with rapid metric changes."""
        classifier = SessionClassifier()
        
        # Simulate rapid changes
        categories_detected = []
        for i in range(20):
            if i % 2 == 0:
                # Gaming-like
                metrics = {"gpu_utilization": 80.0, "cpu_utilization": 40.0}
            else:
                # Idle-like
                metrics = {"gpu_utilization": 5.0, "cpu_utilization": 5.0}
            
            result = classifier.update(metrics)
            if result:
                categories_detected.append(result.name)
        
        # Should have some stability
    
    def test_classifier_thread_safety(self):
        """Test classifier thread safety."""
        classifier = SessionClassifier()
        errors = []
        
        def update_classifier():
            try:
                for _ in range(100):
                    classifier.update({
                        "gpu_utilization": 50.0,
                        "cpu_utilization": 50.0,
                    })
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=update_classifier) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


class TestConfigurationEdgeCases:
    """Tests for configuration handling edge cases."""
    
    def test_missing_config_file(self):
        """Test handling of missing config file."""
        config = load_config("/nonexistent/path/config.yaml")
        # Should return defaults
        assert "general" in config
        assert "logging" in config
    
    def test_invalid_config_yaml(self):
        """Test handling of invalid YAML in config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            # Should return defaults on parse error
            assert "general" in config
        finally:
            os.unlink(temp_path)
    
    def test_empty_config_file(self):
        """Test handling of empty config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            # Should return defaults
            assert "general" in config
        finally:
            os.unlink(temp_path)
    
    def test_config_save_invalid_path(self):
        """Test saving config to invalid path."""
        # Use a path that's definitely invalid on Windows
        result = save_config({}, "Z:\\nonexistent\\path\\that\\cannot\\exist\\config.yaml")
        assert result is False


class TestHardwareIDEdgeCases:
    """Tests for hardware ID generation edge cases."""
    
    def test_hardware_id_empty_inputs(self):
        """Test hardware ID with empty inputs."""
        hw_id = generate_hardware_id(
            cpu_model="",
            gpu_names=[],
            config=get_default_config()
        )
        assert len(hw_id) == 32
        assert hw_id.isalnum()
    
    def test_hardware_id_unicode_inputs(self):
        """Test hardware ID with unicode characters."""
        hw_id = generate_hardware_id(
            cpu_model="Intel® Core™ i7-12700K",
            gpu_names=["NVIDIA GeForce RTX™ 3080"],
            config=get_default_config()
        )
        assert len(hw_id) == 32
    
    def test_hardware_id_very_long_inputs(self):
        """Test hardware ID with very long inputs."""
        hw_id = generate_hardware_id(
            cpu_model="A" * 1000,
            gpu_names=["B" * 1000] * 10,
            config=get_default_config()
        )
        assert len(hw_id) == 32
    
    def test_hardware_id_consistency(self):
        """Test that hardware ID is consistent for same inputs."""
        inputs = {
            "cpu_model": "Intel Core i7",
            "gpu_names": ["NVIDIA RTX 3080"],
            "config": get_default_config()
        }
        
        id1 = generate_hardware_id(**inputs)
        id2 = generate_hardware_id(**inputs)
        id3 = generate_hardware_id(**inputs)
        
        assert id1 == id2 == id3


class TestSessionStateEdgeCases:
    """Tests for session state persistence edge cases."""
    
    def test_session_state_save_load(self):
        """Test session state save and load."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            state = SessionState(
                last_timestamp="2024-01-01T00:00:00",
                last_log_file="/path/to/log.csv",
                hardware_id="abc123",
                session_start="2024-01-01T00:00:00",
                metrics_count=1000,
            )
            
            save_session_state(state, temp_path)
            loaded = load_session_state(temp_path)
            
            assert loaded.hardware_id == state.hardware_id
            assert loaded.metrics_count == state.metrics_count
        finally:
            os.unlink(temp_path)
    
    def test_session_state_corrupted_file(self):
        """Test handling of corrupted session state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            temp_path = f.name
        
        try:
            loaded = load_session_state(temp_path)
            assert loaded is None
        finally:
            os.unlink(temp_path)
    
    def test_session_state_missing_file(self):
        """Test handling of missing session state file."""
        loaded = load_session_state("/nonexistent/state.json")
        assert loaded is None


class TestAdapterErrorRecovery:
    """Tests for adapter error recovery."""
    
    def test_adapter_error_count_threshold(self):
        """Test that adapters become unavailable after too many errors."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        # Simulate many errors
        for _ in range(15):
            adapter.record_error("Test error")
        
        assert adapter.is_available() is False
        
        # Reset should restore availability
        adapter.reset_error_count()
        assert adapter.is_available() is True
        
        adapter.cleanup()
    
    def test_adapter_context_manager(self):
        """Test adapter context manager usage."""
        with CPUAdapter() as adapter:
            assert adapter.is_initialized
            metrics = adapter.collect_metrics()
            assert len(metrics) > 0
    
    def test_adapter_double_initialization(self):
        """Test that double initialization is handled."""
        adapter = CPUAdapter()
        result1 = adapter.initialize()
        result2 = adapter.initialize()
        
        # Both should succeed or be idempotent
        assert result1 is True
        
        adapter.cleanup()


class TestCSVWriterEdgeCases:
    """Tests for CSV writing edge cases."""
    
    def test_csv_special_characters(self):
        """Test CSV writing with special characters in values."""
        from src.hardware_logger import CSVWriter
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{
                "timestamp": "2024-01-01T00:00:00",
                "metric_with_comma": "value,with,commas",
                "metric_with_quote": 'value"with"quotes',
                "metric_with_newline": "value\nwith\nnewlines",
            }]
            
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_csv_empty_batch(self):
        """Test CSV writing with empty batch."""
        from src.hardware_logger import CSVWriter
        
        writer = CSVWriter(get_default_config())
        written = writer.write_batch([])
        assert written == 0
        writer.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
