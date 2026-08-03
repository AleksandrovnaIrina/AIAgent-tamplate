# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Fetch a URL and return its readable text content."""
from __future__ import annotations

import logging

import html2text
import httpx

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; ScoutBot/1.0)"


def read_url(url: str, max_chars: int = 10000) -> dict:
    with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        resp = client.get(url)
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0
    text = h.handle(resp.text).strip()
    truncated = len(text) > max_chars
    log.info("read_url: %s → %d chars (truncated=%s)", url, len(text), truncated)
    return {
        "url": url,
        "status_code": resp.status_code,
        "text": text[:max_chars],
        "truncated": truncated,
    }
