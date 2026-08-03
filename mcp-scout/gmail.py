# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Gmail integration — read and summarize recent emails."""
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from typing import Optional

import gauth

log = logging.getLogger(__name__)

_SKIP_SENDERS = re.compile(
    r"(no-reply|noreply|donotreply|notifications?@|mailer@|newsletter@"
    r"|support@|info@|hello@|admin@|bot@|automated@)",
    re.IGNORECASE,
)


def _svc():
    return gauth.service("gmail", "v1")


def _decode_body(part: dict) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_text(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        return _decode_body(payload)
    if mime == "text/html":
        html = _decode_body(payload)
        # Strip HTML tags
        return re.sub(r"<[^>]+>", " ", html)
    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _extract_text(part)
            if text.strip():
                return text
    return ""


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def get_recent_emails(
    hours: int = 24,
    max_emails: int = 40,
    skip_automated: bool = True,
) -> list[dict]:
    """Fetch recent emails from Gmail INBOX.

    Args:
      hours: how many hours back to look (default 24)
      max_emails: max emails to return (default 40)
      skip_automated: skip newsletters, no-reply senders (default True)

    Returns: list of {subject, from, date, snippet, body_preview, message_id, thread_id}
    """
    svc = _svc()
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    query = f"in:inbox after:{since} -in:spam -in:trash"

    result = svc.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_emails,
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        return []

    emails = []
    for msg in messages:
        try:
            full = svc.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full",
            ).execute()
        except Exception as e:
            log.warning("gmail: failed to fetch message %s: %s", msg["id"], e)
            continue

        headers = full.get("payload", {}).get("headers", [])
        sender = _header(headers, "from")
        subject = _header(headers, "subject") or "(no subject)"
        date_str = _header(headers, "date")
        snippet = full.get("snippet", "")
        body = _extract_text(full.get("payload", {}))

        if skip_automated and _SKIP_SENDERS.search(sender):
            continue

        emails.append({
            "message_id": full["id"],
            "thread_id": full.get("threadId", ""),
            "subject": subject,
            "from": sender,
            "date": date_str,
            "snippet": snippet[:200],
            "body_preview": body[:500].strip(),
        })

    log.info("gmail: fetched %d emails (hours=%d)", len(emails), hours)
    return emails
