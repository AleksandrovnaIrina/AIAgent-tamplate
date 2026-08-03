# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Sirius MCP server — Notion, PDF, Banner tools.

FastMCP server on port 3400, exposed to the sirius-bot container only.
Memory tools live in the shared mcp-memory server.

Tools:
  Notion:
    create_lead_magnet(title, content, ...)
    list_lead_magnets(status=None)
    update_lead_magnet(page_id, status=None, title=None, topic=None)
  PDF:
    list_pdf_templates()
    render_pdf_from_template(template_name, data, name, ...)
    render_pdf(html, name, page_format='A4', landscape=False, margin_mm=None)
  Banner:
    list_templates()
    render_banner(template_name, data, name=None, width=1080, height=1350)
    Story banners: use render_banner with height=1920 and *_story templates.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastmcp import FastMCP

import banner as _banner
import fetch as _fetch
import notion as _notion
import pdf as _pdf
import search as _search
import sheets as _sheets
import youtube as _youtube

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("sirius-mcp")

HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "3400"))

mcp = FastMCP("sirius")


# ---- Notion ----

@mcp.tool()
def create_lead_magnet(
    title: str,
    content: str,
    topic: Optional[str] = None,
    reference: Optional[str] = None,
    reel_url: Optional[str] = None,
    status: str = "Draft",
    cover_url: Optional[str] = None,
) -> dict:
    """Create a new lead-magnet page in Notion.

    Args:
      title: Page name
      content: Markdown body (headings, lists, quotes, code, images, callouts).
               Use `> 💡 text` for blue-bg insight callouts; `> text` for brown quotes.
      topic: Optional Topic property
      reference: Optional Reference URL property
      reel_url: Optional Reel URL property
      status: Draft / Ready / Published / old
      cover_url: External URL for the page cover banner

    Returns: {page_id, url, title, blocks}.
    """
    return _notion.create_lead_magnet(
        title=title, content=content, topic=topic, reference=reference,
        reel_url=reel_url, status=status, cover_url=cover_url,
    )


@mcp.tool()
def list_lead_magnets(status: Optional[str] = None) -> list[dict]:
    """List lead-magnet pages, optionally filtered by status
    (Draft / Ready / Published / old)."""
    return _notion.list_lead_magnets(status=status)


@mcp.tool()
def update_lead_magnet(
    page_id: str,
    status: Optional[str] = None,
    title: Optional[str] = None,
    topic: Optional[str] = None,
    reference: Optional[str] = None,
) -> dict:
    """Update a lead-magnet page's properties. Pass only fields to change."""
    return _notion.update_lead_magnet(
        page_id=page_id, status=status, title=title, topic=topic, reference=reference,
    )


# ---- PDF ----

@mcp.tool()
def list_pdf_templates() -> list[dict]:
    """List available PDF templates with their data-schema docstrings.
    Templates: lead_magnet (branded guide), checklist (printable checklist).
    Call this to see what variables each template accepts.
    """
    return _pdf.list_pdf_templates()


@mcp.tool()
def render_pdf_from_template(
    template_name: str,
    data: dict,
    name: str,
    page_format: str = "A4",
    landscape: bool = False,
    margin_mm: Optional[list[int]] = None,
) -> dict:
    """Render a PDF from a named template (lead_magnet / checklist) and upload to Drive.

    Args:
      template_name: 'lead_magnet' or 'checklist'. See list_pdf_templates() for schemas.
      data: dict of variables matching the template schema
      name: output filename for Drive (e.g. "hr-checklist"). .pdf appended automatically.
      page_format: A4 / Letter
      landscape: True for landscape
      margin_mm: [top, right, bottom, left] in mm. Defaults to [20,15,20,15].

    Returns: {drive_url, file_id, size_bytes, name}.
    """
    return _pdf.render_pdf_from_template(
        template_name=template_name, data=data, name=name,
        page_format=page_format, landscape=landscape, margin_mm=margin_mm,
    )


