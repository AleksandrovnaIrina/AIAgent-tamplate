# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Shared Google OAuth credentials for Sheets integration."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SECRETS_DIR = Path(os.environ.get("GOOGLE_SECRETS_DIR", "/app/secrets"))
TOKEN_PATH = SECRETS_DIR / "google-token.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_svc_cache: dict = {}


def credentials() -> Credentials:
    if not TOKEN_PATH.is_file():
        raise RuntimeError(
            f"Google OAuth token missing: {TOKEN_PATH}. "
            "Run setup_gmail_auth.py to authorize."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise RuntimeError(
                    f"Google token refresh failed ({e}). "
                    "Re-run setup_gmail_auth.py to re-authorize."
                ) from e
            try:
                TOKEN_PATH.write_text(creds.to_json())
                TOKEN_PATH.chmod(0o600)
            except OSError:
                log.debug("Cannot persist refreshed token (read-only FS) — using in-memory creds")
            _svc_cache.clear()
        else:
            raise RuntimeError(
                f"Google OAuth token at {TOKEN_PATH} is invalid. "
                "Re-run setup_gmail_auth.py to re-authorize."
            )
    return creds


def service(name: str, version: str):
    key = f"{name}:{version}"
    if key not in _svc_cache:
        _svc_cache[key] = build(name, version, credentials=credentials(), cache_discovery=False)
    return _svc_cache[key]


def invalidate_cache() -> None:
    """Clear the service cache so the next call rebuilds with fresh credentials."""
    _svc_cache.clear()
