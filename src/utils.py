"""
OptiMetrics Utility Functions

This module provides helper functions for:
    - Hardware detection and identification
    - Cryptographic hardware ID generation
    - Session/workload classification
    - Cloud upload (Google Drive integration)
    - Configuration management
    - Logging utilities
"""

import os
import sys
import json
import hashlib
import logging
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque
import threading

import yaml

# Conditional imports for cloud storage
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

# Conditional imports for encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# Configure module logger
logger = logging.getLogger("optimetrics")


# =============================================================================
# Configuration Management
# =============================================================================

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, uses default location.
    
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        # Default config location
        project_root = Path(__file__).parent.parent
        config_path = project_root / "configs" / "config.yaml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}. Using defaults.")
        return get_default_config()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config or get_default_config()
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Return default configuration values."""
    return {
        "general": {
            "logging_interval": 1,
            "collect_cpu": True,
            "collect_gpu": True,
            "collect_ram": True,
            "collect_disk": True,
            "collect_network": True,
            "collect_power": True,
            "enable_session_classification": True,
            "auto_start": False,
        },
        "logging": {
            "log_directory": "logs",
            "rolling_logs": True,
            "max_file_size_mb": 50,
            "max_files_per_day": 10,
            "enable_delta_filtering": True,
            "delta_threshold_percent": 2.0,
            "compress_old_logs": True,
            "compress_after_days": 1,
        },
        "hardware_id": {
            "use_cryptographic_id": True,
            "hash_algorithm": "sha256",
            "include_cpu": True,
            "include_gpu": True,
            "include_motherboard": True,
            "include_ram": False,
        },
        "cloud": {
            "enabled": False,
            "provider": "gdrive",
            "upload_interval_minutes": 60,
            "encrypt_before_upload": True,
        },
        "session_classification": {
            "update_interval": 30,
            "confidence_threshold": 0.6,
        },
        "privacy": {
            "collect_process_names": False,
            "collect_window_titles": False,
            "collect_user_names": False,
            "collect_file_paths": False,
            "collect_network_addresses": False,
            "anonymize_hardware": True,
        },
        "debug": {
            "verbose": False,
            "log_level": "INFO",
        },
    }


def save_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """
    Save configuration to YAML file.
    
    Args:
        config: Configuration dictionary
        config_path: Path to save config file
    
    Returns:
        True if successful, False otherwise
    """
    if config_path is None:
        project_root = Path(__file__).parent.parent
        config_path = project_root / "configs" / "config.yaml"
    
    config_path = Path(config_path)
    
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False


# =============================================================================
# Hardware Detection and Identification
# =============================================================================

@dataclass
class SystemInfo:
    """Container for system hardware information."""
    cpu_model: str
    cpu_cores_physical: int
    cpu_cores_logical: int
    gpu_names: List[str]
    ram_total_gb: float
    storage_total_gb: float
    os_name: str
    os_version: str
    hostname_hash: str  # Hashed for privacy
    hardware_id: str


def get_system_info(config: Optional[Dict[str, Any]] = None) -> SystemInfo:
    """
    Detect and return system hardware information.
    
    Args:
        config: Optional configuration dictionary
    
    Returns:
        SystemInfo dataclass with hardware details
    """
    import psutil
    
    config = config or get_default_config()
    
    # CPU Info
    try:
        import cpuinfo
        cpu_data = cpuinfo.get_cpu_info()
        cpu_model = cpu_data.get("brand_raw", "Unknown CPU")
    except ImportError:
        cpu_model = platform.processor() or "Unknown CPU"
    
    cpu_cores_physical = psutil.cpu_count(logical=False) or 1
    cpu_cores_logical = psutil.cpu_count(logical=True) or 1
    
    # GPU Info
    gpu_names = []
    try:
        import pynvml
        pynvml.nvmlInit()
        gpu_count = pynvml.nvmlDeviceGetCount()
        for i in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            gpu_names.append(name)
        pynvml.nvmlShutdown()
    except Exception:
        gpu_names = ["No NVIDIA GPU detected"]
    
    # RAM Info
    ram_total_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    
    # Storage Info
    storage_total_gb = 0.0
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            storage_total_gb += usage.total / (1024**3)
        except (PermissionError, OSError):
            continue
    storage_total_gb = round(storage_total_gb, 2)
    
    # OS Info
    os_name = platform.system()
    os_version = platform.version()
    
    # Hashed hostname for privacy
    hostname = platform.node()
    hostname_hash = hashlib.sha256(hostname.encode()).hexdigest()[:16]
    
    # Generate hardware ID
    hardware_id = generate_hardware_id(
        cpu_model=cpu_model,
        gpu_names=gpu_names,
        config=config
    )
    
    return SystemInfo(
        cpu_model=cpu_model,
        cpu_cores_physical=cpu_cores_physical,
        cpu_cores_logical=cpu_cores_logical,
        gpu_names=gpu_names,
        ram_total_gb=ram_total_gb,
        storage_total_gb=storage_total_gb,
        os_name=os_name,
        os_version=os_version,
        hostname_hash=hostname_hash,
        hardware_id=hardware_id,
    )


def generate_hardware_id(
    cpu_model: str,
    gpu_names: List[str],
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a unique cryptographic hardware ID for anonymized tracking.
    
    The ID is a hash of hardware identifiers, making it:
    - Unique per machine
    - Consistent across reboots
    - Privacy-preserving (cannot be reversed to identify hardware)
    
    Args:
        cpu_model: CPU model string
        gpu_names: List of GPU names
        config: Configuration dictionary
    
    Returns:
        Hexadecimal hardware ID string
    """
    config = config or get_default_config()
    hw_config = config.get("hardware_id", {})
    
    components = []
    
    # CPU component
    if hw_config.get("include_cpu", True):
        components.append(f"CPU:{cpu_model}")
    
    # GPU component
    if hw_config.get("include_gpu", True):
        gpu_str = "|".join(sorted(gpu_names))
        components.append(f"GPU:{gpu_str}")
    
    # Motherboard/BIOS component (Windows only)
    if hw_config.get("include_motherboard", True) and sys.platform == "win32":
        try:
            import wmi
            c = wmi.WMI()
            for board in c.Win32_BaseBoard():
                components.append(f"MB:{board.Manufacturer}:{board.Product}")
                break
        except Exception:
            pass
    
    # Combine components
    combined = "||".join(components)
    
    # Hash with selected algorithm
    algorithm = hw_config.get("hash_algorithm", "sha256")
    if algorithm == "sha384":
        hasher = hashlib.sha384
    elif algorithm == "sha512":
        hasher = hashlib.sha512
    else:
        hasher = hashlib.sha256
    
    hardware_id = hasher(combined.encode("utf-8")).hexdigest()
    
    # Return truncated ID (first 32 chars for readability)
    return hardware_id[:32]


