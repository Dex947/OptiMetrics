"""
OptiMetrics Cloud Sync

Handles incremental uploads to Google Drive with:
- Per-device folder structure
- Append-only uploads (continue from last row)
- Proper file management on cloud
"""

import csv
import json
import io
import logging
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

from src.data_manager import DeviceDataManager, extract_rows_from_csv, rows_to_csv_string

logger = logging.getLogger("optimetrics.cloud_sync")

SCOPES = ["https://www.googleapis.com/auth/drive"]
SHARED_FOLDER_ID = "1KLCQmnhgXTraQvVs0I60iut9scDMCMxr"


class CloudSyncManager:
    """
    Manages cloud synchronization for device data.
    
    Features:
    - Creates device folder on first sync
    - Uploads new rows incrementally (appends to existing files)
    - Tracks sync state per file
    """
    
    def __init__(self, data_manager: DeviceDataManager):
        if not HAS_GDRIVE:
            raise ImportError(
                "Google Drive API not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
        
        self.data_manager = data_manager
        self.hardware_id = data_manager.hardware_id
        self.project_root = Path(__file__).parent.parent
        
        self._service = None
        self._lock = threading.Lock()
        self._running = False
        self._sync_thread: Optional[threading.Thread] = None
    
    def authenticate(self, credentials_path: Optional[str] = None) -> bool:
        """Authenticate with Google Drive."""
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
    
    def _ensure_device_folder(self) -> Optional[str]:
        """Ensure device folder exists on Google Drive, create if needed."""
        folder_id = self.data_manager.get_device_folder_id()
        
        if folder_id:
            # Verify folder still exists
            try:
                self._service.files().get(fileId=folder_id, fields="id").execute()
                return folder_id
            except HttpError as e:
                if e.resp.status == 404:
                    logger.info("Device folder not found, will recreate")
                    folder_id = None
                else:
                    raise
        
        if not folder_id:
            # Check if folder already exists by name
            query = (
                f"name='{self.hardware_id}' and "
                f"'{SHARED_FOLDER_ID}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )
            
            try:
                results = self._service.files().list(
                    q=query, fields="files(id, name)", spaces="drive"
                ).execute()
                
                files = results.get("files", [])
                if files:
                    folder_id = files[0]["id"]
                    logger.info(f"Found existing device folder: {folder_id}")
                else:
                    # Create new folder
                    folder_metadata = {
                        "name": self.hardware_id,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [SHARED_FOLDER_ID]
                    }
                    
                    folder = self._service.files().create(
                        body=folder_metadata, fields="id"
                    ).execute()
                    
                    folder_id = folder.get("id")
                    logger.info(f"Created device folder: {folder_id}")
                
                # Save folder ID
                self.data_manager.set_device_folder_id(folder_id)
                
            except HttpError as e:
                logger.error(f"Failed to create/find device folder: {e}")
                return None
        
        return folder_id
    
    def _find_cloud_file(self, folder_id: str, filename: str) -> Optional[str]:
        """Find a file in the device folder by name."""
        query = (
            f"name='{filename}' and "
            f"'{folder_id}' in parents and "
            f"trashed=false"
        )
        
        try:
            results = self._service.files().list(
                q=query, fields="files(id, name)", spaces="drive"
            ).execute()
            
            files = results.get("files", [])
            if files:
                return files[0]["id"]
        except HttpError as e:
            logger.error(f"Error finding file {filename}: {e}")
        
        return None
    
    def _download_existing_file(self, file_id: str) -> Optional[str]:
        """Download existing file content from Google Drive."""
        try:
            request = self._service.files().get_media(fileId=file_id)
            content = request.execute()
            return content.decode("utf-8")
        except HttpError as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def _upload_or_append_file(
        self,
        folder_id: str,
        hw_type: str,
        local_path: Path,
        start_row: int,
        end_row: int
    ) -> Optional[Tuple[str, int]]:
        """
        Upload new rows to cloud file, appending to existing content.
        
        Returns:
            Tuple of (file_id, rows_uploaded) or None on failure
        """
        filename = f"{hw_type}.csv"
        
        # Extract new rows from local file
        headers, new_rows = extract_rows_from_csv(local_path, start_row, end_row)
        
        if not new_rows:
            logger.debug(f"No new rows to upload for {hw_type}")
            return None
        
        # Check if file exists on cloud
        cloud_file_id = self._find_cloud_file(folder_id, filename)
        
        if cloud_file_id:
            # Download existing content and append
            existing_content = self._download_existing_file(cloud_file_id)
            
            if existing_content:
                # Parse existing content to get row count
                existing_lines = existing_content.strip().split("\n")
                
                # Create new content with appended rows
                new_rows_csv = io.StringIO()
                writer = csv.DictWriter(new_rows_csv, fieldnames=headers, extrasaction="ignore")
                for row in new_rows:
                    writer.writerow(row)
                
                # Combine: existing + new rows (no header for new rows)
                combined_content = existing_content.rstrip("\n") + "\n" + new_rows_csv.getvalue()
                
                # Upload updated file
                media = MediaIoBaseUpload(
                    io.BytesIO(combined_content.encode("utf-8")),
                    mimetype="text/csv",
                    resumable=True
                )
                
                try:
                    result = self._service.files().update(
                        fileId=cloud_file_id,
                        media_body=media,
                        fields="id, size"
                    ).execute()
                    
                    logger.info(f"Appended {len(new_rows)} rows to {filename}")
                    return (cloud_file_id, end_row)
                    
                except HttpError as e:
                    logger.error(f"Failed to update {filename}: {e}")
                    return None
            else:
                # Couldn't download, treat as new file
                cloud_file_id = None
        
        if not cloud_file_id:
            # Create new file with header + rows
            csv_content = rows_to_csv_string(headers, new_rows)
            
            file_metadata = {
                "name": filename,
                "parents": [folder_id]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(csv_content.encode("utf-8")),
                mimetype="text/csv",
                resumable=True
            )
            
            try:
                result = self._service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, size"
                ).execute()
                
                cloud_file_id = result.get("id")
                logger.info(f"Created {filename} with {len(new_rows)} rows")
                return (cloud_file_id, end_row)
                
            except HttpError as e:
                logger.error(f"Failed to create {filename}: {e}")
                return None
        
        return None
    
    def sync(self) -> Dict[str, int]:
        """
        Synchronize all pending data to cloud.
        
        Returns:
            Dictionary of rows synced per hardware type
        """
        if not self._service and not self.authenticate():
            logger.error("Cannot sync: not authenticated")
            return {}
        
        synced = {}
        
        with self._lock:
            # Ensure device folder exists
            folder_id = self._ensure_device_folder()
            if not folder_id:
                logger.error("Cannot sync: failed to get device folder")
                return {}
            
            # Get pending uploads
            pending = self.data_manager.get_pending_uploads()
            
            for hw_type, local_path, start_row, end_row in pending:
                result = self._upload_or_append_file(
                    folder_id, hw_type, local_path, start_row, end_row
                )
                
                if result:
                    cloud_file_id, rows_uploaded = result
                    self.data_manager.mark_uploaded(hw_type, rows_uploaded, cloud_file_id)
                    synced[hw_type] = end_row - start_row
        
        if synced:
            total_rows = sum(synced.values())
            logger.info(f"Synced {total_rows} total rows across {len(synced)} files")
        
        return synced
    
    def start_background_sync(self, interval_minutes: int = 5) -> None:
        """Start background sync thread."""
        if self._running:
            return
        
        self._running = True
        
        def sync_loop():
            # Initial sync
            try:
                self.sync()
            except Exception as e:
                logger.error(f"Initial sync error: {e}")
            
            while self._running:
                # Sleep in small increments for responsive shutdown
                for _ in range(interval_minutes * 60):
                    if not self._running:
                        break
                    time.sleep(1)
                
                if not self._running:
                    break
                
                try:
                    self.sync()
                except Exception as e:
                    logger.error(f"Background sync error: {e}")
        
        self._sync_thread = threading.Thread(
            target=sync_loop, name="CloudSync", daemon=True
        )
        self._sync_thread.start()
        logger.info(f"Background sync started (interval: {interval_minutes} min)")
    
    def stop_background_sync(self) -> None:
        """Stop background sync thread."""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        logger.info("Background sync stopped")
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        stats = self.data_manager.get_stats()
        stats["cloud_folder_id"] = self.data_manager.get_device_folder_id()
        stats["authenticated"] = self._service is not None
        return stats


# Backwards compatibility alias
IncrementalUploader = CloudSyncManager
