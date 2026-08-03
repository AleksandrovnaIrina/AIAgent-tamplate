# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""LinkedIn X-Ray candidate sourcing via DuckDuckGo."""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_LOCATION_RE = re.compile(r"[-–|·•]\s*([^·•\-–]+(?:,\s*[^·•\-–]+)*)\s*$")


def _build_queries(position: str, location: str, keywords: list[str] | None = None) -> list[str]:
    base = f'site:linkedin.com/in "{position}" "{location}"'
    if not keywords:
        return [base]
    pairs = [f'"{kw}"' for kw in keywords[:6]]
    extra = [f'{base} {kw}' for kw in pairs[:3]]
    return [base] + extra


def _ddg_search(query: str, max_results: int = 10) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def _parse_item(r: dict, position: str, location: str) -> dict | None:
    url: str = r.get("href", "") or r.get("link", "") or r.get("url", "")
    if "linkedin.com/in/" not in url:
        return None

    title: str = r.get("title", "")
    snippet: str = r.get("body", "") or r.get("snippet", "")

    parts = [p.strip() for p in re.split(r"\s[-–|]\s", title)]
    full_name = re.sub(r"\s*\|\s*LinkedIn$", "", parts[0], flags=re.IGNORECASE).strip()
    headline = parts[1] if len(parts) > 1 else ""
    company = re.sub(r"\s*\|\s*LinkedIn$", "", parts[2], flags=re.IGNORECASE).strip() if len(parts) > 2 else ""

    loc_match = _LOCATION_RE.search(snippet)
    inferred_location = loc_match.group(1).strip() if loc_match else location

    return {
        "full_name": full_name,
        "url": url,
        "headline": headline,
        "company": company,
        "location": inferred_location,
        "snippet": snippet[:300],
    }


def find_linkedin_candidates(
    position: str,
    location: str,
    keywords: list[str] | None = None,
    max_results: int = 20,
) -> list[dict]:
    """Search LinkedIn profiles via DuckDuckGo X-Ray."""
    queries = _build_queries(position, location, keywords)
    seen: set[str] = set()
    candidates: list[dict] = []

    for query in queries:
        if len(candidates) >= max_results:
            break
        log.info("DDG X-Ray: %s", query)
        try:
            results = _ddg_search(query, max_results=10)
        except Exception as exc:
            log.warning("DDG search failed: %s", exc)
            continue

        for r in results:
            c = _parse_item(r, position, location)
            if c and c["url"] not in seen:
                seen.add(c["url"])
                candidates.append(c)

    log.info("X-Ray complete: %d candidates for '%s' in '%s'", len(candidates), position, location)
    return candidates[:max_results]
