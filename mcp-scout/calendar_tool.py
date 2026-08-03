# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Google Calendar integration — free slots and upcoming events."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, time
from typing import Optional
from zoneinfo import ZoneInfo

import gauth

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Warsaw")
UTC = timezone.utc


def _svc():
    return gauth.service("calendar", "v3")


def _dt_to_str(dt: datetime) -> str:
    return dt.strftime("%d.%m %H:%M")


def get_free_slots(
    days: int = 3,
    slot_duration_minutes: int = 45,
    work_start_hour: int = 9,
    work_end_hour: int = 18,
    calendar_id: str = "primary",
) -> dict:
    """Find free time slots in Google Calendar for scheduling interviews.

    Args:
      days: how many days ahead to look (default 3)
      slot_duration_minutes: interview duration in minutes (default 45)
      work_start_hour: working day start hour in Warsaw time (default 9)
      work_end_hour: working day end hour in Warsaw time (default 18)
      calendar_id: calendar ID (default 'primary')

    Returns: {slots: [{start, end, label}], timezone, generated_at}
    """
    now = datetime.now(TZ)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    # Get busy times via freebusy API
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": "Europe/Warsaw",
        "items": [{"id": calendar_id}],
    }
    result = _svc().freebusy().query(body=body).execute()
    busy_periods = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])

    busy = []
    for b in busy_periods:
        start = datetime.fromisoformat(b["start"].replace("Z", "+00:00")).astimezone(TZ)
        end = datetime.fromisoformat(b["end"].replace("Z", "+00:00")).astimezone(TZ)
        busy.append((start, end))

    # Generate free slots
    free_slots = []
    slot_delta = timedelta(minutes=slot_duration_minutes)

    for day_offset in range(days):
        day = (now + timedelta(days=day_offset)).date()
        # Skip weekends
        if datetime(day.year, day.month, day.day).weekday() >= 5:
            continue

        work_start = datetime(day.year, day.month, day.day, work_start_hour, 0, tzinfo=TZ)
        work_end = datetime(day.year, day.month, day.day, work_end_hour, 0, tzinfo=TZ)

        cursor = max(work_start, now + timedelta(minutes=30))
        while cursor + slot_delta <= work_end:
            slot_end = cursor + slot_delta
            # Check if slot overlaps with any busy period
            overlap = any(
                cursor < b_end and slot_end > b_start
                for b_start, b_end in busy
            )
            if not overlap:
                free_slots.append({
                    "start": cursor.strftime("%Y-%m-%dT%H:%M"),
                    "end": slot_end.strftime("%Y-%m-%dT%H:%M"),
                    "label": f"{cursor.strftime('%a %d.%m')} {cursor.strftime('%H:%M')}–{slot_end.strftime('%H:%M')}",
                })
            cursor += timedelta(minutes=30)

    log.info("calendar: found %d free slots over %d days", len(free_slots), days)
    return {
        "slots": free_slots[:20],
        "timezone": "Europe/Warsaw",
        "slot_duration_minutes": slot_duration_minutes,
        "generated_at": now.strftime("%d.%m.%Y %H:%M"),
    }


def get_upcoming_events(
    hours: int = 48,
    calendar_id: str = "primary",
    max_results: int = 20,
) -> list[dict]:
    """Get upcoming calendar events (interviews, meetings).

    Args:
      hours: how many hours ahead to look (default 48)
      calendar_id: calendar ID (default 'primary')
      max_results: max events to return (default 20)

    Returns: list of {title, start, end, start_iso, location, description, event_id}
    """
    now = datetime.now(UTC)
    time_min = now.isoformat()
    time_max = (now + timedelta(hours=hours)).isoformat()

    result = _svc().events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for e in result.get("items", []):
        start_raw = e.get("start", {})
        end_raw = e.get("end", {})

        start_str = start_raw.get("dateTime") or start_raw.get("date", "")
        end_str = end_raw.get("dateTime") or end_raw.get("date", "")

        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(TZ)
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(TZ)
            start_label = start_dt.strftime("%a %d.%m %H:%M")
            end_label = end_dt.strftime("%H:%M")
            start_iso = start_dt.isoformat()
        except Exception:
            start_label = start_str
            end_label = end_str
            start_iso = start_str

        events.append({
            "event_id": e.get("id", ""),
            "title": e.get("summary", "(без назви)"),
            "start": start_label,
            "end": end_label,
            "start_iso": start_iso,
            "location": e.get("location", ""),
            "description": (e.get("description") or "")[:200],
        })

    log.info("calendar: %d upcoming events in next %dh", len(events), hours)
    return events


def get_events_starting_soon(minutes: int = 15) -> list[dict]:
    """Get events starting within the next N minutes. Used for reminders."""
    now = datetime.now(UTC)
    time_min = now.isoformat()
    time_max = (now + timedelta(minutes=minutes)).isoformat()

    result = _svc().events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=5,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for e in result.get("items", []):
        start_raw = e.get("start", {}).get("dateTime", "")
        if not start_raw:
            continue
        try:
            start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(TZ)
            minutes_left = int((start_dt.astimezone(UTC) - now).total_seconds() / 60)
            events.append({
                "event_id": e.get("id", ""),
                "title": e.get("summary", "(без назви)"),
                "start": start_dt.strftime("%H:%M"),
                "minutes_left": minutes_left,
                "location": e.get("location", ""),
            })
        except Exception:
            continue

    return events
