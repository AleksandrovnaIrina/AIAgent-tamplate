# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Voice message transcription via Groq Whisper API."""

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("lumys.voice")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"


def voice_enabled() -> bool:
    return bool(GROQ_API_KEY)


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> Optional[str]:
    """Transcribe audio bytes using Groq Whisper. Returns transcript or None."""
    if not voice_enabled():
        return None

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    files = {"file": (filename, audio_bytes, "audio/ogg")}
    data = {"model": GROQ_MODEL}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                GROQ_TRANSCRIBE_URL, headers=headers, files=files, data=data
            )
            resp.raise_for_status()
            text = resp.json().get("text", "").strip()
            return text or None
    except Exception as e:
        log.warning("Groq transcription failed: %s", e)
        return None