def get_cached_hardware_id(cache_file: Optional[str] = None) -> str:
    """
    Get hardware ID from cache or generate new one.
    
    Args:
        cache_file: Path to cache file
    
    Returns:
        Hardware ID string
    """
    if cache_file is None:
        project_root = Path(__file__).parent.parent
        cache_file = project_root / ".hardware_id_cache"
    
    cache_file = Path(cache_file)
    
    # Try to load from cache
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cached_id = f.read().strip()
                if len(cached_id) == 32:
                    return cached_id
        except Exception:
            pass
    
    # Generate new ID
    system_info = get_system_info()
    hardware_id = system_info.hardware_id
    
    # Cache it
    try:
        with open(cache_file, "w") as f:
            f.write(hardware_id)
    except Exception:
        pass
    
    return hardware_id


# =============================================================================
# Session Classification
# =============================================================================

@dataclass
class SessionCategory:
    """Represents a detected session/workload category."""
    name: str
    confidence: float
    detected_at: datetime
    metrics_snapshot: Dict[str, float]


class SessionClassifier:
    """
    Classifies system workload based on hardware metrics patterns.
    
    Categories:
        - gaming: High GPU usage, high frame rates, moderate CPU
        - ai_training: High GPU compute, high VRAM, sustained load
        - cad_3d_modeling: High GPU, moderate CPU, specific memory patterns
        - graphics_design: Moderate GPU, variable CPU, image processing patterns
        - video_editing: High disk I/O, encoder usage, moderate GPU
        - coding_development: Low GPU, moderate CPU, high RAM
        - document_editing: Low resource usage overall
        - web_browsing: Network activity, low-moderate CPU
        - idle: Very low resource usage
        - system_maintenance: High disk I/O, system processes
    
    Note: Classification is based ONLY on system metrics, not on process names
    or window titles, ensuring privacy.
    """
    
    # Metric thresholds for classification (percentage or absolute values)
    THRESHOLDS = {
        "gaming": {
            "gpu_utilization": (60, 100),
            "cpu_utilization": (30, 90),
            "vram_percent": (40, 100),
            "gpu_power_ratio": (0.5, 1.0),  # Power usage vs limit
        },
        "ai_training": {
            "gpu_utilization": (80, 100),
            "vram_percent": (60, 100),
            "cpu_utilization": (20, 80),
            "gpu_compute_processes": (1, 100),
        },
        "cad_3d_modeling": {
            "gpu_utilization": (30, 90),
            "cpu_utilization": (40, 90),
            "ram_percent": (40, 90),
        },
        "graphics_design": {
            "gpu_utilization": (20, 70),
            "cpu_utilization": (30, 80),
            "ram_percent": (40, 85),
        },
        "video_editing": {
            "gpu_encoder_utilization": (10, 100),
            "disk_write_rate_mbps": (5, 500),
            "cpu_utilization": (40, 95),
        },
        "coding_development": {
            "gpu_utilization": (0, 30),
            "cpu_utilization": (10, 60),
            "ram_percent": (30, 80),
        },
        "document_editing": {
            "gpu_utilization": (0, 20),
            "cpu_utilization": (5, 40),
            "ram_percent": (20, 60),
        },
        "web_browsing": {
            "gpu_utilization": (0, 40),
            "cpu_utilization": (5, 50),
            "net_activity": (1, 1000),  # KB/s
        },
        "idle": {
            "gpu_utilization": (0, 10),
            "cpu_utilization": (0, 10),
            "disk_io_rate": (0, 1),
        },
        "system_maintenance": {
            "disk_write_rate_mbps": (10, 500),
            "cpu_utilization": (30, 100),
            "gpu_utilization": (0, 30),
        },
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the session classifier.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or get_default_config()
        self._history: deque = deque(maxlen=60)  # Last 60 seconds of metrics
        self._current_category: Optional[SessionCategory] = None
        self._lock = threading.Lock()
        
        session_config = self.config.get("session_classification", {})
        self.confidence_threshold = session_config.get("confidence_threshold", 0.6)
    
    def update(self, metrics: Dict[str, Any]) -> Optional[SessionCategory]:
        """
        Update classifier with new metrics and return current category.
        
        Args:
            metrics: Dictionary of current metric values
        
        Returns:
            Current SessionCategory or None if confidence too low
        """
        with self._lock:
            # Extract relevant metrics
            snapshot = self._extract_metrics(metrics)
            self._history.append(snapshot)
            
            # Need at least 5 seconds of data for classification
            if len(self._history) < 5:
                return None
            
            # Calculate average metrics over history window
            avg_metrics = self._calculate_averages()
            
            # Score each category
            scores = {}
            for category, thresholds in self.THRESHOLDS.items():
                score = self._score_category(avg_metrics, thresholds)
                scores[category] = score
            
            # Find best matching category
            best_category = max(scores, key=scores.get)
            best_score = scores[best_category]
            
            if best_score >= self.confidence_threshold:
                self._current_category = SessionCategory(
                    name=best_category,
                    confidence=round(best_score, 3),
                    detected_at=datetime.now(),
                    metrics_snapshot=avg_metrics,
                )
                return self._current_category
            
            return None
    
    def _extract_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Extract relevant metrics for classification."""
        snapshot = {}
        
        # GPU metrics
        for key in ["utilization", "gpu0_utilization"]:
            if key in metrics:
                val = metrics[key]
                snapshot["gpu_utilization"] = val.value if hasattr(val, "value") else val
                break
        
        for key in ["vram_percent", "gpu0_vram_percent"]:
            if key in metrics:
                val = metrics[key]
                snapshot["vram_percent"] = val.value if hasattr(val, "value") else val
                break
        
        for key in ["encoder_utilization", "gpu0_encoder_utilization"]:
            if key in metrics:
                val = metrics[key]
                snapshot["gpu_encoder_utilization"] = val.value if hasattr(val, "value") else val
                break
        
        for key in ["compute_processes", "gpu0_compute_processes"]:
            if key in metrics:
                val = metrics[key]
                snapshot["gpu_compute_processes"] = val.value if hasattr(val, "value") else val
                break
        
        # CPU metrics
        if "total_utilization" in metrics:
            val = metrics["total_utilization"]
            snapshot["cpu_utilization"] = val.value if hasattr(val, "value") else val
        
        # RAM metrics
        if "ram_percent" in metrics:
            val = metrics["ram_percent"]
            snapshot["ram_percent"] = val.value if hasattr(val, "value") else val
        
        # Disk metrics
        if "disk_write_rate_mbps" in metrics:
            val = metrics["disk_write_rate_mbps"]
            snapshot["disk_write_rate_mbps"] = val.value if hasattr(val, "value") else val
        
        # Network metrics
        for key in ["net_recv_rate_kbps", "net_send_rate_kbps"]:
            if key in metrics:
                val = metrics[key]
                rate = val.value if hasattr(val, "value") else val
                snapshot["net_activity"] = snapshot.get("net_activity", 0) + rate
        
        return snapshot
    
    def _calculate_averages(self) -> Dict[str, float]:
        """Calculate average metrics over history window."""
        if not self._history:
            return {}
        
        # Collect all keys
        all_keys = set()
        for snapshot in self._history:
            all_keys.update(snapshot.keys())
        
        # Calculate averages
        averages = {}
        for key in all_keys:
            values = [s.get(key, 0) for s in self._history if key in s]
            if values:
                averages[key] = sum(values) / len(values)
        
        return averages
    
    def _score_category(
        self, 
        metrics: Dict[str, float], 
        thresholds: Dict[str, Tuple[float, float]]
    ) -> float:
        """
        Score how well metrics match a category's thresholds.
        
        Returns:
            Score between 0.0 and 1.0
        """
        if not thresholds:
            return 0.0
        
        matched = 0
        total = 0
        
        for metric_name, (min_val, max_val) in thresholds.items():
            if metric_name in metrics:
                total += 1
                value = metrics[metric_name]
                if min_val <= value <= max_val:
                    # Score based on how centered the value is in the range
                    range_size = max_val - min_val
                    if range_size > 0:
                        center = (min_val + max_val) / 2
                        distance = abs(value - center) / (range_size / 2)
                        matched += 1 - (distance * 0.3)  # Partial credit for being in range
                    else:
                        matched += 1
        
        if total == 0:
            return 0.0
        
        return matched / total
    
    def get_current_category(self) -> Optional[SessionCategory]:
        """Get the current detected session category."""
        with self._lock:
            return self._current_category
    
    def reset(self) -> None:
        """Reset classifier state."""
        with self._lock:
            self._history.clear()
            self._current_category = None


# =============================================================================
# Cloud Upload (Google Drive)
# =============================================================================

class GDriveUploader:
    """
    Google Drive uploader for log files.
    
    Supports:
        - OAuth2 authentication
        - Automatic folder creation
        - File encryption before upload
        - Resume capability
    """
    
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Google Drive uploader.
        
        Args:
            config: Configuration dictionary
        """
        if not HAS_GDRIVE:
            raise ImportError(
                "Google Drive dependencies not installed. "
                "Install with: pip install google-api-python-client google-auth-oauthlib"
            )
        
        self.config = config or get_default_config()
        cloud_config = self.config.get("cloud", {})
        gdrive_config = cloud_config.get("gdrive", {})
        
        project_root = Path(__file__).parent.parent
        
        self.credentials_file = Path(
            gdrive_config.get("credentials_file", project_root / "configs" / "gdrive_credentials.json")
        )
        self.token_file = Path(
            gdrive_config.get("token_file", project_root / "configs" / "gdrive_token.json")
        )
        self.folder_name = gdrive_config.get("folder_name", "OptiMetrics_Logs")
        
        self._service = None
        self._folder_id = None
        self._encryptor = None
        
        if cloud_config.get("encrypt_before_upload", True):
            self._init_encryption()
    
    def _init_encryption(self) -> None:
        """Initialize encryption for file uploads."""
        if not HAS_CRYPTO:
            logger.warning("Encryption requested but cryptography not installed")
            return
        
        project_root = Path(__file__).parent.parent
        key_file = project_root / "configs" / "encryption.key"
        
        if key_file.exists():
            with open(key_file, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, "wb") as f:
                f.write(key)
        
        self._encryptor = Fernet(key)
    
    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive.
        
        Returns:
            True if authentication successful
        """
        creds = None
        
        # Load existing token
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            except Exception:
                pass
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            
            if not creds:
                if not self.credentials_file.exists():
                    logger.error(
                        f"Credentials file not found: {self.credentials_file}\n"
                        "Please download OAuth credentials from Google Cloud Console."
                    )
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save token
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, "w") as f:
                f.write(creds.to_json())
        
        self._service = build("drive", "v3", credentials=creds)
        return True
    
    def _get_or_create_folder(self) -> Optional[str]:
        """Get or create the upload folder in Google Drive."""
        if self._folder_id:
            return self._folder_id
        
        if not self._service:
            return None
        
        # Search for existing folder
        query = f"name='{self.folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self._service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        
        if files:
            self._folder_id = files[0]["id"]
            return self._folder_id
        
        # Create new folder
        folder_metadata = {
            "name": self.folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        folder = self._service.files().create(body=folder_metadata, fields="id").execute()
        self._folder_id = folder.get("id")
        return self._folder_id
    
    def upload_file(self, file_path: str, encrypt: bool = True) -> Optional[str]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to file to upload
            encrypt: Whether to encrypt before upload
        
        Returns:
            File ID if successful, None otherwise
        """
        if not self._service:
            if not self.authenticate():
                return None
        
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        folder_id = self._get_or_create_folder()
        if not folder_id:
            return None
        
        try:
            # Encrypt if requested
            upload_path = file_path
            if encrypt and self._encryptor:
                with open(file_path, "rb") as f:
                    data = f.read()
                encrypted_data = self._encryptor.encrypt(data)
                
                upload_path = file_path.with_suffix(file_path.suffix + ".enc")
                with open(upload_path, "wb") as f:
                    f.write(encrypted_data)
            
            # Upload
            file_metadata = {
                "name": upload_path.name,
                "parents": [folder_id]
            }
            media = MediaFileUpload(str(upload_path), resumable=True)
            
            file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()
            
            # Clean up encrypted temp file
            if encrypt and self._encryptor and upload_path != file_path:
                upload_path.unlink()
            
            logger.info(f"Uploaded {file_path.name} to Google Drive")
            return file.get("id")
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None
    
    def upload_directory(self, dir_path: str, pattern: str = "*.csv") -> List[str]:
        """
        Upload all matching files from a directory.
        
        Args:
            dir_path: Directory path
            pattern: Glob pattern for files to upload
        
        Returns:
            List of uploaded file IDs
        """
        dir_path = Path(dir_path)
        uploaded_ids = []
        
        for file_path in dir_path.glob(pattern):
            file_id = self.upload_file(str(file_path))
            if file_id:
                uploaded_ids.append(file_id)
        
        return uploaded_ids


# =============================================================================
# Logging Utilities
# =============================================================================

def setup_logging(config: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Set up logging for OptiMetrics.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Configured logger
    """
    config = config or get_default_config()
    debug_config = config.get("debug", {})
    
    log_level = getattr(logging, debug_config.get("log_level", "INFO").upper())
    verbose = debug_config.get("verbose", False)
    
    # Configure root logger
    logger = logging.getLogger("optimetrics")
    logger.setLevel(log_level)
    
    # Console handler
    if verbose or log_level == logging.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if debug_config.get("save_debug_logs", False):
        project_root = Path(__file__).parent.parent
        log_file = project_root / debug_config.get("debug_log_file", "logs/debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_log_file_path(config: Optional[Dict[str, Any]] = None) -> Path:
    """
    Get the current log file path based on date.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Path to current log file
    """
    config = config or get_default_config()
    logging_config = config.get("logging", {})
    
    project_root = Path(__file__).parent.parent
    log_dir = project_root / logging_config.get("log_directory", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Daily rolling log file
    date_str = datetime.now().strftime("%Y-%m-%d")
    hardware_id = get_cached_hardware_id()[:8]
    
    log_file = log_dir / f"metrics_{hardware_id}_{date_str}.csv"
    
    return log_file


# =============================================================================
# Session State Management (for auto-resume)
# =============================================================================

@dataclass
class SessionState:
    """Persistent session state for auto-resume."""
    last_timestamp: str
    last_log_file: str
    hardware_id: str
    session_start: str
    metrics_count: int


def save_session_state(state: SessionState, state_file: Optional[str] = None) -> bool:
    """Save session state for resume after reboot."""
    if state_file is None:
        project_root = Path(__file__).parent.parent
        state_file = project_root / ".session_state.json"
    
    try:
        with open(state_file, "w") as f:
            json.dump(asdict(state), f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save session state: {e}")
        return False


def load_session_state(state_file: Optional[str] = None) -> Optional[SessionState]:
    """Load session state for resume."""
    if state_file is None:
        project_root = Path(__file__).parent.parent
        state_file = project_root / ".session_state.json"
    
    state_file = Path(state_file)
    if not state_file.exists():
        return None
    
    try:
        with open(state_file, "r") as f:
            data = json.load(f)
        return SessionState(**data)
    except Exception as e:
        logger.error(f"Failed to load session state: {e}")
        return None
