"""
Pytest Configuration and Fixtures

Provides shared fixtures and configuration for all tests.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import get_default_config


@pytest.fixture
def default_config():
    """Provide default configuration."""
    return get_default_config()


@pytest.fixture
def temp_log_dir():
    """Provide temporary log directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def config_with_temp_dir(temp_log_dir):
    """Provide config with temporary log directory."""
    config = get_default_config()
    config["logging"]["log_directory"] = temp_log_dir
    return config


@pytest.fixture
def temp_config_file():
    """Provide temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("general:\n  logging_interval: 1\n")
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_json_file():
    """Provide temporary JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_metrics():
    """Provide sample metrics for testing."""
    return {
        "timestamp": "2024-01-01T00:00:00",
        "hardware_id": "test_hardware_id",
        "total_utilization": 50.0,
        "gpu_utilization": 30.0,
        "ram_percent": 60.0,
        "disk_percent": 45.0,
        "net_bytes_sent": 1000000,
        "net_bytes_recv": 2000000,
    }


@pytest.fixture
def gaming_metrics():
    """Provide gaming-like metrics."""
    return {
        "gpu_utilization": 85.0,
        "cpu_utilization": 45.0,
        "vram_percent": 70.0,
        "ram_percent": 50.0,
    }


@pytest.fixture
def idle_metrics():
    """Provide idle-like metrics."""
    return {
        "gpu_utilization": 2.0,
        "cpu_utilization": 3.0,
        "ram_percent": 30.0,
    }


@pytest.fixture
def ai_training_metrics():
    """Provide AI training-like metrics."""
    return {
        "gpu_utilization": 95.0,
        "cpu_utilization": 30.0,
        "vram_percent": 90.0,
        "compute_processes": 2,
    }
