"""
get_refresh_token.py — One-time script to get a Google OAuth refresh token.
Run this once locally, then store the output as GitHub Secrets.

Usage:
    python get_refresh_token.py
"""

import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Look for credentials file
creds_path = Path("oauth_credentials.json")
if not creds_path.exists():
    print("ERROR: oauth_credentials.json not found in current directory")
    print("Download it from console.cloud.google.com → APIs & Services → Credentials")
    exit(1)

print("Opening browser for Google authorization...")
print("Sign in with your personal Google account and allow Drive access.\n")

flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
creds = flow.run_local_server(port=0)

print("\n✅ Authorization successful!\n")
print("=" * 60)
print("Add these as GitHub Secrets:\n")
print(f"GOOGLE_CLIENT_ID:\n{creds.client_id}\n")
print(f"GOOGLE_CLIENT_SECRET:\n{creds.client_secret}\n")
print(f"GOOGLE_REFRESH_TOKEN:\n{creds.refresh_token}\n")
print("=" * 60)

# Also save to a local file for reference
output = {
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "refresh_token": creds.refresh_token,
}
Path("oauth_tokens.json").write_text(json.dumps(output, indent=2))
print("\nAlso saved to oauth_tokens.json (DO NOT commit this file!)")