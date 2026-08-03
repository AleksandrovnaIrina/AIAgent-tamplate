# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Scout MCP server — HR, sourcing, and recruiting tools.

FastMCP server on port 3400.
Memory tools live in the shared mcp-memory server.

Tools:
  Sourcing:
    build_boolean_search(role, skills, location, ...)
    web_search(query, max_results, sites)
    read_url(url)
  Job Descriptions:
    save_job_description(title, content, company, department, status)
    list_job_descriptions(status)
  Candidate tracking:
    track_candidate(name, profile_url, role, status, source, comment)
    save_research_article(title, url, summary, topic, source)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx
from fastmcp import FastMCP

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
PROXYCURL_API_KEY = os.environ.get("PROXYCURL_API_KEY", "")

import boolean_builder as _bool
import calendar_tool as _cal
import fetch as _fetch
import gmail as _gmail
import search as _search
import sheets as _sheets
import sourcing as _sourcing
import tg_channels as _tg
import tg_reader as _tgreader
import tg_sender as _tgsend

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("scout-mcp")

HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "3400"))

mcp = FastMCP("scout")


# ---- Boolean / X-Ray search builder ----

@mcp.tool()
def build_boolean_search(
    role: str,
    skills: list[str],
    location: Optional[str] = None,
    exclude_terms: Optional[list[str]] = None,
    role_synonyms: Optional[list[str]] = None,
    experience_level: Optional[str] = None,
) -> dict:
    """Build Boolean and X-Ray search strings for LinkedIn, Google, and GitHub.

    Call this whenever Iryna asks for search strings, Boolean, or X-Ray for any role.
    Always use this tool — never construct search strings manually.

    Args:
      role: Primary role name (e.g. "Affiliate Manager", "Media Buyer", "Head of BD")
      skills: Key skills or keywords (e.g. ["iGaming", "CPA", "traffic arbitrage"])
      location: Target location (e.g. "Ukraine", "Poland", "Europe", "Remote")
      exclude_terms: Words to exclude from results (e.g. ["intern", "student"])
      role_synonyms: Alternative titles (e.g. ["Partnership Manager", "Partner Manager"])
      experience_level: "junior", "mid", or "senior" — adds level-specific terms

    Returns: {role, linkedin_boolean, google_xray_linkedin, google_xray_github,
              github_search_url, tips}
    """
    return _bool.build_boolean_search(
        role=role,
        skills=skills,
        location=location,
        exclude_terms=exclude_terms,
        role_synonyms=role_synonyms,
        experience_level=experience_level,
    )


# ---- Web search ----

@mcp.tool()
def web_search(
    query: str,
    max_results: int = 8,
    sites: Optional[list[str]] = None,
) -> list[dict]:
    """Search the web via DuckDuckGo. Use for market research, salary benchmarks,
    company info, sourcing tips, or finding candidates on public platforms.

    Recruiting-focused sources (use via sites=[...]):
      linkedin.com, github.com, glassdoor.com, levels.fyi, builtin.com,
      wellfound.com, djinni.co, dou.ua, hh.ru

    Args:
      query: search query (English gives best results for global sources)
      max_results: number of results (default 8, max 15)
      sites: restrict to specific domains (e.g. ["djinni.co", "dou.ua"])

    Returns: list of {title, url, snippet}
    """
    return _search.web_search(query, max_results=min(max_results, 15), sites=sites)


# ---- URL reader ----

@mcp.tool()
def read_url(url: str) -> dict:
    """Fetch a web page and return its readable text content (max 10,000 chars).

    Use for:
    - Reading job postings for competitive analysis
    - Reading articles, company pages, or any public URL
    NOTE: For LinkedIn profiles use fetch_linkedin_profile instead.

    Args:
      url: public URL to fetch

    Returns: {url, status_code, text, truncated}
    """
    return _fetch.read_url(url)


@mcp.tool()
def fetch_linkedin_profile(url: str) -> str:
    """Fetch a LinkedIn profile via DuckDuckGo search (same as X-Ray candidate search).

    Use this whenever Iryna shares a linkedin.com/in/... URL.

    Args:
      url: LinkedIn profile URL (linkedin.com/in/username)
    """
    # Extract username from URL
    import re
    match = re.search(r'linkedin\.com/in/([^/?#]+)', url)
    username = match.group(1).rstrip('/') if match else None
    if not username:
        return f"❌ Не вдалося розпізнати LinkedIn URL: {url}"

    results = _search.web_search(
        query=f"site:linkedin.com/in/{username}",
        max_results=5,
        sites=["linkedin.com"],
    )

    if not results:
        return f"❌ DuckDuckGo не знайшов профіль: {url}"

    # Also search for more context about this person
    name_results = _search.web_search(
        query=f'linkedin.com/in/{username} HR recruiter experience',
        max_results=5,
    )

    parts = [f"🔗 {url}", ""]
    seen = set()
    for r in results + name_results:
        snippet = r.get('snippet', '').strip()
        title = r.get('title', '').strip()
        if snippet and snippet not in seen:
            seen.add(snippet)
            if title:
                parts.append(f"**{title}**")
            parts.append(snippet)
            parts.append("")

    return "\n".join(parts) if parts else f"❌ Профіль не знайдено: {url}"


