# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Notion integration — create / list / update lead magnet pages.

Env:
  NOTION_TOKEN          — integration token, owns the parent database
  NOTION_DATABASE_ID    — target DB for lead magnets
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from notion_client import Client

log = logging.getLogger(__name__)

NOTION_BLOCK_BATCH = 100

INLINE_RE = re.compile(
    r"(?<!!)\[(?P<lt>[^\]]+)\]\((?P<url>[^)]+)\)"
    r"|\*\*(?P<bold>[^*]+)\*\*"
    r"|\*(?P<italic>[^*]+)\*"
    r"|`(?P<code>[^`]+)`"
)
IMAGE_LINE_RE = re.compile(r"^\s*!\[(?P<alt>[^\]]*)\]\((?P<url>[^)]+)\)\s*$")


def _client() -> Client:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("NOTION_TOKEN must be set in .env")
    return Client(auth=token)


def _db_id() -> str:
    db = os.environ.get("NOTION_DATABASE_ID", "").strip()
    if not db:
        raise RuntimeError("NOTION_DATABASE_ID must be set in .env")
    return db


def parse_inline(text: str) -> list[dict]:
    parts: list[dict] = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            parts.append({"type": "text", "text": {"content": text[pos:m.start()]}})
        if m.group("url"):
            parts.append({
                "type": "text",
                "text": {"content": m.group("lt"), "link": {"url": m.group("url")}},
            })
        elif m.group("bold"):
            parts.append({
                "type": "text", "text": {"content": m.group("bold")},
                "annotations": {"bold": True},
            })
        elif m.group("italic"):
            parts.append({
                "type": "text", "text": {"content": m.group("italic")},
                "annotations": {"italic": True},
            })
        elif m.group("code"):
            parts.append({
                "type": "text", "text": {"content": m.group("code")},
                "annotations": {"code": True},
            })
        pos = m.end()
    if pos < len(text):
        parts.append({"type": "text", "text": {"content": text[pos:]}})
    if not parts:
        parts = [{"type": "text", "text": {"content": text}}]
    return parts


def _is_block_starter(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith(("- ", "> ", "```")):
        return True
    if re.match(r"^#{1,3}\s+", s) or re.match(r"^\d+\.\s+", s):
        return True
    if re.match(r"^---+$", s) or IMAGE_LINE_RE.match(s):
        return True
    return False


def md_to_blocks(md: str) -> list[dict]:
    blocks: list[dict] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = IMAGE_LINE_RE.match(line)
        if m:
            url = m.group("url").strip()
            blocks.append({
                "object": "block", "type": "image",
                "image": {
                    "type": "external", "external": {"url": url},
                    "caption": parse_inline((m.group("alt") or "").strip())
                                if (m.group("alt") or "").strip() else [],
                },
            })
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            blocks.append({
                "object": "block",
                "type": f"heading_{level}",
                f"heading_{level}": {"rich_text": parse_inline(m.group(2))},
            })
            i += 1
            continue
        if line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            blocks.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": lang,
                },
            })
            continue
        if line.lstrip().startswith("- "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_inline(line.lstrip()[2:])},
            })
            i += 1
            continue
        if re.match(r"^\d+\.\s+", line):
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": parse_inline(re.sub(r"^\d+\.\s+", "", line))},
            })
            i += 1
            continue
        if line.startswith("> "):
            content = line[2:]
            if content.startswith("💡"):
                blocks.append({
                    "object": "block", "type": "callout",
                    "callout": {
                        "rich_text": parse_inline(content[len("💡"):].lstrip()),
                        "icon": {"type": "emoji", "emoji": "💡"},
                        "color": "blue_background",
                    },
                })
            else:
                blocks.append({
                    "object": "block", "type": "quote",
                    "quote": {"rich_text": parse_inline(content), "color": "brown_background"},
                })
            i += 1
            continue
        if re.match(r"^---+$", line):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue
        para = [line]
        i += 1
        while i < len(lines) and not _is_block_starter(lines[i]):
            para.append(lines[i])
            i += 1
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": parse_inline(" ".join(para))},
        })
    return blocks


def create_lead_magnet(title: str, content: str,
                       topic: Optional[str] = None,
                       reference: Optional[str] = None,
                       reel_url: Optional[str] = None,
                       status: str = "Draft",
                       cover_url: Optional[str] = None) -> dict:
    client = _client()
    blocks = md_to_blocks(content) if content.strip() else []
    properties = {
        "Name": {"title": [{"type": "text", "text": {"content": title}}]},
    }
    if status:
        properties["Status"] = {"status": {"name": status}}
    if topic:
        properties["Topic"] = {"rich_text": [{"type": "text", "text": {"content": topic}}]}
    if reference:
        properties["Reference"] = {"url": reference}
    if reel_url:
        properties["Reel"] = {"url": reel_url}

    create_kwargs = {
        "parent": {"database_id": _db_id()},
        "properties": properties,
        "children": blocks[:NOTION_BLOCK_BATCH],
    }
    if cover_url:
        create_kwargs["cover"] = {"type": "external", "external": {"url": cover_url}}

    page = client.pages.create(**create_kwargs)
    for off in range(NOTION_BLOCK_BATCH, len(blocks), NOTION_BLOCK_BATCH):
        client.blocks.children.append(
            block_id=page["id"], children=blocks[off:off + NOTION_BLOCK_BATCH],
        )
    log.info("notion: created page %s '%s' blocks=%d", page["id"], title, len(blocks))
    return {
        "page_id": page["id"],
        "url": page.get("url", ""),
        "title": title,
        "blocks": len(blocks),
    }


def _resolve_data_source_id(client: Client, db_id: str) -> str:
    db = client.databases.retrieve(database_id=db_id)
    sources = db.get("data_sources", [])
    return sources[0]["id"] if sources else db_id


def list_lead_magnets(status: Optional[str] = None) -> list[dict]:
    client = _client()
    ds_id = _resolve_data_source_id(client, _db_id())
    body = {"data_source_id": ds_id, "page_size": 100}
    if status:
        body["filter"] = {"property": "Status", "status": {"equals": status}}
    result = client.data_sources.query(**body)
    rows = []
    for p in result.get("results", []):
        props = p.get("properties", {})
        title = "".join(t.get("plain_text", "")
                        for t in props.get("Name", {}).get("title", []))
        s = props.get("Status", {}).get("status", {}) or {}
        topic = "".join(t.get("plain_text", "")
                        for t in props.get("Topic", {}).get("rich_text", []))
        rows.append({
            "page_id": p.get("id"),
            "url": p.get("url", ""),
            "title": title,
            "status": s.get("name", ""),
            "topic": topic,
            "created": p.get("created_time", ""),
        })
    return rows


def update_lead_magnet(page_id: str,
                       status: Optional[str] = None,
                       title: Optional[str] = None,
                       topic: Optional[str] = None,
                       reference: Optional[str] = None) -> dict:
    client = _client()
    properties = {}
    if status:
        properties["Status"] = {"status": {"name": status}}
    if title:
        properties["Name"] = {"title": [{"type": "text", "text": {"content": title}}]}
    if topic is not None:
        properties["Topic"] = {"rich_text": [{"type": "text", "text": {"content": topic}}]}
    if reference is not None:
        properties["Reference"] = {"url": reference or None}
    if not properties:
        return {"ok": False, "reason": "no fields to update"}
    page = client.pages.update(page_id=page_id, properties=properties)
    return {"ok": True, "page_id": page["id"], "url": page.get("url", "")}
