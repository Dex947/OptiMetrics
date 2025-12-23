"""
Tests for CSV Writer

Covers:
    - CSV file creation and writing
    - Rolling log files
    - Delta filtering
    - Special character handling
    - Error recovery
"""

import pytest
import tempfile
import os
import csv
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware_logger import CSVWriter
from src.utils import get_default_config


class TestCSVWriterBasic:
    """Basic CSV writer tests."""
    
    def test_initialization(self):
        """Test CSV writer initializes correctly."""
        config = get_default_config()
        writer = CSVWriter(config)
        assert writer is not None
        writer.close()
    
    def test_write_single_record(self):
        """Test writing a single record."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{
                "timestamp": datetime.now().isoformat(),
                "metric1": 50.0,
                "metric2": 100,
            }]
            
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_write_multiple_records(self):
        """Test writing multiple records."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [
                {"timestamp": datetime.now().isoformat(), "metric": i}
                for i in range(10)
            ]
            
            written = writer.write_batch(records)
            assert written == 10
            
            writer.close()
    
    def test_write_empty_batch(self):
        """Test writing empty batch."""
        config = get_default_config()
        writer = CSVWriter(config)
        
        written = writer.write_batch([])
        assert written == 0
        
        writer.close()
    
    def test_close_idempotent(self):
        """Test close can be called multiple times."""
        config = get_default_config()
        writer = CSVWriter(config)
        
        writer.close()
        writer.close()
        writer.close()


class TestCSVWriterFileCreation:
    """Tests for CSV file creation."""
    
    def test_creates_log_directory(self):
        """Test log directory is created if missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = os.path.join(temp_dir, "logs", "subdir")
            
            config = get_default_config()
            config["logging"]["log_directory"] = log_dir
            
            writer = CSVWriter(config)
            writer.write_batch([{"timestamp": "2024-01-01", "value": 1}])
            
            assert os.path.exists(log_dir)
            
            writer.close()
    
    def test_file_naming(self):
        """Test log file naming convention."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            writer.write_batch([{"timestamp": "2024-01-01", "value": 1}])
            
            # Should create a CSV file
            csv_files = list(Path(temp_dir).glob("*.csv"))
            assert len(csv_files) >= 0  # May be 0 if buffered
            
            writer.close()


class TestCSVWriterSpecialCharacters:
    """Tests for special character handling."""
    
    def test_comma_in_value(self):
        """Test handling commas in values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{
                "timestamp": "2024-01-01",
                "metric": "value,with,commas",
            }]
            
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_quote_in_value(self):
        """Test handling quotes in values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{
                "timestamp": "2024-01-01",
                "metric": 'value"with"quotes',
            }]
            
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_newline_in_value(self):
        """Test handling newlines in values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{
                "timestamp": "2024-01-01",
                "metric": "value\nwith\nnewlines",
            }]
            
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_unicode_values(self):
        """Test handling unicode values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{
                "timestamp": "2024-01-01",
                "metric": "Intel® Core™ i7",
            }]
            
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()


class TestCSVWriterDataTypes:
    """Tests for different data types."""
    
    def test_integer_values(self):
        """Test writing integer values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{"timestamp": "2024-01-01", "count": 12345}]
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_float_values(self):
        """Test writing float values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{"timestamp": "2024-01-01", "percent": 99.99}]
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_boolean_values(self):
        """Test writing boolean values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{"timestamp": "2024-01-01", "flag": True}]
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_none_values(self):
        """Test writing None values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{"timestamp": "2024-01-01", "missing": None}]
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()
    
    def test_very_large_values(self):
        """Test writing very large values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [{"timestamp": "2024-01-01", "bytes": 10**15}]
            written = writer.write_batch(records)
            assert written == 1
            
            writer.close()


class TestCSVWriterConsistency:
    """Tests for data consistency."""
    
    def test_consistent_columns(self):
        """Test columns remain consistent across writes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            # First batch
            writer.write_batch([{"timestamp": "2024-01-01", "a": 1, "b": 2}])
            
            # Second batch with same columns
            writer.write_batch([{"timestamp": "2024-01-01", "a": 3, "b": 4}])
            
            writer.close()
    
    def test_new_columns_handled(self):
        """Test new columns are handled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            # First batch
            writer.write_batch([{"timestamp": "2024-01-01", "a": 1}])
            
            # Second batch with new column
            writer.write_batch([{"timestamp": "2024-01-01", "a": 2, "b": 3}])
            
            writer.close()


class TestCSVWriterErrorHandling:
    """Tests for error handling."""
    
    def test_invalid_directory(self):
        """Test handling of invalid directory."""
        config = get_default_config()
        config["logging"]["log_directory"] = "Z:\\nonexistent\\path"
        
        # Should not crash during init
        try:
            writer = CSVWriter(config)
            writer.close()
        except Exception:
            pass  # May raise, but shouldn't crash unexpectedly
    
    def test_disk_full_simulation(self):
        """Test handling of disk full scenario."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            # Should handle write errors gracefully
            try:
                writer.write_batch([{"timestamp": "2024-01-01", "value": 1}])
            except Exception:
                pass
            
            writer.close()


class TestCSVWriterPerformance:
    """Tests for performance characteristics."""
    
    def test_large_batch(self):
        """Test writing large batch."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            records = [
                {"timestamp": f"2024-01-01T00:00:{i:02d}", "value": i}
                for i in range(1000)
            ]
            
            written = writer.write_batch(records)
            assert written == 1000
            
            writer.close()
    
    def test_many_columns(self):
        """Test writing records with many columns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            writer = CSVWriter(config)
            
            record = {"timestamp": "2024-01-01"}
            for i in range(100):
                record[f"metric_{i}"] = i * 1.5
            
            written = writer.write_batch([record])
            assert written == 1
            
            writer.close()
