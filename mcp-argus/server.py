# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Argus MCP server — Instagram competitor intelligence tools."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import psycopg
import yaml
from fastmcp import FastMCP

import sheets as _sheets

log = logging.getLogger("argus-mcp")
DATABASE_URL = os.environ["DATABASE_URL"]
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "3500"))
COMPETITORS_FILE = os.environ.get("COMPETITORS_FILE", "/app/competitors.yml")

mcp = FastMCP("argus")


def _conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)


# ── Competitor posts ──────────────────────────────────────────────────────────

@mcp.tool()
def get_competitor_posts(
    handle: Optional[str] = None,
    limit: int = 10,
    min_engagement: Optional[float] = None,
) -> list[dict]:
    """Query the Instagram competitor post archive.

    Args:
      handle: Instagram handle (e.g. 'honchar_yuliia'), or None for all
      limit: number of posts to return (default 10)
      min_engagement: filter by minimum engagement rate
    """
    where_parts = []
    params: list = []
    if handle:
        where_parts.append("competitor_handle = %s")
        params.append(handle)
    if min_engagement is not None:
        where_parts.append("engagement_rate >= %s")
        params.append(min_engagement)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    params.append(limit)

    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT post_id, competitor_handle, post_url, caption, transcript,
                       hook, likes, comments, views, engagement_rate, posted_at
                FROM scout_posts
                {where}
                ORDER BY posted_at DESC
                LIMIT %s""",
            params,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@mcp.tool()
def list_competitors() -> list[dict]:
    """List all monitored Instagram competitors from competitors.yml."""
    try:
        with open(COMPETITORS_FILE) as f:
            config = yaml.safe_load(f)
        return config.get("competitors", [])
    except FileNotFoundError:
        return []


@mcp.tool()
def add_competitor(handle: str, posts_per_run: int = 10) -> dict:
    """Add a new competitor to the monitoring list."""
    try:
        with open(COMPETITORS_FILE) as f:
            config = yaml.safe_load(f) or {"competitors": []}
        existing = [c["handle"] for c in config.get("competitors", [])]
        if handle in existing:
            return {"status": "already_exists", "handle": handle}
        config["competitors"].append({"handle": handle, "posts_per_run": posts_per_run})
        with open(COMPETITORS_FILE, "w") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        return {"status": "added", "handle": handle}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def trigger_scout_run() -> dict:
    """Trigger an immediate Instagram scout run (picks up within 30s)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bot_settings (key, value) VALUES ('scout_trigger', 'run') "
            "ON CONFLICT (key) DO UPDATE SET value = 'run'"
        )
    return {"status": "triggered", "message": "Скаут запущено ✅. Дайджест прийде в Telegram коли завершиться (10–30 хв)."}


# ── Google Sheets ─────────────────────────────────────────────────────────────

@mcp.tool()
def write_analysis(query: str, analysis: str) -> dict:
    """Save a competitor analysis to Google Sheets (Аналіз tab)."""
    try:
        _sheets.write_analysis(query, analysis)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def update_caption(post_url: str, caption: str) -> dict:
    """Update the caption for a post in Google Sheets (Reels tab)."""
    try:
        _sheets.update_caption(post_url, caption)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def write_carousel(
    topic: str,
    slides: list[str],
    caption: str,
    source_url: str = "",
) -> dict:
    """Save a carousel to Google Sheets."""
    try:
        _sheets.write_carousel(topic=topic, slides=slides, caption=caption, source_url=source_url)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT, path="/mcp")
