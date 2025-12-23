"""
Google Drive Auto-Uploader for OptiMetrics

This module handles automatic incremental uploads of collected metrics
to a shared Google Drive folder for research data aggregation.

Features:
    - Incremental uploads (only new data)
    - Automatic retry on failure
    - Bandwidth-efficient compression
    - Service account support for unattended operation
"""

import os
import sys
import json
import gzip
import shutil
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import threading
import time

# Google Drive API imports
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

logger = logging.getLogger("optimetrics.gdrive")

# Scopes required for Google Drive access
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]


class IncrementalUploader:
    """
    Handles incremental uploads of metrics files to Google Drive.
    
    Tracks which files have been uploaded to avoid duplicates and
    supports resumable uploads for large files.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the uploader.
        
        Args:
            config_path: Path to gdrive_service_config.json
        """
        if not HAS_GDRIVE:
            raise ImportError(
                "Google Drive API not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
        
        self.project_root = Path(__file__).parent.parent
        
        # Load configuration
        if config_path is None:
            config_path = self.project_root / "configs" / "gdrive_service_config.json"
        
        self.config = self._load_config(config_path)
        
        # State tracking
        self._service = None
        self._upload_state_file = self.project_root / ".upload_state.json"
        self._upload_state = self._load_upload_state()
        self._lock = threading.Lock()
        self._running = False
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load uploader configuration."""
        config_path = Path(config_path)
        
        if config_path.exists():
            with open(config_path, "r") as f:
                return json.load(f)
        
        # Default configuration
        return {
            "research_folder_id": None,
            "upload_mode": "incremental",
            "batch_size_mb": 5,
            "retry_attempts": 3,
            "retry_delay_seconds": 60,
            "compress_before_upload": True,
        }
    
    def _load_upload_state(self) -> Dict[str, Any]:
        """Load upload state to track uploaded files."""
        if self._upload_state_file.exists():
            try:
                with open(self._upload_state_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {
            "uploaded_files": {},
            "last_upload": None,
            "total_bytes_uploaded": 0,
        }
    
    def _save_upload_state(self) -> None:
        """Save upload state."""
        try:
            with open(self._upload_state_file, "w") as f:
                json.dump(self._upload_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save upload state: {e}")
    
    def authenticate(self, credentials_path: Optional[str] = None) -> bool:
        """
        Authenticate with Google Drive.
        
        Supports both OAuth2 (interactive) and service account (unattended).
        
        Args:
            credentials_path: Path to credentials file
        
        Returns:
            True if authentication successful
        """
        if credentials_path is None:
            credentials_path = self.project_root / "configs" / "gdrive_credentials.json"
        
        credentials_path = Path(credentials_path)
        token_path = self.project_root / "configs" / "gdrive_token.json"
        
        creds = None
        
        # Try to load existing token
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
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
                if not credentials_path.exists():
                    logger.error(
                        f"Credentials file not found: {credentials_path}\n"
                        "Please set up Google Drive API credentials."
                    )
                    return False
                
                # Check if it's a service account
                with open(credentials_path, "r") as f:
                    cred_data = json.load(f)
                
                if "type" in cred_data and cred_data["type"] == "service_account":
                    # Service account authentication
                    creds = service_account.Credentials.from_service_account_file(
                        str(credentials_path), scopes=SCOPES
                    )
                else:
                    # OAuth2 flow
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save token for future use
                if hasattr(creds, "to_json"):
                    token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(token_path, "w") as f:
                        f.write(creds.to_json())
        
        try:
            self._service = build("drive", "v3", credentials=creds)
            logger.info("Google Drive authentication successful")
            return True
        except Exception as e:
            logger.error(f"Failed to build Drive service: {e}")
            return False
    
    def _get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Get or create a folder in Google Drive."""
        if not self._service:
            return None
        
        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        try:
            results = self._service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get("files", [])
            
            if files:
                return files[0]["id"]
            
            # Create folder
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            if parent_id:
                folder_metadata["parents"] = [parent_id]
            
            folder = self._service.files().create(body=folder_metadata, fields="id").execute()
            return folder.get("id")
            
        except HttpError as e:
            logger.error(f"Failed to get/create folder: {e}")
            return None
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of a file for change detection."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _compress_file(self, file_path: Path) -> Path:
        """Compress a file using gzip."""
        gz_path = file_path.with_suffix(file_path.suffix + ".gz")
        
        with open(file_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return gz_path
    
    def upload_file(
        self, 
        file_path: str, 
        folder_id: Optional[str] = None,
        compress: bool = True
    ) -> Optional[str]:
        """
        Upload a single file to Google Drive.
        
        Args:
            file_path: Path to file to upload
            folder_id: Target folder ID (uses research folder if None)
            compress: Whether to compress before upload
        
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
        
        # Use shared research folder - all contributors upload here
        if folder_id is None:
            folder_id = self.config.get("research_folder_id")
            # Default to the shared OptiMetrics research folder
            if not folder_id:
                folder_id = "1KLCQmnhgXTraQvVs0I60iut9scDMCMxr"
        
        # Check if file already uploaded (by hash)
        file_hash = self._compute_file_hash(file_path)
        if file_path.name in self._upload_state["uploaded_files"]:
            if self._upload_state["uploaded_files"][file_path.name].get("hash") == file_hash:
                logger.debug(f"File {file_path.name} already uploaded (unchanged)")
                return self._upload_state["uploaded_files"][file_path.name].get("id")
        
        # Compress if requested
        upload_path = file_path
        if compress and self.config.get("compress_before_upload", True):
            upload_path = self._compress_file(file_path)
        
        try:
            file_metadata = {
                "name": upload_path.name,
            }
            if folder_id:
                file_metadata["parents"] = [folder_id]
            
            media = MediaFileUpload(
                str(upload_path),
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Upload with retry
            for attempt in range(self.config.get("retry_attempts", 3)):
                try:
                    file = self._service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields="id, size"
                    ).execute()
                    
                    file_id = file.get("id")
                    file_size = int(file.get("size", 0))
                    
                    # Update state
                    with self._lock:
                        self._upload_state["uploaded_files"][file_path.name] = {
                            "id": file_id,
                            "hash": file_hash,
                            "uploaded_at": datetime.now().isoformat(),
                            "size": file_size,
                        }
                        self._upload_state["total_bytes_uploaded"] += file_size
                        self._upload_state["last_upload"] = datetime.now().isoformat()
                        self._save_upload_state()
                    
                    logger.info(f"Uploaded {file_path.name} ({file_size} bytes)")
                    
                    # Clean up compressed file
                    if upload_path != file_path:
                        upload_path.unlink()
                    
                    return file_id
                    
                except HttpError as e:
                    if attempt < self.config.get("retry_attempts", 3) - 1:
                        delay = self.config.get("retry_delay_seconds", 60)
                        logger.warning(f"Upload failed, retrying in {delay}s: {e}")
                        time.sleep(delay)
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            # Clean up compressed file on failure
            if upload_path != file_path and upload_path.exists():
                upload_path.unlink()
            return None
    
    def upload_new_files(self, log_directory: Optional[str] = None) -> List[str]:
        """
        Upload all new/changed files from log directory.
        
        Args:
            log_directory: Directory containing log files
        
        Returns:
            List of uploaded file IDs
        """
        if log_directory is None:
            log_directory = self.project_root / "logs"
        
        log_directory = Path(log_directory)
        uploaded_ids = []
        
        # Find CSV files
        for csv_file in log_directory.glob("*.csv"):
            file_id = self.upload_file(str(csv_file))
            if file_id:
                uploaded_ids.append(file_id)
        
        return uploaded_ids
    
    def start_background_sync(self, interval_minutes: int = 30) -> None:
        """
        Start background sync thread.
        
        Args:
            interval_minutes: Upload interval in minutes
        """
        if self._running:
            return
        
        self._running = True
        
        def sync_loop():
            while self._running:
                try:
                    self.upload_new_files()
                except Exception as e:
                    logger.error(f"Background sync error: {e}")
                
                # Sleep in small increments to allow quick shutdown
                for _ in range(interval_minutes * 60):
                    if not self._running:
                        break
                    time.sleep(1)
        
        thread = threading.Thread(target=sync_loop, name="GDriveSync", daemon=True)
        thread.start()
        logger.info(f"Background sync started (interval: {interval_minutes} min)")
    
    def stop_background_sync(self) -> None:
        """Stop background sync thread."""
        self._running = False
        logger.info("Background sync stopped")
    
    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload statistics."""
        return {
            "total_files_uploaded": len(self._upload_state["uploaded_files"]),
            "total_bytes_uploaded": self._upload_state["total_bytes_uploaded"],
            "last_upload": self._upload_state["last_upload"],
        }


def setup_gdrive_for_research():
    """
    Interactive setup for Google Drive research data collection.
    
    Guides users through setting up credentials and folder access.
    """
    print("\n" + "="*60)
    print("OptiMetrics Google Drive Setup")
    print("="*60)
    print("\nThis will configure automatic upload of anonymized metrics")
    print("to support hardware optimization research.\n")
    
    project_root = Path(__file__).parent.parent
    creds_path = project_root / "configs" / "gdrive_credentials.json"
    
    if not creds_path.exists():
        print("To enable cloud sync, you need Google Drive API credentials.")
        print("\nSteps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Google Drive API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download credentials.json")
        print(f"6. Save as: {creds_path}")
        print("\nAlternatively, a service account can be used for unattended operation.")
        return False
    
    uploader = IncrementalUploader()
    
    if uploader.authenticate():
        print("\nAuthentication successful!")
        print("Metrics will be automatically uploaded to Google Drive.")
        return True
    else:
        print("\nAuthentication failed. Please check your credentials.")
        return False


if __name__ == "__main__":
    # Run setup if executed directly
    setup_gdrive_for_research()
