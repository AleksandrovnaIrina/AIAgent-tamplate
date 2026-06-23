"""Per-chat Claude session + last-used agent persistence."""

import os
from typing import Optional

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]


def get_session(chat_id: int) -> tuple[Optional[str], Optional[str]]:
    """Return (claude_session_id, last_agent) for this chat."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT claude_session_id, last_agent FROM chat_sessions WHERE chat_id = %s",
            (chat_id,),
        )
        row = cur.fetchone()
        if row:
            return row[0], row[1]
        return None, None


def save_session(chat_id: int, claude_session_id: str, agent: str) -> None:
    """Upsert session_id and last agent for this chat."""
    if not claude_session_id:
        return
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_sessions (chat_id, claude_session_id, last_agent, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (chat_id) DO UPDATE
              SET claude_session_id = EXCLUDED.claude_session_id,
                  last_agent = EXCLUDED.last_agent,
                  updated_at = NOW()
            """,
            (chat_id, claude_session_id, agent),
        )


def clear_session(chat_id: int) -> None:
    """Forget the session for this chat (used by /new)."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_sessions WHERE chat_id = %s", (chat_id,))
