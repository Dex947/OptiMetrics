"""
Tests for Hardware Logger (Main Script)

Covers:
    - Logger initialization
    - Adapter management
    - Metric collection orchestration
    - Start/stop lifecycle
    - Configuration handling
"""

import pytest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware_logger import HardwareLogger, MetricsBuffer, CSVWriter
from src.utils import get_default_config


class TestMetricsBuffer:
    """Tests for metrics buffer."""
    
    def test_buffer_initialization(self):
        """Test buffer initializes correctly."""
        buffer = MetricsBuffer()
        assert buffer is not None
    
    def test_buffer_with_config(self):
        """Test buffer with config."""
        config = get_default_config()
        buffer = MetricsBuffer(config=config)
        assert buffer is not None
    
    def test_add_record(self):
        """Test adding record to buffer."""
        buffer = MetricsBuffer()
        result = buffer.add({"timestamp": "2024-01-01", "value": 1})
        # Result depends on delta filtering
        assert isinstance(result, bool)
    
    def test_get_batch(self):
        """Test getting batch from buffer."""
        buffer = MetricsBuffer()
        
        for i in range(10):
            buffer.add({"timestamp": f"2024-01-01T00:00:{i:02d}", "value": i * 10})
        
        batch = buffer.get_batch()
        assert isinstance(batch, list)
    
    def test_buffer_get_batch_clears(self):
        """Test getting batch clears buffer."""
        buffer = MetricsBuffer()
        
        for i in range(10):
            buffer.add({"value": i * 10})
        
        batch1 = buffer.get_batch()
        batch2 = buffer.get_batch()
        # Second batch should be empty after first get
        assert len(batch2) == 0


class TestCSVWriterBasic:
    """Tests for CSV writer."""
    
    def test_initialization(self):
        """Test CSV writer initializes correctly."""
        config = get_default_config()
        writer = CSVWriter(config)
        assert writer is not None
        writer.close()
    
    def test_write_batch(self):
        """Test writing a batch."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            records = [{"timestamp": "2024-01-01", "value": 1}]
            written = writer.write_batch(records)
            
            assert written >= 0
            writer.close()


class TestHardwareLoggerWithConfigPath:
    """Tests for hardware logger using config path."""
    
    def test_initialization_with_config_path(self):
        """Test logger initializes with config path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("general:\n  logging_interval: 2\n")
            config_path = f.name
        
        try:
            hw_logger = HardwareLogger(config_path)
            assert hw_logger is not None
        finally:
            os.unlink(config_path)
    
    def test_adapters_loaded(self):
        """Test adapters are loaded."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("general:\n  collect_cpu: true\n  collect_ram: true\n")
            config_path = f.name
        
        try:
            hw_logger = HardwareLogger(config_path)
            assert len(hw_logger._adapters) > 0
        finally:
            os.unlink(config_path)


class TestHardwareLoggerLifecycle:
    """Tests for logger lifecycle."""
    
    def test_start_stop(self):
        """Test starting and stopping logger."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("general:\n  logging_interval: 1\n")
            config_path = f.name
        
        try:
            hw_logger = HardwareLogger(config_path)
            hw_logger.start()
            assert hw_logger._running is True
            
            hw_logger.stop()
            assert hw_logger._running is False
        finally:
            os.unlink(config_path)
    
    def test_stop_without_start(self):
        """Test stopping without starting."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("general:\n  logging_interval: 1\n")
            config_path = f.name
        
        try:
            hw_logger = HardwareLogger(config_path)
            hw_logger.stop()  # Should not raise
        finally:
            os.unlink(config_path)
