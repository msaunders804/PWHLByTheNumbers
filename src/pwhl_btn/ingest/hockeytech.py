"""
Shared HockeyTech API settings.

The public feed key is intentionally configurable so jobs can run with a
rotated key without editing code.
"""

from __future__ import annotations

import os

API_BASE = os.environ.get(
    "PWHL_HOCKEYTECH_API_BASE",
    "https://lscluster.hockeytech.com/feed/index.php",
)
API_KEY = os.environ.get("PWHL_HOCKEYTECH_API_KEY", "446521baf8c38984")
CLIENT_CODE = os.environ.get("PWHL_HOCKEYTECH_CLIENT_CODE", "pwhl")


def with_auth(params: dict) -> dict:
    """Return a copy of params with HockeyTech auth/query defaults attached."""
    return {
        **params,
        "key": API_KEY,
        "client_code": CLIENT_CODE,
        "fmt": "json",
    }