@mcp.tool()
def render_pdf(
    html: str,
    name: str,
    page_format: str = "A4",
    landscape: bool = False,
    margin_mm: Optional[list[int]] = None,
) -> dict:
    """Render a self-contained HTML document to PDF (via Chromium) and upload to Drive.

    The HTML should be a full <!doctype html>... document. Inline CSS or
    CDN-loaded fonts (Google Fonts) are fine. Use `@page { size: A4; margin: 20mm; }`
    to fine-tune page setup; `break-inside: avoid` to keep sections together.

    Args:
      html: full HTML
      name: filename for Drive (e.g. "linkedin-strategy.pdf"). .pdf appended automatically.
      page_format: A4 / Letter / Legal / Tabloid / Ledger
      landscape: True for landscape orientation
      margin_mm: [top, right, bottom, left] in mm. Defaults to [20,15,20,15].

    Returns: {drive_url, file_id, size_bytes, name}.
    """
    return _pdf.render_pdf(
        html=html, name=name,
        page_format=page_format, landscape=landscape, margin_mm=margin_mm,
    )


# ---- Banner ----

@mcp.tool()
def list_templates() -> list[dict]:
    """List available banner templates with their data-schema docstrings.
    Call this if you're unsure which template to use or what fields to pass.
    """
    return _banner.list_templates()


@mcp.tool()
def render_banner(
    template_name: str,
    data: dict,
    name: Optional[str] = None,
    width: int = 1080,
    height: int = 1350,
) -> dict:
    """Render a banner template to PNG (via Chromium screenshot) and upload to Drive.

    Args:
      template_name: stem of a template, e.g. 'quote_card' / 'tip_list' / 'cta_card'.
                     See list_templates() for the full list + variable schemas.
      data: dict of variables matching the template's schema
      name: output filename (auto: <template>-<timestamp>.png)
      width: viewport pixels. 1080 = IG/LinkedIn width.
      height: viewport pixels. 1350 (portrait IG, default) / 1920 (story) / 1080 (square)

    Returns: {drive_url, file_id, name}.
    """
    return _banner.render_banner(
        template_name=template_name, data=data,
        name=name, width=width, height=height,
    )


# ---- Research sheet ----

@mcp.tool()
def save_research_article(
    title: str,
    url: str,
    summary: str,
    topic: str = "",
    source: str = "",
) -> dict:
    """Save a research article to the Sirius Research Google Sheet.

    Always call this after web_search when Iryna asks to find articles or research a topic.

    Args:
      title: article title
      url: article URL
      summary: 1-2 sentence summary in Ukrainian
      topic: content topic or theme (e.g. "сорсинг", "AI в HR")
      source: publication name or domain

    Returns: {sheet_url, updated_range, title}.
    """
    return _sheets.save_article(title=title, url=url, summary=summary, topic=topic, source=source)


# ---- YouTube ----

@mcp.tool()
def get_youtube_transcript(url: str) -> dict:
    """Fetch the transcript and metadata of a YouTube video.

    Works with youtube.com/watch, youtu.be, and Shorts links.
    Tries Ukrainian → English → Russian → any available language.
    No API key required.

    Args:
      url: YouTube video URL

    Returns: {video_id, url, title, author, transcript, word_count, truncated}.
    After getting the transcript — summarise it and draft a LinkedIn/Instagram post
    in Iryna's voice based on the key insights.
    """
    return _youtube.get_transcript(url)


# ---- Web search ----

@mcp.tool()
def web_search(
    query: str,
    max_results: int = 8,
    sites: Optional[list[str]] = None,
) -> list[dict]:
    """Search the web via DuckDuckGo. Always search in English for HR/recruiting topics.

    Default behaviour: worldwide English results (region=wt-wt).
    Use `sites` to restrict to specific domains.

    Preferred HR sources (use via sites=[...]):
      linkedin.com, hbr.org, shrm.org, ere.net, medium.com, forbes.com,
      recruitingdaily.com, tlnt.com, hrexaminer.com, workable.com

    Args:
      query: search query — always write in English for best results
      max_results: number of results (default 8, max 15)
      sites: optional list of domains to search within, e.g. ["linkedin.com", "hbr.org"]

    Returns: list of {title, url, snippet}.
    """
    return _search.web_search(query, max_results=min(max_results, 15), sites=sites)


# ---- URL reader ----

@mcp.tool()
def read_url(url: str) -> dict:
    """Fetch a web page and return its readable text content (max 8000 chars).

    Use this to read articles, blog posts, LinkedIn posts, or any public URL
    that Iryna shares for research or content inspiration.

    Args:
      url: public URL to fetch

    Returns: {url, status_code, text, truncated}.
    """
    return _fetch.read_url(url)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT, path="/mcp")
