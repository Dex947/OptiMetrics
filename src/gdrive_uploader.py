"""
Google Drive Auto-Uploader for OptiMetrics

Handles automatic incremental uploads of collected metrics to a shared
Google Drive folder for research data aggregation.
"""

import json
import gzip
import shutil
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import threading
import time

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

SCOPES = ["https://www.googleapis.com/auth/drive"]
SHARED_FOLDER_ID = "1KLCQmnhgXTraQvVs0I60iut9scDMCMxr"


class IncrementalUploader:
    """Handles incremental uploads of metrics files to Google Drive."""
    
    def __init__(self, config_path: Optional[str] = None):
        if not HAS_GDRIVE:
            raise ImportError(
                "Google Drive API not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
        
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_config(config_path)
        self._service = None
        self._upload_state_file = self.project_root / ".upload_state.json"
        self._upload_state = self._load_upload_state()
        self._lock = threading.Lock()
        self._running = False
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load uploader configuration."""
        if config_path is None:
            config_path = self.project_root / "configs" / "gdrive_service_config.json"
        
        config_path = Path(config_path)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning(f"Failed to load config from {config_path}, using defaults")
        
        return {
            "research_folder_id": SHARED_FOLDER_ID,
            "retry_attempts": 3,
            "retry_delay_seconds": 60,
            "compress_before_upload": True,
        }
    
    def _load_upload_state(self) -> Dict[str, Any]:
        """Load upload state to track uploaded files."""
        if self._upload_state_file.exists():
            try:
                with open(self._upload_state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Failed to load upload state, starting fresh")
        
        return {"uploaded_files": {}, "last_upload": None, "total_bytes_uploaded": 0}
    
    def _save_upload_state(self) -> None:
        """Save upload state."""
        try:
            with open(self._upload_state_file, "w", encoding="utf-8") as f:
                json.dump(self._upload_state, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save upload state: {e}")
    
    def authenticate(self, credentials_path: Optional[str] = None) -> bool:
        """Authenticate with Google Drive using OAuth2 or service account."""
        if credentials_path is None:
            credentials_path = self.project_root / "configs" / "gdrive_credentials.json"
        
        credentials_path = Path(credentials_path)
        token_path = self.project_root / "configs" / "gdrive_token.json"
        creds = None
        
        # Try existing token
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
                    logger.error(f"Credentials file not found: {credentials_path}")
                    return False
                
                try:
                    with open(credentials_path, "r", encoding="utf-8") as f:
                        cred_data = json.load(f)
                    
                    if cred_data.get("type") == "service_account":
                        creds = service_account.Credentials.from_service_account_file(
                            str(credentials_path), scopes=SCOPES
                        )
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            str(credentials_path), SCOPES
                        )
                        creds = flow.run_local_server(port=0)
                    
                    # Save token
                    if hasattr(creds, "to_json"):
                        token_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(token_path, "w", encoding="utf-8") as f:
                            f.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Authentication failed: {e}")
                    return False
        
        try:
            self._service = build("drive", "v3", credentials=creds)
            logger.info("Google Drive authentication successful")
            return True
        except Exception as e:
            logger.error(f"Failed to build Drive service: {e}")
            return False
    
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
        """Upload a single file to Google Drive."""
        if not self._service and not self.authenticate():
            return None
        
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        # Use shared research folder
        if folder_id is None:
            folder_id = self.config.get("research_folder_id", SHARED_FOLDER_ID)
        
        # Check if already uploaded (by hash)
        file_hash = self._compute_file_hash(file_path)
        cached = self._upload_state["uploaded_files"].get(file_path.name, {})
        if cached.get("hash") == file_hash:
            logger.debug(f"File {file_path.name} already uploaded (unchanged)")
            return cached.get("id")
        
        # Compress if requested
        upload_path = file_path
        if compress and self.config.get("compress_before_upload", True):
            try:
                upload_path = self._compress_file(file_path)
            except IOError as e:
                logger.warning(f"Compression failed, uploading uncompressed: {e}")
                upload_path = file_path
        
        try:
            file_metadata = {"name": upload_path.name}
            if folder_id:
                file_metadata["parents"] = [folder_id]
            
            # Set mimetype based on file extension
            mimetype = "text/csv" if upload_path.suffix.lower() == ".csv" else "application/octet-stream"
            if upload_path.suffix.lower() == ".gz":
                mimetype = "application/gzip"
            
            media = MediaFileUpload(str(upload_path), mimetype=mimetype, resumable=True, chunksize=1024*1024)
            
            # Upload with retry
            retry_attempts = self.config.get("retry_attempts", 3)
            retry_delay = self.config.get("retry_delay_seconds", 60)
            
            for attempt in range(retry_attempts):
                try:
                    result = self._service.files().create(
                        body=file_metadata, media_body=media, fields="id, size"
                    ).execute()
                    
                    file_id = result.get("id")
                    file_size = int(result.get("size", 0))
                    
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
                    
                    # Cleanup compressed file
                    if upload_path != file_path and upload_path.exists():
                        upload_path.unlink()
                    
                    return file_id
                    
                except HttpError as e:
                    if attempt < retry_attempts - 1:
                        logger.warning(f"Upload failed, retrying in {retry_delay}s: {e}")
                        time.sleep(retry_delay)
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            if upload_path != file_path and upload_path.exists():
                upload_path.unlink()
            return None
        
        return None
    
    def upload_new_files(self, log_directory: Optional[str] = None) -> List[str]:
        """Upload all new/changed files from log directory."""
        if log_directory is None:
            log_directory = self.project_root / "logs"
        
        log_directory = Path(log_directory)
        if not log_directory.exists():
            logger.warning(f"Log directory not found: {log_directory}")
            return []
        
        uploaded_ids = []
        for csv_file in log_directory.glob("*.csv"):
            file_id = self.upload_file(str(csv_file))
            if file_id:
                uploaded_ids.append(file_id)
        
        return uploaded_ids
    
    def start_background_sync(self, interval_minutes: int = 30) -> None:
        """Start background sync thread."""
        if self._running:
            return
        
        self._running = True
        
        def sync_loop():
            while self._running:
                try:
                    self.upload_new_files()
                except Exception as e:
                    logger.error(f"Background sync error: {e}")
                
                # Sleep in small increments for responsive shutdown
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


def setup_gdrive_for_research() -> bool:
    """Interactive setup for Google Drive research data collection."""
    print("\n" + "="*60)
    print("OptiMetrics Google Drive Setup")
    print("="*60)
    print("\nThis will configure automatic upload of anonymized metrics")
    print("to support hardware optimization research.\n")
    
    project_root = Path(__file__).parent.parent
    creds_path = project_root / "configs" / "gdrive_credentials.json"
    
    if not creds_path.exists():
        print("To enable cloud sync, you need Google Drive API credentials.\n")
        print("Steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Google Drive API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download credentials.json")
        print(f"6. Save as: {creds_path}\n")
        return False
    
    try:
        uploader = IncrementalUploader()
        if uploader.authenticate():
            print("\nAuthentication successful!")
            print("Metrics will be automatically uploaded to Google Drive.")
            return True
        else:
            print("\nAuthentication failed. Please check your credentials.")
            return False
    except ImportError as e:
        print(f"\nMissing dependencies: {e}")
        return False


if __name__ == "__main__":
    setup_gdrive_for_research()
