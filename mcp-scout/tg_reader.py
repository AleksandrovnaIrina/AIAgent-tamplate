# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Deep Telegram channel search via Telethon (personal account).

Uses the same Telethon session as tg_sender so no extra auth is needed.
Can read private channels where Iryna is a member — not just public ones.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SESSION_PATH = str(
    Path(os.environ.get("GOOGLE_SECRETS_DIR", "/app/secrets")) / "scout_sender.session"
)
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")


def _run_in_thread(coro):
    result = None
    error = None

    def runner():
        nonlocal result, error
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
        except Exception as e:
            error = e
        finally:
            loop.close()

    t = threading.Thread(target=runner)
    t.start()
    t.join(timeout=60)
    if error:
        raise error
    return result


async def _search_channels_async(
    keywords: list[str],
    channels: list[str],
    max_messages: int,
) -> list[dict]:
    from telethon import TelegramClient
    from telethon.tl.types import Message

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    results: list[dict] = []
    keywords_lower = [kw.lower() for kw in keywords]

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log.warning("tg_reader: not authorized — use setup_telegram_sender.py")
            return []

        for channel in channels:
            is_invite = channel.startswith("https://t.me/+") or channel.startswith("https://t.me/joinchat/")
            display_name = channel if is_invite else f"@{channel.lstrip('@')}"
            channel_key = channel if is_invite else channel.lstrip("@")
            try:
                entity = await client.get_entity(channel_key)
                messages = await client.get_messages(entity, limit=max_messages)
                for msg in messages:
                    if not isinstance(msg, Message) or not msg.text:
                        continue
                    text_lower = msg.text.lower()
                    if any(kw in text_lower for kw in keywords_lower):
                        username = getattr(entity, "username", None)
                        link = (
                            f"https://t.me/{username}/{msg.id}"
                            if username
                            else f"https://t.me/c/{entity.id}/{msg.id}"
                        )
                        results.append({
                            "channel": display_name,
                            "text": msg.text[:800],
                            "link": link,
                            "date": msg.date.strftime("%Y-%m-%d") if msg.date else "",
                        })
                log.info("tg_reader: %s — %d messages scanned", display_name, len(messages))
            except Exception as e:
                log.warning("tg_reader: failed to read %s: %s", display_name, e)
    finally:
        await client.disconnect()

    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    return results


def search_channels_deep(
    keywords: list[str],
    channels: list[str],
    max_messages: int = 100,
) -> dict:
    """Search Telegram channels via personal account (Telethon).

    Can read private channels where Iryna is a member.
    Returns more posts than the public web scraper.
    """
    if not API_ID or not API_HASH:
        return {
            "error": "TELEGRAM_API_ID / TELEGRAM_API_HASH not set",
            "results": [],
        }

    session_file = Path(SESSION_PATH)
    if not session_file.exists():
        return {
            "error": f"Session not found at {SESSION_PATH} — run setup_telegram_sender.py",
            "results": [],
        }

    try:
        results = _run_in_thread(
            _search_channels_async(keywords, channels, max_messages)
        )
        return {
            "total_channels": len(channels),
            "matches_found": len(results),
            "max_messages_per_channel": max_messages,
            "results": results,
        }
    except Exception as e:
        log.exception("tg_reader: search failed")
        return {"error": str(e), "results": []}
