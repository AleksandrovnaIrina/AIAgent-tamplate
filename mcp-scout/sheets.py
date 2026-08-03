# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Google Sheets — candidate tracker and research articles."""
from __future__ import annotations

import logging
import os
from datetime import date

import gauth

log = logging.getLogger(__name__)

CANDIDATE_SHEET_ID = os.environ.get("CANDIDATE_SHEET_ID", "").strip() or None
RESEARCH_SHEET_ID = os.environ.get("RESEARCH_SHEET_ID", "").strip() or None

CANDIDATES_TAB = "Candidates"
ARTICLES_TAB = "Articles"
JD_TAB = "Job Descriptions"


def _svc():
    return gauth.service("sheets", "v4")


def _ensure_header(sheet_id: str, tab: str, headers: list[str]) -> None:
    result = _svc().spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1:Z1",
    ).execute()
    if result.get("values"):
        return
    _svc().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [headers]},
    ).execute()


def track_candidate(
    name: str,
    profile_url: str,
    role: str,
    status: str,
    source: str = "",
    comment: str = "",
) -> dict:
    """Append a candidate row to the candidate tracker Google Sheet.

    Columns: Дата, Ім'я, Профіль URL, Роль, Статус, Джерело, Коментар
    """
    if not CANDIDATE_SHEET_ID:
        raise RuntimeError(
            "CANDIDATE_SHEET_ID env var is not set. "
            "Create a Google Sheet and add its ID to .env."
        )
    _ensure_header(
        CANDIDATE_SHEET_ID,
        CANDIDATES_TAB,
        ["Дата", "Ім'я", "Профіль URL", "Роль", "Статус", "Джерело", "Коментар"],
    )
    row = [date.today().isoformat(), name, profile_url, role, status, source, comment]
    result = _svc().spreadsheets().values().append(
        spreadsheetId=CANDIDATE_SHEET_ID,
        range=f"{CANDIDATES_TAB}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    log.info("sheets: tracked candidate '%s' for role '%s'", name, role)
    return {
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{CANDIDATE_SHEET_ID}",
        "candidate": name,
        "role": role,
        "status": status,
    }


def save_research_article(
    title: str,
    url: str,
    summary: str,
    topic: str = "",
    source: str = "",
) -> dict:
    """Append a research article to the research Google Sheet."""
    if not RESEARCH_SHEET_ID:
        raise RuntimeError(
            "RESEARCH_SHEET_ID env var is not set. "
            "Create a Google Sheet and add its ID to .env."
        )
    _ensure_header(
        RESEARCH_SHEET_ID,
        ARTICLES_TAB,
        ["Дата", "Заголовок", "URL", "Самарі", "Тема", "Джерело"],
    )
    row = [date.today().isoformat(), title, url, summary, topic, source]
    result = _svc().spreadsheets().values().append(
        spreadsheetId=RESEARCH_SHEET_ID,
        range=f"{ARTICLES_TAB}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    log.info("sheets: saved article '%s'", title)
    return {
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{RESEARCH_SHEET_ID}",
        "title": title,
    }


def save_job_description(
    title: str,
    content: str,
    company: str = "",
    department: str = "",
    status: str = "Draft",
) -> dict:
    """Save a Job Description to the JD tab of the candidate tracker Google Sheet.

    Columns: Дата, Роль, Компанія, Відділ, Статус, Текст JD
    """
    sheet_id = CANDIDATE_SHEET_ID
    if not sheet_id:
        raise RuntimeError(
            "CANDIDATE_SHEET_ID env var is not set. "
            "Create a Google Sheet and add its ID to .env."
        )
    _ensure_header(
        sheet_id,
        JD_TAB,
        ["Дата", "Роль", "Компанія", "Відділ", "Статус", "Текст JD"],
    )
    row = [date.today().isoformat(), title, company, department, status, content]
    _svc().spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f"{JD_TAB}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    log.info("sheets: saved JD '%s'", title)
    return {
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}",
        "title": title,
        "status": status,
    }


def list_job_descriptions(status: str = "") -> list[dict]:
    """List saved JDs from the Job Descriptions tab."""
    sheet_id = CANDIDATE_SHEET_ID
    if not sheet_id:
        raise RuntimeError("CANDIDATE_SHEET_ID env var is not set.")
    result = _svc().spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{JD_TAB}!A1:F1000",
    ).execute()
    rows = result.get("values", [])
    if not rows or len(rows) < 2:
        return []
    headers = rows[0]
    out = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        item = dict(zip(headers, padded))
        if not status or item.get("Статус", "") == status:
            out.append(item)
    return out