# ---- Job Description (Google Sheets) ----

@mcp.tool()
def save_job_description(
    title: str,
    content: str,
    company: Optional[str] = None,
    department: Optional[str] = None,
    status: str = "Draft",
) -> dict:
    """Save a generated Job Description to the Google Sheet (Job Descriptions tab).

    Always call this after generating a JD if Iryna confirms she wants to save it.
    Generate the full JD content first, then call this tool to persist it.

    Args:
      title: Role name (e.g. "Senior Affiliate Manager")
      content: Full JD text (plain text or Markdown)
      company: Company name (optional)
      department: Department or team (optional)
      status: Draft / Ready / Published (default: Draft)

    Returns: {sheet_url, title, status}
    """
    return _sheets.save_job_description(
        title=title,
        content=content,
        company=company or "",
        department=department or "",
        status=status,
    )


@mcp.tool()
def list_job_descriptions(status: Optional[str] = None) -> list[dict]:
    """List saved Job Descriptions from the Google Sheet.

    Args:
      status: Filter by status — Draft / Ready / Published (optional)

    Returns: list of rows from the Job Descriptions tab
    """
    return _sheets.list_job_descriptions(status=status or "")


# ---- Candidate tracker (Google Sheets) ----

@mcp.tool()
def track_candidate(
    name: str,
    profile_url: str,
    role: str,
    status: str,
    source: str = "",
    comment: str = "",
) -> dict:
    """Save a candidate to the Google Sheets candidate tracker.

    Call this when Iryna wants to log a candidate: after sourcing, screening,
    or any pipeline stage. Status values: New / Contacted / Screening /
    Interview / Offer / Hired / Rejected / On hold.

    Args:
      name: Full name (e.g. "Ivan Petrenko")
      profile_url: LinkedIn or other profile URL
      role: Role they're being considered for
      status: Pipeline status (e.g. "New", "Contacted", "Screening")
      source: Where found (e.g. "LinkedIn X-Ray", "Djinni", "Referral")
      comment: Any notes (e.g. "5y iGaming, open to relocation")

    Returns: {sheet_url, candidate, role, status}
    """
    return _sheets.track_candidate(
        name=name, profile_url=profile_url, role=role,
        status=status, source=source, comment=comment,
    )


# ---- Research articles (Google Sheets) ----

@mcp.tool()
def save_research_article(
    title: str,
    url: str,
    summary: str,
    topic: str = "",
    source: str = "",
) -> dict:
    """Save a research article or resource to the Scout Research Google Sheet.

    Call after web_search when finding useful recruiting/HR resources.

    Args:
      title: article title
      url: article URL
      summary: 1-2 sentences in Ukrainian: what it's about and why useful
      topic: topic tag (e.g. "сорсинг", "salary benchmark", "iGaming ринок")
      source: publication name or domain

    Returns: {sheet_url, title}
    """
    return _sheets.save_research_article(
        title=title, url=url, summary=summary, topic=topic, source=source,
    )


# ---- Google Calendar ----

@mcp.tool()
def get_free_slots(
    days: int = 3,
    slot_duration_minutes: int = 45,
    work_start_hour: int = 9,
    work_end_hour: int = 18,
) -> dict:
    """Find free time slots in Google Calendar for scheduling interviews.

    Call this when Iryna asks for free slots, available time, or wants to
    send interview invitation with specific times.

    Args:
      days: how many days ahead to look (default 3)
      slot_duration_minutes: interview duration in minutes (default 45)
      work_start_hour: working day start, Warsaw time (default 9)
      work_end_hour: working day end, Warsaw time (default 18)

    Returns: {slots: [{start, end, label}], timezone, slot_duration_minutes}

    After getting results — show Iryna top 3-5 slots as a formatted list
    she can send to the candidate.
    """
    return _cal.get_free_slots(
        days=days,
        slot_duration_minutes=slot_duration_minutes,
        work_start_hour=work_start_hour,
        work_end_hour=work_end_hour,
    )


