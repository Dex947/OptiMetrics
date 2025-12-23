"""
Tests for Utility Functions

Covers:
    - Configuration loading/saving
    - Hardware ID generation
    - Session state persistence
    - Logging setup
"""

import pytest
import tempfile
import os
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    load_config,
    save_config,
    get_default_config,
    generate_hardware_id,
    SessionState,
    save_session_state,
    load_session_state,
    setup_logging,
)


class TestConfigurationLoading:
    """Tests for configuration loading."""
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        config = get_default_config()
        assert "general" in config
        assert "logging" in config
        assert "cloud" in config
    
    def test_load_missing_config(self):
        """Test loading missing config file returns defaults."""
        config = load_config("/nonexistent/path/config.yaml")
        assert "general" in config
        assert "logging" in config
    
    def test_load_valid_config(self):
        """Test loading valid config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("general:\n  logging_interval: 5\n")
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert "general" in config
        finally:
            os.unlink(temp_path)
    
    def test_load_invalid_yaml(self):
        """Test loading invalid YAML returns defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert "general" in config
        finally:
            os.unlink(temp_path)
    
    def test_load_empty_config(self):
        """Test loading empty config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            assert "general" in config
        finally:
            os.unlink(temp_path)


class TestConfigurationSaving:
    """Tests for configuration saving."""
    
    def test_save_config(self):
        """Test saving configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.yaml")
            config = {"general": {"test": True}}
            
            result = save_config(config, config_path)
            assert result is True
            assert os.path.exists(config_path)
    
    def test_save_config_invalid_path(self):
        """Test saving to invalid path."""
        result = save_config({}, "Z:\\nonexistent\\path\\config.yaml")
        assert result is False
    
    def test_save_and_load_roundtrip(self):
        """Test save and load roundtrip."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.yaml")
            original = {"general": {"logging_interval": 5}}
            
            save_config(original, config_path)
            loaded = load_config(config_path)
            
            assert loaded["general"]["logging_interval"] == 5


class TestHardwareIDGeneration:
    """Tests for hardware ID generation."""
    
    def test_generate_hardware_id(self):
        """Test hardware ID generation."""
        hw_id = generate_hardware_id(
            cpu_model="Intel Core i7",
            gpu_names=["NVIDIA RTX 3080"],
            config=get_default_config()
        )
        assert len(hw_id) == 32
        assert hw_id.isalnum()
    
    def test_hardware_id_consistency(self):
        """Test hardware ID is consistent for same inputs."""
        inputs = {
            "cpu_model": "Intel Core i7",
            "gpu_names": ["NVIDIA RTX 3080"],
            "config": get_default_config()
        }
        
        id1 = generate_hardware_id(**inputs)
        id2 = generate_hardware_id(**inputs)
        id3 = generate_hardware_id(**inputs)
        
        assert id1 == id2 == id3
    
    def test_hardware_id_different_inputs(self):
        """Test different inputs produce different IDs."""
        config = get_default_config()
        
        id1 = generate_hardware_id("Intel i7", ["RTX 3080"], config)
        id2 = generate_hardware_id("AMD Ryzen", ["RTX 3080"], config)
        
        assert id1 != id2
    
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
    
    def test_hardware_id_special_characters(self):
        """Test hardware ID with special characters."""
        hw_id = generate_hardware_id(
            cpu_model="Intel(R) Core(TM) i7-12700K @ 3.60GHz",
            gpu_names=["NVIDIA GeForce RTX 3080 Ti (10GB)"],
            config=get_default_config()
        )
        assert len(hw_id) == 32


class TestSessionState:
    """Tests for session state persistence."""
    
    def test_session_state_creation(self):
        """Test creating session state."""
        state = SessionState(
            last_timestamp="2024-01-01T00:00:00",
            last_log_file="/path/to/log.csv",
            hardware_id="abc123",
            session_start="2024-01-01T00:00:00",
            metrics_count=1000,
        )
        assert state.hardware_id == "abc123"
        assert state.metrics_count == 1000
    
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
    
    def test_session_state_partial_data(self):
        """Test handling of partial session state data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"hardware_id": "abc123"}, f)
            temp_path = f.name
        
        try:
            loaded = load_session_state(temp_path)
            # Should handle missing fields
        finally:
            os.unlink(temp_path)


class TestLoggingSetup:
    """Tests for logging setup."""
    
    def test_setup_logging(self):
        """Test logging setup."""
        config = get_default_config()
        logger = setup_logging(config)
        assert logger is not None
    
    def test_setup_logging_with_file(self):
        """Test logging setup with file output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = get_default_config()
            config["logging"]["log_directory"] = temp_dir
            
            logger = setup_logging(config)
            assert logger is not None
    
    def test_setup_logging_verbose(self):
        """Test verbose logging setup."""
        config = get_default_config()
        config["debug"] = {"verbose": True}
        
        logger = setup_logging(config)
        assert logger is not None


class TestDefaultConfig:
    """Tests for default configuration structure."""
    
    def test_general_section(self):
        """Test general section exists."""
        config = get_default_config()
        assert "general" in config
        assert "logging_interval" in config["general"]
    
    def test_logging_section(self):
        """Test logging section exists."""
        config = get_default_config()
        assert "logging" in config
        assert "log_directory" in config["logging"]
    
    def test_cloud_section(self):
        """Test cloud section exists."""
        config = get_default_config()
        assert "cloud" in config
        assert "enabled" in config["cloud"]
    
    def test_hardware_id_section(self):
        """Test hardware_id section exists."""
        config = get_default_config()
        assert "hardware_id" in config
    
    def test_session_classification_section(self):
        """Test session_classification section exists."""
        config = get_default_config()
        assert "session_classification" in config
