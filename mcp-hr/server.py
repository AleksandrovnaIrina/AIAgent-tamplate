# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""LumysAgent HR MCP server — FastMCP, port 3200."""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import psycopg
from fastmcp import FastMCP

DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("MCP_HR_PORT", "3200"))
GOOGLE_SHEET_ID = os.environ.get("CANDIDATE_SHEET_ID", "") or os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY") or os.environ.get("SERPAPI_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

OAUTH_TOKEN_PATH = Path(os.environ.get("GOOGLE_TOKEN_PATH", "/secrets/google-token.json"))
CLIENT_SECRET_PATH = Path(os.environ.get("GOOGLE_CLIENT_SECRET_PATH", "/secrets/client_secret.json"))
SERVICE_ACCOUNT_PATH = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "/secrets/google_credentials.json"))

mcp = FastMCP("lumys-hr")


def _conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(DATABASE_URL, autocommit=True)


def _google_creds():
    """Return google.oauth2.credentials.Credentials from mounted token files."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GRequest

    if not OAUTH_TOKEN_PATH.exists():
        raise RuntimeError(f"OAuth token not found at {OAUTH_TOKEN_PATH}")
    if not CLIENT_SECRET_PATH.exists():
        raise RuntimeError(f"Client secret not found at {CLIENT_SECRET_PATH}")

    token_data = json.loads(OAUTH_TOKEN_PATH.read_text())
    secret_data = json.loads(CLIENT_SECRET_PATH.read_text())
    installed = secret_data.get("installed") or secret_data.get("web", {})

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=installed.get("client_id"),
        client_secret=installed.get("client_secret"),
        scopes=token_data.get("scopes"),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GRequest())
    return creds


def _service_account_creds(scopes: list[str]):
    """Return service account credentials if google_credentials.json exists."""
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH), scopes=scopes
    )


def _sheets_creds():
    """Return credentials for Sheets — service account preferred, OAuth fallback."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if SERVICE_ACCOUNT_PATH.exists():
        return _service_account_creds(scopes)
    return _google_creds()


# ── track_candidate ───────────────────────────────────────────────────────────

@mcp.tool()
def track_candidate(
    name: str,
    profile_url: str = "",
    source: str = "linkedin",
    status: str = "new",
    vacancy: str = "",
    notes: str = "",
) -> str:
    """Add or update a candidate in the database and Google Sheets tracker."""
    results = []

    if DATABASE_URL:
        with _conn() as conn:
            vacancy_id = None
            if vacancy:
                row = conn.execute(
                    "SELECT id FROM vacancies WHERE title ILIKE %s LIMIT 1", (f"%{vacancy}%",)
                ).fetchone()
                vacancy_id = row[0] if row else None

            conn.execute(
                """INSERT INTO candidates (name, profile_url, source, status, vacancy_id, notes)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (profile_url) DO UPDATE
                   SET name=EXCLUDED.name, status=EXCLUDED.status,
                       notes=EXCLUDED.notes, updated_at=NOW()""",
                (name, profile_url or None, source, status, vacancy_id, notes),
            )
        results.append("✅ Збережено в БД")

    if GOOGLE_SHEET_ID:
        try:
            from googleapiclient.discovery import build
            creds = _sheets_creds()
            sheets = build("sheets", "v4", credentials=creds)
            sheets.spreadsheets().values().append(
                spreadsheetId=GOOGLE_SHEET_ID,
                range="Candidates!A:F",
                valueInputOption="USER_ENTERED",
                body={"values": [[name, profile_url, source, status, vacancy, notes]]},
            ).execute()
            results.append("✅ Додано в Google Sheets")
        except Exception as e:
            results.append(f"⚠️ Sheets помилка: {e}")

    return "\n".join(results) if results else "ℹ️ Нічого не збережено (DATABASE_URL не встановлено)"


# ── save_job_description ──────────────────────────────────────────────────────

@mcp.tool()
def save_job_description(title: str, stack: str = "", seniority: str = "", requirements: str = "") -> str:
    """Save a vacancy/job description to the database."""
    if not DATABASE_URL:
        return "ℹ️ DATABASE_URL не встановлено"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO vacancies (title, stack, seniority, requirements) VALUES (%s, %s, %s, %s)",
            (title, stack, seniority, requirements),
        )
    return f"✅ Вакансія '{title}' збережена"


# ── set_reminder ──────────────────────────────────────────────────────────────

@mcp.tool()
def set_reminder(message: str, remind_at: str, chat_id: str = "") -> str:
    """Schedule a reminder to be sent via Telegram at the given time.

    Args:
        message: Text of the reminder.
        remind_at: When to send it — ISO 8601 datetime string, e.g. "2026-06-29T10:00:00+02:00".
                   Warsaw timezone is UTC+2 (summer) / UTC+1 (winter).
        chat_id: Telegram chat ID. Leave empty — the server fills it automatically.
    """
    if not DATABASE_URL:
        return "ℹ️ DATABASE_URL не встановлено"
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")[0].strip()
    if not chat_id:
        return "❌ chat_id невідомий — встанови TELEGRAM_ALLOWED_CHAT_IDS"
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO reminders (chat_id, message, remind_at) VALUES (%s, %s, %s)",
            (chat_id, message, remind_at),
        )
    except Exception as e:
        return f"❌ Не вдалося зберегти нагадування: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return f"✅ Нагадування встановлено на {remind_at}"


