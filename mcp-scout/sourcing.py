"""LinkedIn X-Ray candidate sourcing via Serper.dev API."""
from __future__ import annotations

import logging
import os
import re
import time

import requests

log = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
_LOCATION_RE = re.compile(r"[-–|·•]\s*([^·•\-–]+(?:,\s*[^·•\-–]+)*)\s*$")


def _build_queries(position: str, location: str, keywords: list[str] | None = None) -> list[str]:
    base = f'site:linkedin.com/in/ "{position}" "{location}"'
    if not keywords:
        return [base]
    pairs = [f'"{kw}"' for kw in keywords[:8]]
    extra = [f'{base} {a} {b}' for a, b in zip(pairs[::2], pairs[1::2])]
    return [base] + extra


def _serper_request(query: str, num: int = 10) -> dict:
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        raise ValueError("SERPER_API_KEY is not configured")
    resp = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_item(item: dict, position: str, location: str) -> dict | None:
    url: str = item.get("link", "")
    if "linkedin.com/in/" not in url:
        return None

    title: str = item.get("title", "")
    snippet: str = item.get("snippet", "")

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
    """Search LinkedIn profiles via Google X-Ray (Serper API)."""
    queries = _build_queries(position, location, keywords)
    seen: set[str] = set()
    candidates: list[dict] = []

    for query in queries:
        if len(candidates) >= max_results:
            break
        log.info("Serper X-Ray: %s", query)
        try:
            data = _serper_request(query, num=10)
        except Exception as exc:
            log.warning("Serper request failed: %s", exc)
            continue

        for item in data.get("organic", []):
            c = _parse_item(item, position, location)
            if c and c["url"] not in seen:
                seen.add(c["url"])
                candidates.append(c)

        time.sleep(0.3)

    log.info("X-Ray complete: %d candidates for '%s' in '%s'", len(candidates), position, location)
    return candidates[:max_results]