@mcp.tool()
def get_upcoming_events(hours: int = 48) -> list[dict]:
    """Get upcoming events from Google Calendar.

    Call this when Iryna asks about her schedule, upcoming interviews,
    or wants to see what's planned.

    Args:
      hours: how many hours ahead to look (default 48)

    Returns: list of {event_id, title, start, end, location, description}
    """
    return _cal.get_upcoming_events(hours=hours)


# ---- Gmail ----

@mcp.tool()
def get_email_summary(
    hours: int = 24,
    max_emails: int = 40,
) -> list[dict]:
    """Fetch recent emails from Gmail INBOX and return structured list.

    Call this when Iryna asks about email, wants a summary, or runs /email.
    Always call this first, then analyse and summarise the results.

    Skip newsletters, automated notifications, no-reply senders automatically.

    Args:
      hours: how many hours back to look (default 24)
      max_emails: max emails to fetch (default 40)

    Returns: list of {subject, from, date, snippet, body_preview, message_id}

    After getting results — group by priority:
    🔴 Термінові / потребують відповіді
    🟡 Важливі / для ознайомлення
    ⚪ Інформаційні / можна пізніше
    """
    return _gmail.get_recent_emails(hours=hours, max_emails=max_emails)


# ---- Telegram channel search ----

@mcp.tool()
def search_telegram_channels(
    keywords: list[str],
    channels: Optional[list[str]] = None,
    max_posts_per_channel: int = 40,
) -> dict:
    """Search public Telegram channels for posts matching keywords.

    Call this when Iryna runs /tgsearch or asks to find candidates in Telegram.
    Scans recent posts in recruiting/job channels and returns matching ones.

    Default channels: djinni_jobs, dou_jobs, affiliatework, igamingvacancies,
    jobs_marketing_ua, remote_jobs_ua, bd_sales_jobs, adtech_jobs.

    Args:
      keywords: words to match in posts (e.g. ["affiliate manager", "igaming", "media buyer"])
      channels: override channel list — usernames without @ (optional)
      max_posts_per_channel: how many recent posts to scan per channel (default 40)

    Returns: {total_scanned, channels_checked, matches_found, results: [{channel, text, link, date}]}

    After getting results — summarise the best matches for Iryna with channel, snippet, and link.
    If no matches — suggest expanding keywords or adding more channels.
    """
    return _tg.search_telegram_channels(
        keywords=keywords,
        channels=channels,
        max_posts_per_channel=max_posts_per_channel,
    )


# ---- Telegram deep search (via personal account / Telethon) ----

@mcp.tool()
def search_telegram_deep(
    keywords: list[str],
    channels: Optional[list[str]] = None,
    max_messages: int = 100,
    niche: Optional[str] = None,
) -> dict:
    """Deep search of Telegram channels via Iryna's personal account (Telethon).

    Reads up to 100+ messages per channel — much more than the public web scraper.
    Can access private channels where Iryna is a member.

    Use this when:
    - /tgsearch returns few results
    - Searching for Media Buyer, Affiliate, iGaming candidates specifically
    - Iryna wants to search private channels she's a member of

    niche presets (auto-selects relevant channels if channels not specified):
      "media_buyer" — affiliate, traffic arbitrage, media buying channels
      "igaming"     — iGaming specific channels
      "default"     — general recruiting channels

    Args:
      keywords: words to match (e.g. ["media buyer", "арбітраж", "Facebook ads"])
      channels: list of @usernames without @ to scan (optional, overrides niche)
      max_messages: messages to scan per channel (default 100)
      niche: "media_buyer" | "igaming" | "default" — auto-selects channel list

    Returns: {total_channels, matches_found, results: [{channel, text, link, date}]}
    """
    if channels:
        target = channels
    elif niche == "media_buyer":
        target = _tg.MEDIA_BUYER_CHANNELS
    else:
        target = _tg.DEFAULT_CHANNELS

    return _tgreader.search_channels_deep(
        keywords=keywords,
        channels=target,
        max_messages=max_messages,
    )


# ---- Telegram sender (personal account) ----

@mcp.tool()
def send_telegram_message(
    recipient: str,
    message: str,
) -> dict:
    """Send a Telegram message from Iryna's personal account via Telethon.

    Use this to send rejections, interview invitations, or any message to a candidate.
    Always show Iryna the message text FIRST and get confirmation before sending.

    Args:
      recipient: Telegram @username or phone number (+380...)
      message: message text to send

    Returns: {ok, recipient, name}
    """
    return _tgsend.send_message(recipient=recipient, text=message)


