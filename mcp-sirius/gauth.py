# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Shared Google OAuth credentials for Drive uploads."""
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
    "https://www.googleapis.com/auth/calendar",
]

_svc_cache: dict = {}


def credentials() -> Credentials:
    if not TOKEN_PATH.is_file():
        raise RuntimeError(
            f"Google OAuth token missing: {TOKEN_PATH}. "
            "Run `./setup.sh --auth-google` on the host."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            try:
                TOKEN_PATH.write_text(creds.to_json())
                TOKEN_PATH.chmod(0o600)
            except OSError:
                log.debug("Cannot persist refreshed token (read-only FS) — using in-memory creds")
        else:
            raise RuntimeError(
                f"Google OAuth token at {TOKEN_PATH} is invalid and cannot be "
                "refreshed. Re-run `./setup.sh --auth-google`."
            )
    return creds


def service(name: str, version: str):
    key = f"{name}:{version}"
    if key not in _svc_cache:
        _svc_cache[key] = build(name, version, credentials=credentials(), cache_discovery=False)
    return _svc_cache[key]


def drive():
    return service("drive", "v3")
