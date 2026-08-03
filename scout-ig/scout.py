# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Scout — Instagram reel scraper for competitor accounts.

One cron tick:
  1. Read competitors.yml.
  2. Run Apify `instagram-reel-scraper` for the configured handles.
  3. Optionally backfill missing transcripts via Groq Whisper.
  4. Insert new reels into scout_posts (dedup by post_id).
  5. Rank by engagement rate, push a digest to Telegram.

Run modes:
  python scout.py             # one cron tick
  python scout.py --run-now   # alias (same behavior)
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
import psycopg
import yaml
from apify_client import ApifyClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s scout — %(message)s",
)
log = logging.getLogger("scout")

APIFY_TOKEN = os.environ["APIFY_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_DIGEST_CHAT_ID = os.environ["TELEGRAM_DIGEST_CHAT_ID"]
DATABASE_URL = os.environ["DATABASE_URL"]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

COMPETITORS_FILE = Path("/app/competitors.yml")
LOCK_PATH = Path("/tmp/argus-scout.lock")

APIFY_ACTOR = "apify/instagram-reel-scraper"
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "whisper-large-v3-turbo"
GROQ_LLM_MODEL = "llama-3.1-8b-instant"
HOOK_WORD_LIMIT = 37  # ~15s @ 2.5 wps


# -----------------------------------------------------------------------------
# Concurrency lock — prevent overlapping cron + manual runs
# -----------------------------------------------------------------------------

def acquire_lock(path: Path = LOCK_PATH, timeout_sec: int = 120) -> int:
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()}\n".encode())
            return fd
        except OSError as exc:
            if exc.errno not in (errno.EAGAIN, errno.EACCES):
                os.close(fd)
                raise
            if time.monotonic() >= deadline:
                os.close(fd)
                raise TimeoutError(f"scout lock busy after {timeout_sec}s")
            time.sleep(1.0)


def release_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

def load_config() -> dict:
    if not COMPETITORS_FILE.exists():
        log.error("competitors.yml not mounted at %s", COMPETITORS_FILE)
        sys.exit(1)
    return yaml.safe_load(COMPETITORS_FILE.read_text()) or {}


# -----------------------------------------------------------------------------
# Apify scrape
# -----------------------------------------------------------------------------

def run_apify(handles: list[str], results_limit: int) -> list[dict]:
    log.info("apify start: actor=%s handles=%d limit=%d",
             APIFY_ACTOR, len(handles), results_limit)
    client = ApifyClient(APIFY_TOKEN)
    run = client.actor(APIFY_ACTOR).call(
        run_input={"username": handles, "resultsLimit": results_limit}
    )
    if not run:
        log.error("apify call returned None")
        return []
    # SDK ≥2.0 returns a Run object with attributes; older versions return a dict
    if hasattr(run, "default_dataset_id"):
        dataset_id = run.default_dataset_id
    else:
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        log.error("apify returned no dataset id: %s", run)
        return []
    items = list(client.dataset(dataset_id).iterate_items())
    log.info("apify returned %d items", len(items))
    return items


# -----------------------------------------------------------------------------
# Transcription (Groq Whisper — optional fallback)
# -----------------------------------------------------------------------------

def whisper_enabled() -> bool:
    return bool(GROQ_API_KEY)


def translate_to_ukrainian(text: str) -> str:
    """Translate text to Ukrainian using Groq LLM. Returns original on failure."""
    if not text or not GROQ_API_KEY:
        return text
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": GROQ_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "Переклади текст українською мовою. Поверни лише переклад без пояснень."},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 1024,
                },
            )
        if r.is_success:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        log.warning("translation failed: %s", exc)
    return text


def transcribe(audio_url: str) -> str:
    """Download audio and POST to Groq Whisper. Empty string on failure."""
    if not audio_url or not GROQ_API_KEY:
        return ""
    try:
        with httpx.Client(timeout=60) as client:
            audio = client.get(audio_url).content
    except httpx.HTTPError as exc:
        log.warning("whisper download failed for %s: %s", audio_url[:80], exc)
        return ""
    for attempt in range(3):
        try:
            with httpx.Client(timeout=180) as client:
                r = client.post(
                    GROQ_WHISPER_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    files={"file": ("audio.mp4", audio, "audio/mp4")},
                    data={"model": GROQ_MODEL, "response_format": "text"},
                )
        except httpx.HTTPError as exc:
            log.warning("whisper POST failed: %s", exc)
            return ""
        if r.status_code == 429:
            ra = r.headers.get("retry-after") or "5"
            try:
                wait = max(1, min(int(float(ra)), 30)) + 1
            except (TypeError, ValueError):
                wait = 6
            log.info("whisper 429 (attempt %d), sleep %ds", attempt + 1, wait)
            time.sleep(wait)
            continue
        if not r.is_success:
            log.warning("whisper http %d: %s", r.status_code, r.text[:200])
            return ""
        return r.text.strip()
    return ""


