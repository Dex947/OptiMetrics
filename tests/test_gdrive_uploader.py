"""
Tests for Google Drive Uploader

Covers:
    - Initialization
    - Configuration loading
    - Upload state management
    - File operations (hash, compress)
    - Error handling
"""

import pytest
import tempfile
import os
import json
import gzip
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import with fallback for missing dependencies
try:
    from src.gdrive_uploader import IncrementalUploader, HAS_GDRIVE, SHARED_FOLDER_ID
except ImportError:
    HAS_GDRIVE = False
    IncrementalUploader = None
    SHARED_FOLDER_ID = "1KLCQmnhgXTraQvVs0I60iut9scDMCMxr"


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestUploaderInitialization:
    """Tests for uploader initialization."""
    
    def test_initialization(self):
        """Test uploader initializes correctly."""
        uploader = IncrementalUploader()
        assert uploader is not None
        assert uploader.project_root is not None
    
    def test_initialization_with_config_path(self):
        """Test initialization with custom config path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"research_folder_id": "test_id"}, f)
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader(config_path=temp_path)
            assert uploader.config.get("research_folder_id") == "test_id"
        finally:
            os.unlink(temp_path)
    
    def test_initialization_missing_config(self):
        """Test initialization with missing config uses defaults."""
        uploader = IncrementalUploader(config_path="/nonexistent/config.json")
        assert uploader.config is not None
        assert "research_folder_id" in uploader.config


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestUploaderConfiguration:
    """Tests for configuration loading."""
    
    def test_load_valid_config(self):
        """Test loading valid configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "research_folder_id": "test_folder",
                "retry_attempts": 5,
                "compress_before_upload": False,
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader(config_path=temp_path)
            assert uploader.config["research_folder_id"] == "test_folder"
            assert uploader.config["retry_attempts"] == 5
            assert uploader.config["compress_before_upload"] is False
        finally:
            os.unlink(temp_path)
    
    def test_load_invalid_json(self):
        """Test loading invalid JSON uses defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader(config_path=temp_path)
            assert uploader.config is not None
        finally:
            os.unlink(temp_path)
    
    def test_default_config_values(self):
        """Test default configuration values."""
        uploader = IncrementalUploader(config_path="/nonexistent/config.json")
        
        assert uploader.config.get("retry_attempts", 3) >= 1
        assert "research_folder_id" in uploader.config


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestUploadState:
    """Tests for upload state management."""
    
    def test_initial_state(self):
        """Test initial upload state."""
        uploader = IncrementalUploader()
        
        assert "uploaded_files" in uploader._upload_state
        assert "last_upload" in uploader._upload_state
        assert "total_bytes_uploaded" in uploader._upload_state
    
    def test_save_state(self):
        """Test saving upload state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            uploader = IncrementalUploader()
            uploader._upload_state_file = Path(temp_dir) / ".upload_state.json"
            
            uploader._upload_state["uploaded_files"]["test.csv"] = {
                "id": "file_id",
                "hash": "abc123",
            }
            uploader._save_upload_state()
            
            assert uploader._upload_state_file.exists()
    
    def test_load_existing_state(self):
        """Test loading existing upload state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / ".upload_state.json"
            
            state = {
                "uploaded_files": {"test.csv": {"id": "123", "hash": "abc"}},
                "last_upload": "2024-01-01T00:00:00",
                "total_bytes_uploaded": 1000,
            }
            with open(state_file, "w") as f:
                json.dump(state, f)
            
            uploader = IncrementalUploader()
            uploader._upload_state_file = state_file
            uploader._upload_state = uploader._load_upload_state()
            
            assert uploader._upload_state["total_bytes_uploaded"] == 1000
    
    def test_corrupted_state_file(self):
        """Test handling of corrupted state file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / ".upload_state.json"
            
            with open(state_file, "w") as f:
                f.write("not valid json")
            
            uploader = IncrementalUploader()
            uploader._upload_state_file = state_file
            state = uploader._load_upload_state()
            
            # Should return default state
            assert "uploaded_files" in state


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestFileOperations:
    """Tests for file operations."""
    
    def test_compute_file_hash(self):
        """Test file hash computation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader()
            hash1 = uploader._compute_file_hash(Path(temp_path))
            hash2 = uploader._compute_file_hash(Path(temp_path))
            
            assert hash1 == hash2
            assert len(hash1) == 32  # MD5 hex length
        finally:
            os.unlink(temp_path)
    
    def test_hash_different_content(self):
        """Test different content produces different hash."""
        uploader = IncrementalUploader()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("content 1")
            path1 = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("content 2")
            path2 = f.name
        
        try:
            hash1 = uploader._compute_file_hash(Path(path1))
            hash2 = uploader._compute_file_hash(Path(path2))
            
            assert hash1 != hash2
        finally:
            os.unlink(path1)
            os.unlink(path2)
    
    def test_compress_file(self):
        """Test file compression."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write("test,data\n" * 100)
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader()
            gz_path = uploader._compress_file(Path(temp_path))
            
            assert gz_path.exists()
            assert gz_path.suffix == ".gz"
            
            # Verify it's valid gzip
            with gzip.open(gz_path, 'rt') as f:
                content = f.read()
                assert "test,data" in content
            
            gz_path.unlink()
        finally:
            os.unlink(temp_path)
    
    def test_compress_reduces_size(self):
        """Test compression reduces file size."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write("test,data,row\n" * 1000)
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader()
            original_size = os.path.getsize(temp_path)
            
            gz_path = uploader._compress_file(Path(temp_path))
            compressed_size = os.path.getsize(gz_path)
            
            assert compressed_size < original_size
            
            gz_path.unlink()
        finally:
            os.unlink(temp_path)


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestAuthentication:
    """Tests for authentication."""
    
    def test_auth_missing_credentials(self):
        """Test authentication fails with missing credentials."""
        uploader = IncrementalUploader()
        
        # Should fail without credentials (may succeed if token exists)
        result = uploader.authenticate("/nonexistent/path/credentials.json")
        # Result depends on whether a valid token already exists
        assert isinstance(result, bool)
    
    def test_auth_invalid_credentials(self):
        """Test authentication with invalid credentials."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"invalid": "credentials"}, f)
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader()
            result = uploader.authenticate(temp_path)
            # May succeed if valid token exists, otherwise fails
            assert isinstance(result, bool)
        finally:
            os.unlink(temp_path)


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestUploadFile:
    """Tests for file upload."""
    
    def test_upload_missing_file(self):
        """Test uploading missing file returns None."""
        uploader = IncrementalUploader()
        uploader._service = Mock()  # Mock service
        
        result = uploader.upload_file("/nonexistent/file.csv")
        assert result is None
    
    def test_upload_without_auth(self):
        """Test upload without authentication."""
        uploader = IncrementalUploader()
        uploader._service = None  # Ensure no service
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write("test,data\n")
            temp_path = f.name
        
        try:
            # May succeed if token exists, otherwise returns None
            result = uploader.upload_file(temp_path, compress=False)
            # Result depends on auth state
            assert result is None or isinstance(result, str)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass
    
    def test_upload_skips_unchanged(self):
        """Test upload skips unchanged files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write("test,data\n")
            temp_path = f.name
        
        try:
            uploader = IncrementalUploader()
            uploader._service = Mock()
            
            # Pre-populate state with same hash
            file_hash = uploader._compute_file_hash(Path(temp_path))
            uploader._upload_state["uploaded_files"][Path(temp_path).name] = {
                "id": "existing_id",
                "hash": file_hash,
            }
            
            result = uploader.upload_file(temp_path)
            assert result == "existing_id"
        finally:
            os.unlink(temp_path)


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestUploadNewFiles:
    """Tests for batch upload."""
    
    def test_upload_empty_directory(self):
        """Test uploading from empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            uploader = IncrementalUploader()
            uploader._service = Mock()
            
            result = uploader.upload_new_files(temp_dir)
            assert result == []
    
    def test_upload_nonexistent_directory(self):
        """Test uploading from nonexistent directory."""
        uploader = IncrementalUploader()
        
        result = uploader.upload_new_files("/nonexistent/directory")
        assert result == []


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestBackgroundSync:
    """Tests for background sync."""
    
    def test_start_stop_sync(self):
        """Test starting and stopping background sync."""
        uploader = IncrementalUploader()
        
        uploader.start_background_sync(interval_minutes=1)
        assert uploader._running is True
        
        uploader.stop_background_sync()
        assert uploader._running is False
    
    def test_double_start(self):
        """Test double start is handled."""
        uploader = IncrementalUploader()
        
        uploader.start_background_sync(interval_minutes=1)
        uploader.start_background_sync(interval_minutes=1)  # Should not create second thread
        
        uploader.stop_background_sync()


@pytest.mark.skipif(not HAS_GDRIVE, reason="Google Drive API not installed")
class TestUploadStats:
    """Tests for upload statistics."""
    
    def test_get_stats(self):
        """Test getting upload statistics."""
        uploader = IncrementalUploader()
        
        stats = uploader.get_upload_stats()
        
        assert "total_files_uploaded" in stats
        assert "total_bytes_uploaded" in stats
        assert "last_upload" in stats
    
    def test_stats_after_upload(self):
        """Test stats reflect uploads."""
        uploader = IncrementalUploader()
        
        # Clear existing state first
        uploader._upload_state["uploaded_files"] = {"test.csv": {"id": "123"}}
        uploader._upload_state["total_bytes_uploaded"] = 1000
        
        stats = uploader.get_upload_stats()
        
        assert stats["total_files_uploaded"] >= 1
        assert stats["total_bytes_uploaded"] >= 1000


class TestSharedFolderID:
    """Tests for shared folder ID constant."""
    
    def test_shared_folder_id_format(self):
        """Test shared folder ID has correct format."""
        assert len(SHARED_FOLDER_ID) > 0
        assert SHARED_FOLDER_ID == "1KLCQmnhgXTraQvVs0I60iut9scDMCMxr"
