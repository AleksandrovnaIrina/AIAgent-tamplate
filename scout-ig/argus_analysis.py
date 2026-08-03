# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Weekly competitor analysis — every Monday at 10:00 Warsaw time.

Reads posts scraped by scout.py from the last 7 days,
calls Claude to analyse trends, writes to Google Sheets (Аналіз tab),
and sends a digest to Telegram.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import anthropic
import gspread
import httpx
import psycopg
from google.oauth2.service_account import Credentials

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s argus-analysis — %(message)s")
log = logging.getLogger("argus.analysis")

DATABASE_URL = os.environ["DATABASE_URL"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_DIGEST_CHAT_ID = os.environ["TELEGRAM_DIGEST_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "/app/secrets/google_credentials.json")
ARGUS_SHEET_ID = os.environ.get("ARGUS_SHEET_ID", "")


def _fetch_posts(days: int = 7) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with psycopg.connect(DATABASE_URL) as conn:
        return conn.execute(
            """
            SELECT competitor_handle, post_url, hook, transcript, caption,
                   likes, comments, views, engagement_rate, posted_at
            FROM scout_posts
            WHERE fetched_at >= %s
            ORDER BY competitor_handle, COALESCE(engagement_rate, 0) DESC
            """,
            (cutoff,),
        ).fetchall()


def _format_posts(rows: list) -> tuple[str, dict]:
    competitors: dict[str, list] = {}
    for handle, url, hook, transcript, caption, likes, comments, views, er, posted_at in rows:
        competitors.setdefault(handle, []).append(dict(
            url=url or "",
            hook=(hook or "")[:200],
            transcript=(transcript or "")[:500],
            likes=likes or 0,
            comments=comments or 0,
            views=views or 0,
            er=round(er or 0, 2),
        ))

    text = ""
    for handle, posts in competitors.items():
        text += f"\n\n## @{handle} ({len(posts)} постів)\n"
        for i, p in enumerate(posts[:5], 1):
            text += f"\n### Пост {i}\n"
            if p["hook"]:
                text += f"Хук: {p['hook']}\n"
            if p["transcript"]:
                text += f"Транскрипт: {p['transcript']}\n"
            text += (
                f"👍 {p['likes']} | 💬 {p['comments']} | "
                f"👁 {p['views']} | ER: {p['er']}%\n"
                f"URL: {p['url']}\n"
            )
    return text, competitors


def _analyze(formatted: str, n_competitors: int, n_posts: int) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": f"""\
Ти — аналітик Instagram-контенту для Ірини, Head of HR у iGaming/affiliate ніші.
Проаналізуй дані з {n_competitors} акаунтів конкурентів за останній тиждень ({n_posts} постів).

{formatted}

Зроби структурований аналіз:

## 🏆 Топ-3 пости тижня
Конкретні пости з найвищим залученням (handle + URL)

## 📈 Тренди тижня
Які теми/формати/хуки спрацювали найкраще?

## 🎯 Ідеї для Ірини (HR / рекрутинг / iGaming ніша)
Конкретні теми і формати для адаптації — не загальні поради

## ⚡ Action items
3–5 дій на цей тиждень

Відповідай українською. Коротко і по суті."""}],
    )
    return resp.content[0].text.strip()


def _save_to_sheets(analysis: str) -> bool:
    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        ss = gc.open_by_key(ARGUS_SHEET_ID)
        try:
            ws = ss.worksheet("Аналіз")
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title="Аналіз", rows=1000, cols=3)
            ws.append_row(["Дата", "Тип", "Аналіз"], value_input_option="USER_ENTERED")
            ws.format("1:1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        ws.append_row([now, "Автоаналіз (понеділок)", analysis], value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        log.error("Sheets write failed: %s", e)
        return False


def _send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk in [text[i : i + 4000] for i in range(0, len(text), 4000)]:
        try:
            httpx.post(
                url,
                json={"chat_id": TELEGRAM_DIGEST_CHAT_ID, "text": chunk, "parse_mode": "Markdown"},
                timeout=30,
            )
        except Exception as e:
            log.error("Telegram send failed: %s", e)


def main() -> None:
    log.info("Weekly competitor analysis starting")

    rows = _fetch_posts(days=7)
    if not rows:
        log.info("No posts in last 7 days — sending notice")
        _send_telegram(
            "🔍 *Аналіз конкурентів (понеділок)*\n\n"
            "За останній тиждень нових постів не знайдено.\n"
            "Скаут запускається о 06:00 — якщо він ще не завершив роботу, аналіз прийде пізніше."
        )
        return

    n_posts = len(rows)
    formatted, competitors = _format_posts(rows)
    n_competitors = len(competitors)
    log.info("Analyzing %d posts from %d competitors", n_posts, n_competitors)

    analysis = _analyze(formatted, n_competitors, n_posts)
    saved = _save_to_sheets(analysis)

    week = datetime.now().strftime("%d.%m")
    header = f"🔍 *Аналіз конкурентів — тиждень {week}*\n_{n_posts} постів · {n_competitors} акаунтів_\n\n"
    footer = "\n\n✅ Збережено в таблицю" if saved else ""
    _send_telegram(header + analysis + footer)
    log.info("Analysis done")


if __name__ == "__main__":
    main()
