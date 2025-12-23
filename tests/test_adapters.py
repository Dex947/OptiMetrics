"""
Unit tests for OptiMetrics hardware adapters.

Run with: pytest tests/ -v
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.adapters import (
    CPUAdapter,
    NvidiaGPUAdapter,
    MemoryAdapter,
    DiskAdapter,
    NetworkAdapter,
)
from src.adapters.base_adapter import MetricValue, HardwareInfo


class TestCPUAdapter:
    """Tests for CPU adapter."""
    
    def test_initialization(self):
        """Test CPU adapter initializes successfully."""
        adapter = CPUAdapter()
        assert adapter.initialize() is True
        assert adapter.is_initialized is True
        adapter.cleanup()
    
    def test_hardware_info(self):
        """Test CPU hardware info retrieval."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        info = adapter.get_hardware_info()
        assert info is not None
        assert isinstance(info, HardwareInfo)
        assert info.vendor != ""
        assert info.model != ""
        
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test CPU metrics collection."""
        adapter = CPUAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert len(metrics) > 0
        assert "total_utilization" in metrics
        
        util = metrics["total_utilization"]
        assert isinstance(util, MetricValue)
        assert 0 <= util.value <= 100
        
        adapter.cleanup()


class TestMemoryAdapter:
    """Tests for Memory adapter."""
    
    def test_initialization(self):
        """Test Memory adapter initializes successfully."""
        adapter = MemoryAdapter()
        assert adapter.initialize() is True
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test memory metrics collection."""
        adapter = MemoryAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert "ram_percent" in metrics
        assert "ram_used_mb" in metrics
        assert "swap_percent" in metrics
        
        ram_pct = metrics["ram_percent"]
        assert 0 <= ram_pct.value <= 100
        
        adapter.cleanup()


class TestDiskAdapter:
    """Tests for Disk adapter."""
    
    def test_initialization(self):
        """Test Disk adapter initializes successfully."""
        adapter = DiskAdapter()
        assert adapter.initialize() is True
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test disk metrics collection."""
        adapter = DiskAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert len(metrics) > 0
        
        # Should have at least one disk usage metric
        disk_metrics = [k for k in metrics.keys() if k.startswith("disk_")]
        assert len(disk_metrics) > 0
        
        adapter.cleanup()


class TestNetworkAdapter:
    """Tests for Network adapter."""
    
    def test_initialization(self):
        """Test Network adapter initializes successfully."""
        adapter = NetworkAdapter()
        assert adapter.initialize() is True
        adapter.cleanup()
    
    def test_collect_metrics(self):
        """Test network metrics collection."""
        adapter = NetworkAdapter()
        adapter.initialize()
        
        metrics = adapter.collect_metrics()
        assert "net_bytes_sent" in metrics
        assert "net_bytes_recv" in metrics
        
        adapter.cleanup()


class TestNvidiaAdapter:
    """Tests for NVIDIA GPU adapter."""
    
    def test_initialization(self):
        """Test NVIDIA adapter initialization (may fail if no GPU)."""
        adapter = NvidiaGPUAdapter()
        # This may return False if no NVIDIA GPU is present
        result = adapter.initialize()
        # Just verify it doesn't crash
        assert result in [True, False]
        adapter.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
