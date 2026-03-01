"""
drive_upload.py — Upload files to Google Drive using a service account.
"""

import json
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_drive_service():
    """Build Drive service from service account JSON in env var."""
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if not sa_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT env var not set")

    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive", "v3", credentials=creds)


def upload_files(file_paths: list[Path], folder_id: str) -> list[str]:
    """
    Upload files to a specific Drive folder.
    Returns list of shareable links.
    """
    service = get_drive_service()
    links = []

    for path in file_paths:
        print(f"  Uploading {path.name}...", end=" ", flush=True)

        metadata = {
            "name": path.name,
            "parents": [folder_id],
        }
        media = MediaFileUpload(str(path), mimetype="image/png")

        file = service.files().create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        # Make it readable by anyone with the link
        service.permissions().create(
            fileId=file["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        links.append(file["webViewLink"])
        print(f"OK → {file['webViewLink']}")

    return links
