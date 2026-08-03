# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Google Sheets integration for Argus — writes to content planning spreadsheet."""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger("argus.sheets")

CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "/app/google_credentials.json")
SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

REELS_SHEET = "Reels"
ANALYSIS_SHEET = "Аналіз"
CAROUSELS_SHEET = "Каруселі"

ANALYSIS_HEADERS = ["Дата", "Запит", "Аналіз"]
CAROUSELS_HEADERS = [
    "ID", "Status", "Topic", "Source_URL",
    "Slide_1", "Slide_2", "Slide_3", "Slide_4", "Slide_5",
    "Slide_6", "Slide_7", "Slide_8", "Slide_9",
    "Caption", "Scheduled", "Posted", "Notes", "Created"
]

REELS_HEADERS = [
    "ID", "Status", "From", "URL", "Hook", "Original_Script", "Script",
    "Caption", "CTA_Word", "CTA_Artifact", "CTA_TG_URL", "Video", "Notion",
    "Scheduled", "Posted", "Skip_Reason", "Created", "Updated",
    "Buffer_Post_ID", "Posted_URL", "Source_URL", "Cover"
]


def _client() -> Optional[gspread.Client]:
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        log.error("sheets auth failed: %s", e)
        return None


def _get_next_id(ws: gspread.Worksheet) -> int:
    ids = ws.col_values(1)[1:]
    numeric = []
    for x in ids:
        try:
            numeric.append(int(float(x)))
        except (ValueError, TypeError):
            pass
    return max(numeric, default=0) + 1


def write_posts(rows: list[dict]) -> bool:
    """Write scraped reels to the content planning sheet."""
    if not rows or not SPREADSHEET_ID:
        return False
    client = _client()
    if not client:
        return False
    try:
        ss = client.open_by_key(SPREADSHEET_ID)
        try:
            ws = ss.worksheet(REELS_SHEET)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=REELS_SHEET, rows=1000, cols=len(REELS_HEADERS))
            ws.append_row(REELS_HEADERS, value_input_option="USER_ENTERED")
            ws.format("1:1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)

        def _clean(text: str, max_len: int = 2000) -> str:
            return (text or "").replace("\n", " ").replace("\r", "").strip()[:max_len]

        next_id = _get_next_id(ws)
        now = datetime.now(timezone.utc).strftime("%d/%m/%y %H:%M")
        data = []
        for r in rows:
            posted = str(r.get("posted_at", ""))[:10] if r.get("posted_at") else ""
            data.append([
                str(next_id),  # string to prevent Google Sheets from converting to date
                "draft",
                r.get("competitor_handle", ""),
                r.get("post_url", ""),
                _clean(r.get("hook") or "", 200),
                _clean(r.get("original_transcript") or r.get("transcript") or ""),
                _clean(r.get("transcript_ua") or r.get("transcript") or ""),
                "",  # Caption — заповнює користувач
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
        log.info("wrote %d rows to sheets", len(data))
        return True
    except Exception as e:
        log.error("sheets write_posts failed: %s", e)
        return False


def update_caption(post_url: str, caption: str) -> bool:
    """Update the Caption cell for a row identified by post URL."""
    if not SPREADSHEET_ID:
        return False
    client = _client()
    if not client:
        return False
    try:
        ss = client.open_by_key(SPREADSHEET_ID)
        ws = ss.worksheet(REELS_SHEET)
        urls = ws.col_values(4)  # column D = URL
        for i, url in enumerate(urls):
            if url == post_url:
                row_num = i + 1
                caption_col = REELS_HEADERS.index("Caption") + 1
                ws.update_cell(row_num, caption_col, caption)
                log.info("updated caption for row %d", row_num)
                return True
        log.warning("post_url not found in sheet: %s", post_url)
        return False
    except Exception as e:
        log.error("update_caption failed: %s", e)
        return False


def write_carousel(topic: str, slides: list[str], caption: str, source_url: str = "") -> bool:
    """Save a generated carousel to the Каруселі sheet."""
    if not SPREADSHEET_ID:
        return False
    client = _client()
    if not client:
        return False
    try:
        ss = client.open_by_key(SPREADSHEET_ID)
        try:
            ws = ss.worksheet(CAROUSELS_SHEET)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=CAROUSELS_SHEET, rows=500, cols=len(CAROUSELS_HEADERS))
            ws.append_row(CAROUSELS_HEADERS, value_input_option="RAW")
            ws.format("1:1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)

        next_id = _get_next_id(ws)
        now = datetime.now(timezone.utc).strftime("%d/%m/%y %H:%M")
        padded = (slides + [""] * 9)[:9]
        row = [
            str(next_id), "draft", topic, source_url,
            *padded,
            caption, "", "", "", now
        ]
        ws.append_row(row, value_input_option="RAW")
        log.info("wrote carousel %d to sheets", next_id)
        return True
    except Exception as e:
        log.error("write_carousel failed: %s", e)
        return False


def write_analysis(query: str, analysis: str) -> bool:
    """Write bot analysis to the Аналіз sheet."""
    if not SPREADSHEET_ID:
        return False
    client = _client()
    if not client:
        return False
    try:
        ss = client.open_by_key(SPREADSHEET_ID)
        try:
            ws = ss.worksheet(ANALYSIS_SHEET)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=ANALYSIS_SHEET, rows=1000, cols=3)
            ws.append_row(ANALYSIS_HEADERS, value_input_option="USER_ENTERED")
            ws.format("1:1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        ws.append_row([today, query[:200], analysis[:2000]], value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        log.error("sheets write_analysis failed: %s", e)
        return False
