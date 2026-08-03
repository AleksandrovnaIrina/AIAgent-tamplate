# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Per-chat, per-agent Claude session persistence."""

import os
from typing import Optional

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]

_MIGRATE = """
CREATE TABLE IF NOT EXISTS agent_sessions (
    chat_id   BIGINT NOT NULL,
    agent     TEXT   NOT NULL,
    session_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, agent)
);
"""


def _ensure_table() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(_MIGRATE)


_ensure_table()


def get_session(chat_id: int, agent: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Return (claude_session_id, last_agent) for this chat.

    If agent is given, return that agent's session.
    Otherwise return the most recently used agent + session.
    """
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        if agent:
            row = conn.execute(
                "SELECT session_id FROM agent_sessions WHERE chat_id=%s AND agent=%s",
                (chat_id, agent),
            ).fetchone()
            # Also get last_agent from old table for routing
            last = conn.execute(
                "SELECT last_agent FROM chat_sessions WHERE chat_id=%s", (chat_id,)
            ).fetchone()
            return (row[0] if row else None), (last[0] if last else None)
        else:
            last = conn.execute(
                "SELECT last_agent FROM chat_sessions WHERE chat_id=%s", (chat_id,)
            ).fetchone()
            last_agent = last[0] if last else None
            if last_agent:
                row = conn.execute(
                    "SELECT session_id FROM agent_sessions WHERE chat_id=%s AND agent=%s",
                    (chat_id, last_agent),
                ).fetchone()
                return (row[0] if row else None), last_agent
            return None, None


def save_session(chat_id: int, claude_session_id: str, agent: str) -> None:
    """Save session_id per agent and update last_agent."""
    if not claude_session_id:
        return
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        # Save per-agent session
        conn.execute(
            """INSERT INTO agent_sessions (chat_id, agent, session_id, updated_at)
               VALUES (%s, %s, %s, NOW())
               ON CONFLICT (chat_id, agent) DO UPDATE
                 SET session_id=EXCLUDED.session_id, updated_at=NOW()""",
            (chat_id, agent, claude_session_id),
        )
        # Update last_agent in old table (keep for compatibility)
        conn.execute(
            """INSERT INTO chat_sessions (chat_id, claude_session_id, last_agent, updated_at)
               VALUES (%s, %s, %s, NOW())
               ON CONFLICT (chat_id) DO UPDATE
                 SET claude_session_id=EXCLUDED.claude_session_id,
                     last_agent=EXCLUDED.last_agent, updated_at=NOW()""",
            (chat_id, claude_session_id, agent),
        )


def clear_session(chat_id: int) -> None:
    """Clear all sessions for this chat (/new command)."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("DELETE FROM agent_sessions WHERE chat_id=%s", (chat_id,))
        conn.execute("DELETE FROM chat_sessions WHERE chat_id=%s", (chat_id,))
