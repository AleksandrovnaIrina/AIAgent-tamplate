# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""
LumysAgent Scout — автоматичний пошук кандидатів.

Джерела:
  - Djinni.ua (через Apify або прямий API)
  - DOU.ua (скрапінг через Apify)
  - LinkedIn X-Ray (через Brave Search / SerpAPI)

Запуск: python scout.py [--run-now]
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime

import psycopg
import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("lumys.scout")

DATABASE_URL = os.environ["DATABASE_URL"]
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", os.environ.get("SERPAPI_KEY", ""))
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_DIGEST_CHAT_ID = os.environ["TELEGRAM_DIGEST_CHAT_ID"]

VACANCIES_FILE = os.environ.get("VACANCIES_FILE", "/app/vacancies.yml")


def load_vacancies() -> list[dict]:
    with open(VACANCIES_FILE) as f:
        config = yaml.safe_load(f)
    return config.get("vacancies", [])


def load_digest_config() -> dict:
    with open(VACANCIES_FILE) as f:
        config = yaml.safe_load(f)
    return config.get("digest", {"top_n": 10})


def db_conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)


def deduplicate_url(profile_url: str) -> bool:
    """Returns True if URL is new (not yet in scout_results)."""
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM scout_results WHERE profile_url = %s", (profile_url,))
        return cur.fetchone() is None


