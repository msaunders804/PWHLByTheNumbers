#!/usr/bin/env python3
"""
Cloud Storage Uploader for PWHL Visualizations
Auto-uploads visualizations to Google Drive for easy mobile access
"""

import os
import sys
from pathlib import Path
import mimetypes

# Google Drive setup
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import GOOGLE_DRIVE_FOLDER_ID, GOOGLE_DRIVE_ENABLED

# Google Drive scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GoogleDriveUploader:
    """Upload files to Google Drive"""

    def __init__(self):
        self.service = None
        self.folder_id = GOOGLE_DRIVE_FOLDER_ID
        self.enabled = GOOGLE_DRIVE_ENABLED and GOOGLE_DRIVE_AVAILABLE

        if not GOOGLE_DRIVE_AVAILABLE:
            print("[WARN]  Google Drive libraries not installed")
            print("   Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return

        if not self.enabled:
            print("[WARN]  Google Drive upload disabled in config")
            return

        # Initialize service
        self._initialize_service()

    def _initialize_service(self):
        """Initialize Google Drive service with authentication"""
        creds = None
        token_path = project_root / 'credentials' / 'google_drive_token.json'
        credentials_path = project_root / 'credentials' / 'google_drive_credentials.json'

        # Check for existing token
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            except Exception as e:
                print(f"[WARN]  Error loading token: {e}")

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[WARN]  Error refreshing token: {e}")
                    creds = None

            if not creds:
                if not credentials_path.exists():
                    print("[ERROR] Google Drive credentials not found!")
                    print(f"   Please place credentials file at: {credentials_path}")
                    print("   See setup instructions in README")
                    self.enabled = False
                    return

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"[ERROR] Authentication failed: {e}")
                    self.enabled = False
                    return

            # Save credentials
            token_path.parent.mkdir(exist_ok=True)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        try:
            self.service = build('drive', 'v3', credentials=creds)
            print("[OK] Google Drive service initialized")
        except Exception as e:
            print(f"[ERROR] Failed to build Drive service: {e}")
            self.enabled = False

    def upload_file(self, file_path, folder_id=None, description=None):
        """
        Upload a file to Google Drive

        Args:
            file_path: Path to file to upload
            folder_id: Google Drive folder ID (uses default if not specified)
            description: Optional file description

        Returns:
            dict: Upload result with success status and file info
        """
        if not self.enabled or not self.service:
            return {
                'success': False,
                'error': 'Google Drive upload not enabled or configured'
            }

        file_path = Path(file_path)

        if not file_path.exists():
            return {
                'success': False,
                'error': f'File not found: {file_path}'
            }

        # Use default folder if not specified
        if not folder_id:
            folder_id = self.folder_id

        try:
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = 'application/octet-stream'

            # Prepare file metadata
            file_metadata = {
                'name': file_path.name,
                'parents': [folder_id] if folder_id else []
            }

            if description:
                file_metadata['description'] = description

            # Upload file
            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=True
            )

            # Check if file already exists
            existing_file = self._find_file_by_name(file_path.name, folder_id)

            if existing_file:
                # Update existing file
                file = self.service.files().update(
                    fileId=existing_file['id'],
                    media_body=media,
                    fields='id, name, webViewLink, webContentLink'
                ).execute()
                action = "Updated"
            else:
                # Create new file
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, webViewLink, webContentLink'
                ).execute()
                action = "Uploaded"

            return {
                'success': True,
                'action': action,
                'file_id': file.get('id'),
                'file_name': file.get('name'),
                'web_view_link': file.get('webViewLink'),
                'web_content_link': file.get('webContentLink')
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _find_file_by_name(self, filename, folder_id=None):
        """Find a file by name in a folder"""
        try:
            query = f"name='{filename}' and trashed=false"
            if folder_id:
                query += f" and '{folder_id}' in parents"

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()

            files = results.get('files', [])
            return files[0] if files else None

        except Exception:
            return None

    def upload_latest_visualization(self, viz_type='standings'):
        """
        Upload the most recent visualization of a specific type

        Args:
            viz_type: Type of visualization (e.g., 'standings', 'leaders', etc.)

        Returns:
            dict: Upload result
        """
        viz_dir = project_root / 'outputs' / 'visualizations'

        # Find latest visualization file
        pattern = f'pwhl_{viz_type}_*.png'
        viz_files = list(viz_dir.glob(pattern))

        if not viz_files:
            return {
                'success': False,
                'error': f'No {viz_type} visualizations found'
            }

        # Get most recent file
        latest_file = max(viz_files, key=lambda p: p.stat().st_mtime)

        # Upload with description
        description = f'PWHL {viz_type.title()} visualization - {latest_file.stem}'

        print(f"\n[UPLOAD] Uploading {latest_file.name} to Google Drive...")
        result = self.upload_file(latest_file, description=description)

        if result['success']:
            print(f"[OK] {result['action']}: {result['file_name']}")
            print(f"[LINK] View: {result['web_view_link']}")
        else:
            print(f"[ERROR] Upload failed: {result['error']}")

        return result


def upload_visualization(file_path=None, viz_type=None):
    """
    Convenience function to upload a visualization

    Args:
        file_path: Specific file to upload (optional)
        viz_type: Type of viz to find latest (optional, used if file_path not provided)

    Returns:
        dict: Upload result
    """
    uploader = GoogleDriveUploader()

    if not uploader.enabled:
        return {'success': False, 'error': 'Google Drive not enabled'}

    if file_path:
        return uploader.upload_file(file_path)
    elif viz_type:
        return uploader.upload_latest_visualization(viz_type)
    else:
        return {'success': False, 'error': 'Must provide file_path or viz_type'}


def main():
    """Test the uploader"""
    import argparse

    parser = argparse.ArgumentParser(description='Upload visualization to Google Drive')
    parser.add_argument('--file', type=str, help='Specific file to upload')
    parser.add_argument('--type', type=str, default='standings',
                       help='Type of visualization to upload (default: standings)')

    args = parser.parse_args()

    print("="*60)
    print("GOOGLE DRIVE UPLOADER")
    print("="*60)

    if args.file:
        result = upload_visualization(file_path=args.file)
    else:
        result = upload_visualization(viz_type=args.type)

    if result['success']:
        print("\n[OK] Upload successful!")
    else:
        print(f"\n[ERROR] Upload failed: {result['error']}")


if __name__ == "__main__":
    main()
