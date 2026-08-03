# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Drive upload helper for Sirius artifacts (PDF + banner PNGs).

Files land in SIRIUS_DRIVE_FOLDER_ID (or root if unset) and are marked
anyone:reader by default — Sirius's artifacts are meant to be shared.
"""
from __future__ import annotations

import logging
import mimetypes
import tempfile
from pathlib import Path
from typing import Optional

from googleapiclient.http import MediaFileUpload

from gauth import drive as _drive

log = logging.getLogger(__name__)


def upload(local_path: str, name: Optional[str] = None,
           folder_id: Optional[str] = None, mime: Optional[str] = None,
           public: bool = True) -> dict:
    p = Path(local_path)
    if not p.is_file():
        raise FileNotFoundError(f"upload source missing: {p}")
    body = {"name": name or p.name}
    if folder_id:
        body["parents"] = [folder_id]
    mt = mime or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    media = MediaFileUpload(str(p), mimetype=mt, resumable=True)
    svc = _drive()
    f = svc.files().create(
        body=body, media_body=media,
        fields="id, name, mimeType, size, webViewLink, webContentLink",
        supportsAllDrives=True,
    ).execute()
    if public:
        svc.permissions().create(
            fileId=f["id"],
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
        f = svc.files().get(
            fileId=f["id"],
            fields="id, name, mimeType, size, webViewLink, webContentLink",
            supportsAllDrives=True,
        ).execute()
    log.info("drive: uploaded %s → %s (%s)", p.name, f["id"], mt)
    return f


def upload_bytes(content: bytes, name: str, mime: str,
                 folder_id: Optional[str] = None, public: bool = True) -> dict:
    with tempfile.NamedTemporaryFile(suffix=Path(name).suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return upload(tmp_path, name=name, folder_id=folder_id, mime=mime, public=public)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
