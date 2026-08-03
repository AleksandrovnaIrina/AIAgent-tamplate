# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Read public Telegram channels via t.me/s/ web view — no auth required."""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; ScoutBot/1.0)"

# Default channels relevant for iGaming / affiliate / IT recruiting in Ukraine/CIS
DEFAULT_CHANNELS = [
    "djinni_jobs",        # Djinni job board
    "dou_jobs",           # DOU jobs
    "affiliatework",      # Affiliate jobs
    "igamingvacancies",   # iGaming vacancies
    "jobs_marketing_ua",  # Marketing jobs UA
    "remote_jobs_ua",     # Remote jobs Ukraine
    "bd_sales_jobs",      # BizDev / Sales
    "adtech_jobs",        # AdTech
]

# Channels focused on Media Buying / Affiliate / Traffic arbitrage
# May include invite links (https://t.me/+...) for private channels
MEDIA_BUYER_CHANNELS = [
    "trafflab",                          # Traffic Lab — арбітраж трафіку
    "affiliatework",                     # Affiliate jobs
    "igamingvacancies",                  # iGaming vacancies
    "adtech_jobs",                       # AdTech jobs
    "mediabuying_jobs",                  # Media buying jobs
    "affiliate_jobs_ua",                 # Affiliate UA jobs
    "cpa_jobs",                          # CPA network jobs
    "traffic_jobs",                      # Traffic / арбітраж вакансії
    "remote_jobs_ua",                    # Remote jobs Ukraine
    "https://t.me/+qVOHBtTuDVNmODI6",  # Приватний канал (Media Buyer)
]


def _fetch_channel(channel: str, max_posts: int = 30) -> list[dict]:
    """Fetch recent posts from a public Telegram channel via t.me/s/."""
    url = f"https://t.me/s/{channel}"
    try:
        resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            log.warning("tg_channels: %s returned %d", channel, resp.status_code)
            return []
    except Exception as e:
        log.warning("tg_channels: failed to fetch %s: %s", channel, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = []

    for msg in soup.select(".tgme_widget_message")[-max_posts:]:
        # Text
        text_el = msg.select_one(".tgme_widget_message_text")
        text = text_el.get_text(separator="\n", strip=True) if text_el else ""
        if not text:
            continue

        # Post link
        link_el = msg.select_one(".tgme_widget_message_date")
        link = link_el["href"] if link_el and link_el.get("href") else f"https://t.me/{channel}"

        # Date
        time_el = msg.select_one("time")
        date = time_el.get("datetime", "")[:10] if time_el else ""

        posts.append({
            "channel": f"@{channel}",
            "text": text[:800],
            "link": link,
            "date": date,
        })

    log.info("tg_channels: @%s → %d posts fetched", channel, len(posts))
    return posts


def _matches(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def search_telegram_channels(
    keywords: list[str],
    channels: Optional[list[str]] = None,
    max_posts_per_channel: int = 40,
) -> dict:
    """Search public Telegram channels for posts matching keywords.

    Args:
      keywords: words to match (e.g. ["affiliate", "media buyer", "igaming"])
      channels: list of channel usernames without @. Defaults to recruiting channels.
      max_posts_per_channel: how many recent posts to scan per channel

    Returns: {total_scanned, matches_found, results: [{channel, text, link, date}]}
    """
    target_channels = channels or DEFAULT_CHANNELS
    all_posts: list[dict] = []
    total_scanned = 0

    for ch in target_channels:
        ch = ch.lstrip("@")
        posts = _fetch_channel(ch, max_posts=max_posts_per_channel)
        total_scanned += len(posts)
        for p in posts:
            if _matches(p["text"], keywords):
                all_posts.append(p)

    # Sort by date descending
    all_posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    log.info(
        "tg_channels: scanned %d posts across %d channels, found %d matches for %s",
        total_scanned, len(target_channels), len(all_posts), keywords,
    )
    return {
        "total_scanned": total_scanned,
        "channels_checked": len(target_channels),
        "matches_found": len(all_posts),
        "results": all_posts,
    }