@mcp.tool()
def get_telegram_sender_info() -> dict:
    """Check which Telegram account is authorized for sending.

    Call this to verify the sender account is set up correctly.

    Returns: {id, name, username, phone}
    """
    return _tgsend.get_sender_info()


# ---- LinkedIn X-Ray sourcing ----

@mcp.tool()
def find_candidates(
    position: str,
    location: str,
    keywords: Optional[list[str]] = None,
    max_results: int = 15,
    save_to_sheet: bool = True,
) -> dict:
    """Search for real LinkedIn candidates via Google X-Ray (Serper API).

    Returns a list of LinkedIn profiles and saves them to Google Sheets tracker.
    Use this when Iryna asks to find candidates, do sourcing, or search LinkedIn.

    Args:
      position: job title to search for, e.g. "Head of Recruitment", "Affiliate Manager"
      location: location to filter by, e.g. "Ukraine", "Poland", "Remote"
      keywords: optional extra keywords to narrow search, e.g. ["iGaming", "affiliate"]
      max_results: max number of profiles to return (default 15, max 30)
      save_to_sheet: save found candidates to Google Sheets tracker (default True)

    Returns: {candidates: [...], saved: N, sheet_url: "..."}
    """
    candidates = _sourcing.find_linkedin_candidates(
        position=position,
        location=location,
        keywords=keywords,
        max_results=min(max_results, 30),
    )

    saved = 0
    sheet_url = ""
    if save_to_sheet and candidates:
        for c in candidates:
            try:
                result = _sheets.track_candidate(
                    name=c["full_name"],
                    profile_url=c["url"],
                    role=position,
                    status="New",
                    source="LinkedIn X-Ray",
                    comment=c.get("headline", "") or c.get("snippet", "")[:200],
                )
                saved += 1
                if not sheet_url:
                    sheet_url = result.get("sheet_url", "")
            except Exception as exc:
                log.warning("track_candidate failed for %s: %s", c.get("full_name"), exc)

    return {"candidates": candidates, "saved": saved, "sheet_url": sheet_url}


# ---- Reminders ----

@mcp.tool()
def set_reminder(
    text: str,
    when: str,
    repeat: str = "once",
) -> dict:
    """Set a reminder. Scout will send a message at the specified time.

    Use this when Iryna asks to be reminded about anything:
    - medicines, calls, tasks (repeat='once' or 'daily')
    - employee birthdays (repeat='yearly') — automatically also creates a gift reminder 2 days before
    - any recurring event

    Args:
      text: reminder text, e.g. "парацетамол малому 6 мл" or "день народження Олени"
      when: ISO datetime string in Warsaw time, e.g. "2026-06-12 22:20:00" or "2026-06-14 09:00:00"
      repeat: 'once' | 'daily' | 'weekly' | 'yearly'

    Returns: {ok, reminder_id, remind_at, repeat}
    """
    import psycopg
    from datetime import datetime, timedelta
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    remind_dt = datetime.fromisoformat(when)

    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO reminders (text, remind_at, repeat)
               VALUES (%s, %s, %s) RETURNING id""",
            (text, remind_dt, repeat),
        )
        reminder_id = cur.fetchone()[0]

        # For yearly birthday reminders — also add a gift reminder 2 days before
        if repeat == "yearly" and any(w in text.lower() for w in ["народження", "birthday", "др", "bday"]):
            gift_dt = remind_dt - timedelta(days=2)
            name_hint = text.replace("день народження", "").replace("birthday", "").strip(" -:,")
            gift_text = f"Замов подарунок — {name_hint} (др через 2 дні)" if name_hint else "Замов подарунок (др через 2 дні)"
            cur.execute(
                """INSERT INTO reminders (text, remind_at, repeat)
                   VALUES (%s, %s, %s)""",
                (gift_text, gift_dt, "yearly"),
            )

    return {"ok": True, "reminder_id": reminder_id, "remind_at": str(remind_dt), "repeat": repeat}


@mcp.tool()
def list_reminders() -> list[dict]:
    """List all upcoming reminders.

    Returns: list of {id, text, remind_at, repeat}
    """
    import psycopg
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return []
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, text, remind_at, repeat FROM reminders ORDER BY remind_at LIMIT 50"
        )
        rows = cur.fetchall()
    return [{"id": r[0], "text": r[1], "remind_at": str(r[2]), "repeat": r[3]} for r in rows]


@mcp.tool()
def delete_reminder(reminder_id: int) -> dict:
    """Delete a reminder by ID.

    Args:
      reminder_id: the ID from list_reminders

    Returns: {ok, deleted}
    """
    import psycopg
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
        deleted = cur.rowcount
    return {"ok": True, "deleted": deleted}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT, path="/mcp")
