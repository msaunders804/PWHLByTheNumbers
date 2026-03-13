"""
drive_upload.py — Upload files to Google Drive using OAuth refresh token.
Credentials come from environment variables (GitHub Secrets).
"""

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_drive_service():
    """Build Drive service from OAuth credentials in env vars."""
    client_id     = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or GOOGLE_REFRESH_TOKEN")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )

    # Refresh to get a valid access token
    creds.refresh(Request())
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

        # Make readable by anyone with the link
        service.permissions().create(
            fileId=file["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        links.append(file["webViewLink"])
        print(f"OK → {file['webViewLink']}")

    return links
