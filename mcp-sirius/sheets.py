# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Google Sheets integration — append research articles."""
from __future__ import annotations

import logging
import os
from datetime import date

import gauth

log = logging.getLogger(__name__)

SHEET_ID = os.environ.get("RESEARCH_SHEET_ID", "").strip() or None
SHEET_NAME = "Articles"


def _svc():
    return gauth.service("sheets", "v4")


def _ensure_header(sheet_id: str) -> None:
    """Add header row if sheet is empty."""
    result = _svc().spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A1:F1",
    ).execute()
    if result.get("values"):
        return
    _svc().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [["Дата", "Заголовок", "URL", "Самарі", "Тема", "Джерело"]]},
    ).execute()


def save_article(
    title: str,
    url: str,
    summary: str,
    topic: str = "",
    source: str = "",
) -> dict:
    """Append one article row to the research Google Sheet."""
    if not SHEET_ID:
        raise RuntimeError(
            "RESEARCH_SHEET_ID env var is not set. "
            "Create a Google Sheet and add its ID to .env."
        )
    _ensure_header(SHEET_ID)
    row = [date.today().isoformat(), title, url, summary, topic, source]
    result = _svc().spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    updates = result.get("updates", {})
    log.info("sheets: saved article '%s' to sheet %s", title, SHEET_ID)
    return {
        "sheet_id": SHEET_ID,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}",
        "updated_range": updates.get("updatedRange", ""),
        "title": title,
    }


def create_research_sheet(name: str = "Sirius Research") -> str:
    """Create a new Google Sheet and return its ID."""
    body = {
        "properties": {"title": name},
        "sheets": [{"properties": {"title": SHEET_NAME}}],
    }
    result = _svc().spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sheet_id = result["spreadsheetId"]
    log.info("sheets: created new sheet '%s' id=%s", name, sheet_id)
    return sheet_id
