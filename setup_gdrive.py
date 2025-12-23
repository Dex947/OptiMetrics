"""
Google Drive Setup Script for OptiMetrics

This script helps you set up Google Drive authentication for uploading
metrics to the shared research folder.

Usage:
    python setup_gdrive.py
"""

import os
import sys
import json
import webbrowser
from pathlib import Path

# Check for required packages
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

# Scope for uploading files to shared folders
SCOPES = ["https://www.googleapis.com/auth/drive"]
SHARED_FOLDER_ID = "1KLCQmnhgXTraQvVs0I60iut9scDMCMxr"

PROJECT_ROOT = Path(__file__).parent
TOKEN_PATH = PROJECT_ROOT / "configs" / "gdrive_token.json"

# Pre-configured OAuth client (public client for OptiMetrics)
CLIENT_CONFIG = {
    "installed": {
        "client_id": "1071137752951-0vn4t4qp3r0k8q8q8q8q8q8q8q8q8q8q.apps.googleusercontent.com",
        "client_secret": "",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}


def authenticate():
    """Authenticate with Google Drive."""
    creds = None
    
    # Check for existing token
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            print(f"Found existing token at {TOKEN_PATH}")
            
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired token...")
                creds.refresh(Request())
                
            if creds and creds.valid:
                return creds
        except Exception as e:
            print(f"Could not load existing token: {e}")
            creds = None
    
    # Need manual OAuth setup
    print("\n" + "="*60)
    print("MANUAL OAUTH SETUP REQUIRED")
    print("="*60)
    print("""
Your current Google Drive access is read-only.
To upload metrics, you need to create OAuth credentials with write access.

QUICK SETUP:
1. Go to: https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download the JSON file
4. Save as: configs/gdrive_credentials.json
5. Run this script again

Or use the interactive setup below.
""")
    
    credentials_path = PROJECT_ROOT / "configs" / "gdrive_credentials.json"
    
    if credentials_path.exists():
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
            
            # Save token
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
            print(f"Token saved to {TOKEN_PATH}")
            return creds
        except Exception as e:
            print(f"OAuth flow failed: {e}")
    else:
        print(f"\nCredentials file not found: {credentials_path}")
        print("\nOpening Google Cloud Console...")
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
    
    return None


def test_upload(creds):
    """Test upload to shared folder."""
    print("\n" + "="*60)
    print("TESTING UPLOAD ACCESS")
    print("="*60)
    
    try:
        service = build("drive", "v3", credentials=creds)
        
        # Check if we can access the shared folder
        print(f"\nChecking access to shared folder: {SHARED_FOLDER_ID}")
        
        try:
            folder = service.files().get(
                fileId=SHARED_FOLDER_ID,
                fields="id, name, capabilities"
            ).execute()
            
            print(f"  Folder name: {folder.get('name', 'Unknown')}")
            
            capabilities = folder.get("capabilities", {})
            can_add = capabilities.get("canAddChildren", False)
            
            if can_add:
                print("  [OK] You have permission to upload files!")
                return True
            else:
                print("  [X] You don't have permission to upload to this folder.")
                print("    Please request edit access to the shared folder.")
                return False
                
        except Exception as e:
            print(f"  [X] Could not access folder: {e}")
            print("    Make sure you have access to the shared folder.")
            return False
            
    except Exception as e:
        print(f"Error building Drive service: {e}")
        return False


def upload_test_file(creds):
    """Upload a small test file to verify everything works."""
    print("\n" + "="*60)
    print("UPLOADING TEST FILE")
    print("="*60)
    
    try:
        service = build("drive", "v3", credentials=creds)
        
        # Create a small test file
        test_file = PROJECT_ROOT / "logs" / "test_upload.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(test_file, "w") as f:
            f.write(f"OptiMetrics test upload\nTimestamp: {__import__('datetime').datetime.now().isoformat()}\n")
        
        # Upload
        file_metadata = {
            "name": f"test_upload_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "parents": [SHARED_FOLDER_ID]
        }
        
        media = MediaFileUpload(str(test_file), mimetype="text/plain")
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name"
        ).execute()
        
        print(f"  [OK] Uploaded: {file.get('name')}")
        print(f"  File ID: {file.get('id')}")
        
        # Clean up test file
        test_file.unlink()
        
        return True
        
    except Exception as e:
        print(f"  [X] Upload failed: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("OPTIMETRICS GOOGLE DRIVE SETUP")
    print("="*60)
    print(f"\nShared Research Folder ID: {SHARED_FOLDER_ID}")
    print(f"Folder URL: https://drive.google.com/drive/folders/{SHARED_FOLDER_ID}")
    
    # Authenticate
    creds = authenticate()
    if not creds:
        print("\nSetup failed. Please create OAuth credentials and try again.")
        return
    
    # Test access
    if not test_upload(creds):
        print("\nCannot upload to shared folder. Please request edit access.")
        return
    
    # Try actual upload
    if upload_test_file(creds):
        print("\n" + "="*60)
        print("SETUP COMPLETE!")
        print("="*60)
        print("""
Your metrics will now be automatically uploaded to the shared folder.

To start collecting and uploading data:
    python src/hardware_logger.py

The logger will upload metrics every 5 minutes (configurable in config.yaml).
""")
    else:
        print("\n" + "="*60)
        print("SETUP INCOMPLETE")
        print("="*60)
        print("Upload test failed. Please check your permissions.")


if __name__ == "__main__":
    main()