def save_scout_result(source: str, profile_url: str, candidate_data: dict, vacancy_title: str):
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scout_results (source, profile_url, candidate_data, vacancy_match)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (profile_url) DO NOTHING""",
            (source, profile_url, json.dumps(candidate_data), vacancy_title),
        )


# ─── Djinni ─────────────────────────────────────────────────────────────────

def fetch_djinni(vacancy: dict) -> list[dict]:
    """Fetch candidates from Djinni via Apify actor or direct API."""
    results = []
    stack = vacancy.get("stack", [])
    seniority = vacancy.get("seniority", "")
    limit = vacancy.get("candidates_per_run", 20)

    if APIFY_TOKEN:
        log.info("Djinni: fetching via Apify")
        results = _fetch_djinni_apify(stack, seniority, limit)
    else:
        log.info("Djinni: Apify token not set, skipping")

    return results


def _fetch_djinni_apify(stack: list, seniority: str, limit: int) -> list[dict]:
    """Run Apify djinni-candidates actor."""
    actor_id = "apify/djinni-candidates-scraper"
    run_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"

    keywords = " ".join(stack[:3]) if stack else ""
    payload = {
        "keywords": keywords,
        "experienceLevel": seniority,
        "maxItems": limit,
    }

    try:
        resp = requests.post(
            run_url,
            json=payload,
            params={"token": APIFY_TOKEN},
            timeout=120,
        )
        resp.raise_for_status()
        items = resp.json()
        candidates = []
        for item in items:
            url = item.get("profileUrl") or item.get("url", "")
            if not url or not deduplicate_url(url):
                continue
            candidate = {
                "name": item.get("name", "Unknown"),
                "url": url,
                "title": item.get("title", ""),
                "skills": item.get("skills", []),
                "salary": item.get("salary", ""),
                "location": item.get("location", ""),
                "source": "djinni",
            }
            candidates.append(candidate)
        return candidates
    except Exception as e:
        log.warning("Djinni Apify fetch failed: %s", e)
        return []


# ─── DOU ────────────────────────────────────────────────────────────────────

def fetch_dou(vacancy: dict) -> list[dict]:
    """Fetch candidates from DOU.ua via Apify."""
    if not APIFY_TOKEN:
        log.info("DOU: Apify token not set, skipping")
        return []

    stack = vacancy.get("stack", [])
    limit = vacancy.get("candidates_per_run", 20)

    log.info("DOU: fetching via Apify")
    actor_id = "apify/dou-jobs-scraper"
    run_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"

    category = stack[0] if stack else "Python"

    try:
        resp = requests.post(
            run_url,
            json={"category": category, "maxItems": limit},
            params={"token": APIFY_TOKEN},
            timeout=120,
        )
        resp.raise_for_status()
        items = resp.json()
        candidates = []
        for item in items:
            url = item.get("url", "")
            if not url or not deduplicate_url(url):
                continue
            candidate = {
                "name": item.get("name", "Unknown"),
                "url": url,
                "title": item.get("title", ""),
                "skills": item.get("skills", []),
                "source": "dou",
            }
            candidates.append(candidate)
        return candidates
    except Exception as e:
        log.warning("DOU Apify fetch failed: %s", e)
        return []


# ─── LinkedIn X-Ray ──────────────────────────────────────────────────────────

def fetch_linkedin_xray(vacancy: dict) -> list[dict]:
    """Search LinkedIn profiles via Brave Search (X-Ray)."""
    if not BRAVE_API_KEY:
        log.info("LinkedIn X-Ray: BRAVE_API_KEY not set, skipping")
        return []

    stack = vacancy.get("stack", [])
    seniority = vacancy.get("seniority", "")
    limit = min(vacancy.get("candidates_per_run", 20), 20)

    # Build X-Ray query
    skills_part = " ".join(f'"{s}"' for s in stack[:3]) if stack else ""
    seniority_part = f'"{seniority}"' if seniority else ""
    query = f'site:linkedin.com/in {skills_part} {seniority_part} Ukraine'.strip()

    log.info("LinkedIn X-Ray query: %s", query)

    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("web", {}).get("results", [])

        candidates = []
        for item in items:
            url = item.get("url", "")
            if "linkedin.com/in/" not in url:
                continue
            if not deduplicate_url(url):
                continue
            name = item.get("title", "").split(" | ")[0].split(" - ")[0].strip()
            candidate = {
                "name": name or "LinkedIn Profile",
                "url": url,
                "title": item.get("description", "")[:200],
                "skills": stack,
                "source": "linkedin_xray",
            }
            candidates.append(candidate)
        return candidates
    except Exception as e:
        log.warning("LinkedIn X-Ray fetch failed: %s", e)
        return []


# ─── Telegram digest ─────────────────────────────────────────────────────────

def send_telegram_digest(candidates: list[dict], vacancy_title: str, top_n: int):
    if not candidates:
        log.info("No new candidates for digest")
        return

    top = candidates[:top_n]
    lines = [f"🔍 *Нові кандидати — {vacancy_title}* ({len(top)} з {len(candidates)})\n"]

    for i, c in enumerate(top, 1):
        source_emoji = {"djinni": "🟡", "dou": "🟢", "linkedin_xray": "🔵"}.get(c["source"], "⚪")
        lines.append(
            f"{i}. {source_emoji} [{c['name']}]({c['url']})\n"
            f"   {c.get('title', '')}"
        )

    text = "\n".join(lines)

    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_DIGEST_CHAT_ID,
            "text": text[:4000],
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    if resp.ok:
        log.info("Digest sent: %d candidates for '%s'", len(top), vacancy_title)
    else:
        log.warning("Telegram digest send failed: %s", resp.text)


# ─── Main ────────────────────────────────────────────────────────────────────

def run_scout():
    log.info("Scout started at %s", datetime.now().isoformat())
    vacancies = load_vacancies()
    digest_config = load_digest_config()
    top_n = digest_config.get("top_n", 10)

    for vacancy in vacancies:
        title = vacancy.get("title", "Unknown")
        sources = vacancy.get("sources", ["djinni", "dou", "linkedin_xray"])
        log.info("Processing vacancy: %s (sources: %s)", title, sources)

        all_candidates = []

        if "djinni" in sources:
            candidates = fetch_djinni(vacancy)
            for c in candidates:
                save_scout_result("djinni", c["url"], c, title)
            all_candidates.extend(candidates)
            log.info("Djinni: %d new candidates", len(candidates))

        if "dou" in sources:
            candidates = fetch_dou(vacancy)
            for c in candidates:
                save_scout_result("dou", c["url"], c, title)
            all_candidates.extend(candidates)
            log.info("DOU: %d new candidates", len(candidates))

        if "linkedin_xray" in sources:
            candidates = fetch_linkedin_xray(vacancy)
            for c in candidates:
                save_scout_result("linkedin_xray", c["url"], c, title)
            all_candidates.extend(candidates)
            log.info("LinkedIn X-Ray: %d new candidates", len(candidates))

        send_telegram_digest(all_candidates, title, top_n)

    log.info("Scout finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-now", action="store_true", help="Run immediately, ignore cron")
    args = parser.parse_args()
    run_scout()
