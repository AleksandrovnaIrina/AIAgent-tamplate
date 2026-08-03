# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Per-Telegram-chat Claude session persistence."""

import os
from typing import Optional

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]


def get_session_id(chat_id: int) -> Optional[str]:
    """Return the Claude session_id for this chat, or None if no prior session."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT claude_session_id FROM chat_sessions WHERE chat_id = %s",
            (chat_id,),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def save_session_id(chat_id: int, claude_session_id: str) -> None:
    """Upsert the Claude session_id for this chat."""
    if not claude_session_id:
        return
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_sessions (chat_id, claude_session_id, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (chat_id) DO UPDATE
              SET claude_session_id = EXCLUDED.claude_session_id,
                  updated_at = NOW()
            """,
            (chat_id, claude_session_id),
        )


def clear_session(chat_id: int) -> None:
    """Forget the Claude session for this chat (used by /new)."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_sessions WHERE chat_id = %s", (chat_id,))
