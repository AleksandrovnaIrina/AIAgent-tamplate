# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Send Telegram messages via DB queue — scout-bot processes the queue using its persistent Telethon client."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import psycopg

log = logging.getLogger(__name__)

_DB_URL = os.environ.get("DATABASE_URL", "")
_POLL_INTERVAL = 1    # seconds between polls
_POLL_TIMEOUT = 30    # max seconds to wait for send_queue result


def _db() -> psycopg.Connection:
    if not _DB_URL:
        raise RuntimeError("DATABASE_URL not set — cannot queue Telegram message")
    return psycopg.connect(_DB_URL, autocommit=True)


def send_message(recipient: str, text: str) -> dict:
    """Send a Telegram message from Iryna's personal account.

    Inserts into send_queue; scout-bot delivers it via its persistent Telethon connection.

    Args:
      recipient: Telegram username (@username) or phone number (+380...)
      text: message text

    Returns: {ok, recipient}
    """
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO send_queue (recipient, text) VALUES (%s, %s) RETURNING id",
            (recipient, text),
        )
        row_id = cur.fetchone()[0]

    log.info("tg_sender: queued message to %s (queue id=%d)", recipient, row_id)

    deadline = time.time() + _POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(_POLL_INTERVAL)
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, result FROM send_queue WHERE id = %s", (row_id,)
            )
            row = cur.fetchone()
        if row and row[0] != "pending":
            status, result = row
            if status == "done":
                log.info("tg_sender: delivered to %s (id=%d)", recipient, row_id)
                return {"ok": True, "recipient": recipient}
            raise RuntimeError(f"Помилка відправки Telegram: {result}")

    raise RuntimeError(
        f"Час очікування відправки вийшов ({_POLL_TIMEOUT}s) — перевір чи запущений scout-bot"
    )


def get_sender_info() -> dict:
    """Return the Telegram API ID configured for sending (verification only)."""
    api_id = os.environ.get("TELEGRAM_API_ID", "")
    session_path = Path(os.environ.get("GOOGLE_SECRETS_DIR", "/app/secrets")) / "scout_sender.session"
    return {
        "api_id": api_id,
        "session_exists": session_path.exists(),
        "note": "Messages are sent via scout-bot's persistent Telethon connection",
    }
