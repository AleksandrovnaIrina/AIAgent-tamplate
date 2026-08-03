# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""
LumysAgent memory MCP server.

Generic conversational memory backed by Postgres FTS. Three tools:
  - save_memory(text, tags?)
  - recall_memories(query, limit?)
  - list_memories(tags?, since?, limit?)
"""

import os
from datetime import datetime
from typing import Optional

import psycopg
from fastmcp import FastMCP

DATABASE_URL = os.environ["DATABASE_URL"]
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "3100"))

mcp = FastMCP("lumys-memory")


def _conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)


@mcp.tool()
def save_memory(text: str, tags: Optional[list[str]] = None) -> dict:
    """Save a note to long-term memory. Use for: candidate insights, vacancy context,
    Irina's preferences, sourcing patterns, market observations."""
    tags = tags or []
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO memories (text, tags) VALUES (%s, %s) RETURNING id, created_at",
            (text, tags),
        )
        row = cur.fetchone()
    return {"id": row[0], "created_at": row[1].isoformat()}


@mcp.tool()
def recall_memories(query: str, limit: int = 10) -> list[dict]:
    """Search saved memories by relevance to the query (Postgres FTS).
    Use before answering questions about vacancies, candidates, or preferences."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, text, tags, created_at,
                   ts_rank(text_search, plainto_tsquery('simple', %s)) AS rank
            FROM memories
            WHERE text_search @@ plainto_tsquery('simple', %s)
            ORDER BY rank DESC, created_at DESC
            LIMIT %s
            """,
            (query, query, limit),
        )
        return [
            {"id": r[0], "text": r[1], "tags": r[2], "created_at": r[3].isoformat()}
            for r in cur.fetchall()
        ]


@mcp.tool()
def list_memories(
    tags: Optional[list[str]] = None,
    since: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List recent memories, optionally filtered by tags and/or date (ISO 8601)."""
    where = []
    params: list = []
    if tags:
        where.append("tags && %s")
        params.append(tags)
    if since:
        where.append("created_at >= %s")
        params.append(datetime.fromisoformat(since))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, text, tags, created_at
            FROM memories
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            params,
        )
        return [
            {"id": r[0], "text": r[1], "tags": r[2], "created_at": r[3].isoformat()}
            for r in cur.fetchall()
        ]


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