# -----------------------------------------------------------------------------
# Item transformation
# -----------------------------------------------------------------------------

def _truncate_hook(text: str, max_words: int = HOOK_WORD_LIMIT) -> str:
    if not text:
        return ""
    return " ".join(text.split()[:max_words])


def _parse_timestamp(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def transform(item: dict) -> Optional[dict]:
    post_url = item.get("url") or ""
    post_id = item.get("id") or item.get("shortCode")
    if not post_id or not post_url:
        return None

    handle = item.get("ownerUsername") or ""
    caption = item.get("caption") or ""
    transcript = (item.get("transcript") or "").strip()
    audio_url = item.get("audioUrl") or item.get("videoUrl") or ""

    # Fallback: backfill transcript via Whisper if Apify didn't provide one
    if not transcript and audio_url and whisper_enabled():
        log.info("transcribing audio for %s", post_url)
        transcript = transcribe(audio_url)

    # Keep original, translate to Ukrainian separately
    original_transcript = transcript
    transcript_ua = translate_to_ukrainian(transcript) if transcript else ""

    hook = _truncate_hook(transcript_ua or original_transcript or caption)

    views = item.get("videoPlayCount") or item.get("videoViewCount") or 0
    likes = item.get("likesCount") or 0
    comments = item.get("commentsCount") or 0
    try:
        engagement = round((likes + comments) / views, 4) if views else 0.0
    except (TypeError, ZeroDivisionError):
        engagement = 0.0

    return {
        "post_id": str(post_id),
        "competitor_handle": handle,
        "post_url": post_url,
        "caption": caption,
        "transcript": transcript_ua or original_transcript,
        "original_transcript": original_transcript,
        "transcript_ua": transcript_ua,
        "hook": hook,
        "likes": int(likes or 0),
        "comments": int(comments or 0),
        "views": int(views or 0),
        "engagement_rate": float(engagement),
        "duration_seconds": float(item.get("videoDuration") or 0),
        "video_url": item.get("videoUrl") or "",
        "posted_at": _parse_timestamp(item.get("timestamp")),
        "raw": item,
    }


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

def persist_new(rows: list[dict]) -> list[dict]:
    """Insert rows that aren't already in scout_posts; return only the newly
    inserted ones (for the digest).
    """
    new_rows: list[dict] = []
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO scout_posts (
                    post_id, competitor_handle, post_url, caption, transcript,
                    original_transcript, transcript_ua, hook,
                    likes, comments, views, engagement_rate, duration_seconds,
                    video_url, posted_at, raw
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (post_id) DO NOTHING
                RETURNING post_id
                """,
                (
                    r["post_id"], r["competitor_handle"], r["post_url"],
                    r["caption"], r["transcript"],
                    r["original_transcript"], r["transcript_ua"], r["hook"],
                    r["likes"], r["comments"], r["views"],
                    r["engagement_rate"], r["duration_seconds"],
                    r["video_url"], r["posted_at"],
                    psycopg.types.json.Jsonb(r["raw"]),
                ),
            )
            if cur.fetchone():
                new_rows.append(r)
    log.info("persisted %d new posts (of %d fetched)", len(new_rows), len(rows))
    return new_rows


def mark_sent(rows: list[dict]) -> None:
    if not rows:
        return
    ids = [r["post_id"] for r in rows]
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE scout_posts SET sent_in_digest_at = NOW() WHERE post_id = ANY(%s)",
            (ids,),
        )


# -----------------------------------------------------------------------------
# Digest formatting & delivery
# -----------------------------------------------------------------------------

def _format_views(n: Any) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n // 1000}k"
    return str(n)


def format_digest(new_rows: list[dict], checked_handles: int, top_n: int) -> str:
    if not new_rows:
        return "🔍 Argus: scout ran — no new reels since last digest."
    top = sorted(new_rows, key=lambda r: r["engagement_rate"], reverse=True)[:top_n]
    lines = [
        "🔍 Argus digest",
        "",
        f"Checked: {checked_handles} competitors",
        f"New reels: {len(new_rows)}",
        "",
        "Top by engagement:",
    ]
    for i, r in enumerate(top, 1):
        er_pct = f"{r['engagement_rate'] * 100:.1f}%"
        views_short = _format_views(r["views"])
        hook = (r["hook"] or "").replace("\n", " ").strip()
        if len(hook) > 80:
            hook = hook[:77] + "..."
        lines.append(
            f"{i}. 🎬 [{er_pct} / {views_short}] @{r['competitor_handle']} — \"{hook}\""
        )
        lines.append(f"   {r['post_url']}")
        lines.append("")
    return "\n".join(lines).strip()


def send_telegram(text: str) -> None:
    if not text.strip():
        return
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_DIGEST_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not r.is_success:
            log.error("telegram send http %d: %s", r.status_code, r.text[:300])
    except httpx.HTTPError as exc:
        log.error("telegram send failed: %s", exc)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def run() -> int:
    cfg = load_config()
    competitors = cfg.get("competitors") or []
    if not competitors:
        log.warning("no competitors configured in competitors.yml")
        send_telegram("🔍 Argus: competitors.yml is empty — nothing to scout.")
        return 0

    handles = [str(c["handle"]).lstrip("@").lower() for c in competitors if c.get("handle")]
    results_limit = max((c.get("posts_per_run", 10) for c in competitors), default=10)
    top_n = (cfg.get("digest") or {}).get("top_n", 10)

    items = run_apify(handles, results_limit)
    if not items:
        send_telegram(
            "🔍 Argus: Apify returned no items — check that handles are public accounts."
        )
        return 0

    rows = [t for t in (transform(it) for it in items) if t]
    new_rows = persist_new(rows)
    digest = format_digest(new_rows, len(handles), top_n)
    send_telegram(digest)
    mark_sent(new_rows)

    if new_rows:
        _write_to_sheets(new_rows)

    return 0


def _write_to_sheets(rows: list[dict]) -> None:
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "")
    spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID", "")
    if not creds_file or not spreadsheet_id or not Path(creds_file).exists():
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from datetime import datetime, timezone as tz
        creds = Credentials.from_service_account_file(
            creds_file, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        ss = client.open_by_key(spreadsheet_id)
        headers = [
            "ID", "Status", "From", "URL", "Hook", "Original_Script", "Script",
            "Caption", "CTA_Word", "CTA_Artifact", "CTA_TG_URL", "Video", "Notion",
            "Scheduled", "Posted", "Skip_Reason", "Created", "Updated",
            "Buffer_Post_ID", "Posted_URL", "Source_URL", "Cover"
        ]
        try:
            ws = ss.worksheet("Reels")
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title="Reels", rows=1000, cols=len(headers))
            ws.append_row(headers, value_input_option="USER_ENTERED")
            ws.format("1:1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)

        # Get next ID — use float() to handle Google Sheets date-formatted cells
        ids = ws.col_values(1)[1:]
        numeric = []
        for x in ids:
            try:
                numeric.append(int(float(x)))
            except (ValueError, TypeError):
                pass
        next_id = max(numeric, default=0) + 1

        now = datetime.now(tz.utc).strftime("%d/%m/%y %H:%M")
        data = []
        for r in rows:
            posted_dt = _parse_timestamp(r.get("posted_at"))
            posted = posted_dt.strftime("%d/%m/%y %H:%M") if posted_dt else ""
            # Clean newlines from text fields
            def clean(v): return (v or "").replace("\n", " ").replace("\r", " ").strip()
            data.append([
                str(next_id),
                "draft",
                r.get("competitor_handle", ""),
                r.get("post_url", ""),
                clean(r.get("hook"))[:200],
                clean(r.get("original_transcript") or r.get("transcript") or "")[:2000],
                clean(r.get("transcript_ua") or r.get("transcript") or "")[:2000],
                "",  # Caption
                "",  # CTA_Word
                "",  # CTA_Artifact
                "",  # CTA_TG_URL
                r.get("video_url", ""),
                "",  # Notion
                "",  # Scheduled
                "",  # Posted
                "",  # Skip_Reason
                posted or now,
                now,
                "",  # Buffer_Post_ID
                "",  # Posted_URL
                r.get("post_url", ""),
                "",  # Cover
            ])
            next_id += 1
        ws.append_rows(data, value_input_option="RAW")
        log.info("wrote %d rows to Google Sheets", len(data))
    except Exception as e:
        log.warning("sheets write failed (non-critical): %s", e)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-now", action="store_true", help="alias for default")
    parser.parse_args(argv)

    lock_fd: Optional[int] = None
    try:
        lock_fd = acquire_lock()
        return run()
    except TimeoutError as exc:
        log.error("%s", exc)
        return 1
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("scout failed: %s\n%s", exc, tb)
        send_telegram(f"⚠️ Argus scout crashed: {exc}")
        return 1
    finally:
        if lock_fd is not None:
            release_lock(lock_fd)


if __name__ == "__main__":
    sys.exit(main())
