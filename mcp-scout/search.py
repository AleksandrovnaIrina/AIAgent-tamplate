# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Web search via DuckDuckGo — recruiting-focused sources."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

RECRUITING_SOURCES = [
    "linkedin.com",
    "github.com",
    "glassdoor.com",
    "levels.fyi",
    "builtin.com",
    "wellfound.com",
    "angel.co",
    "djinni.co",
    "dou.ua",
    "robota.ua",
    "hh.ru",
]


def web_search(
    query: str,
    max_results: int = 8,
    sites: list[str] | None = None,
    region: str = "wt-wt",
) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    if sites:
        site_filter = " OR ".join(f"site:{s}" for s in sites)
        full_query = f"({query}) ({site_filter})"
    else:
        full_query = query

    with DDGS() as ddgs:
        results = list(ddgs.text(
            full_query,
            max_results=max_results,
            region=region,
        ))

    out = [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in results
    ]
    log.info("web_search: '%s' → %d results", full_query, len(out))
    return out