# ── get_free_slots ────────────────────────────────────────────────────────────

@mcp.tool()
def get_free_slots(days: int = 3, duration_minutes: int = 60) -> str:
    """Return free time slots from Google Calendar for the next N days."""
    if not GOOGLE_CALENDAR_ID:
        return "ℹ️ GOOGLE_CALENDAR_ID не встановлено"
    try:
        from googleapiclient.discovery import build
        creds = _google_creds()
        cal = build("calendar", "v3", credentials=creds)

        now = datetime.utcnow()
        end = now + timedelta(days=days)
        events_result = cal.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        busy = [(
            e["start"].get("dateTime", e["start"].get("date")),
            e["end"].get("dateTime", e["end"].get("date")),
        ) for e in events_result.get("items", [])]

        if not busy:
            return f"Немає подій на найближчі {days} дні — весь час вільний."

        lines = [f"Зайняті слоти на {days} дні:"]
        for s, e_end in busy:
            lines.append(f"• {s[:16]} – {e_end[:16]}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Google Calendar помилка: {e}"


# ── get_email_summary ─────────────────────────────────────────────────────────

@mcp.tool()
def get_email_summary(max_results: int = 10, query: str = "is:unread") -> str:
    """Get a summary of recent emails from Gmail."""
    try:
        from googleapiclient.discovery import build
        creds = _google_creds()
        gmail = build("gmail", "v1", credentials=creds)

        list_res = gmail.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()

        messages = list_res.get("messages", [])
        if not messages:
            return "Нових листів немає."

        lines = []
        for m in messages[:max_results]:
            msg = gmail.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            sender = headers.get("From", "").split("<")[0].strip()
            subject = headers.get("Subject", "(без теми)")
            date = headers.get("Date", "")[:16]
            lines.append(f"• {date} | {sender} | {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Gmail помилка: {e}"


# ── web_search ────────────────────────────────────────────────────────────────

@mcp.tool()
def web_search(query: str, count: int = 10) -> str:
    """Search the web via Brave Search API."""
    if not BRAVE_API_KEY:
        return "ℹ️ BRAVE_API_KEY не встановлено"
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count},
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        if not results:
            return "Нічого не знайдено."
        return "\n\n".join(f"**{r['title']}**\n{r['url']}\n{r.get('description','')}" for r in results)
    except Exception as e:
        return f"❌ Пошук помилка: {e}"


# ── send_telegram_message ─────────────────────────────────────────────────────

@mcp.tool()
def send_telegram_message(chat_id: str, text: str) -> str:
    """Send a Telegram message to a specific chat (candidate outreach)."""
    if not TELEGRAM_BOT_TOKEN:
        return "ℹ️ TELEGRAM_BOT_TOKEN не встановлено"
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            return f"❌ Telegram помилка: {data.get('description')}"
        return f"✅ Повідомлення надіслано до {chat_id}"
    except Exception as e:
        return f"❌ Telegram помилка: {e}"


# ── Daily email digest cron ───────────────────────────────────────────────────

DIGEST_CHAT_ID = os.environ.get("TELEGRAM_DIGEST_CHAT_ID") or os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")[0].strip()
EMAIL_DIGEST_HOUR = int(os.environ.get("EMAIL_DIGEST_HOUR", "20"))  # UTC hour


def _send_tg(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not DIGEST_CHAT_ID:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": DIGEST_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def _email_digest_loop() -> None:
    last_run_date = None
    while True:
        now = datetime.utcnow()
        if now.hour == EMAIL_DIGEST_HOUR and now.date() != last_run_date:
            last_run_date = now.date()
            summary = get_email_summary(max_results=15, query="is:unread")
            _send_tg(f"📬 Дайджест пошти ({now.strftime('%d.%m %H:%M')} UTC):\n\n{summary}")
        time.sleep(60)


def _reminder_loop() -> None:
    while True:
        if DATABASE_URL:
            try:
                with _conn() as conn:
                    rows = conn.execute(
                        "SELECT id, chat_id, message FROM reminders WHERE remind_at <= NOW() AND sent = FALSE"
                    ).fetchall()
                    for row_id, chat_id, message in rows:
                        _send_tg(f"🔔 Нагадування: {message}")
                        conn.execute("UPDATE reminders SET sent=TRUE WHERE id=%s", (row_id,))
            except Exception:
                pass
        time.sleep(60)


if __name__ == "__main__":
    threading.Thread(target=_email_digest_loop, daemon=True).start()
    threading.Thread(target=_reminder_loop, daemon=True).start()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT, path="/mcp")
