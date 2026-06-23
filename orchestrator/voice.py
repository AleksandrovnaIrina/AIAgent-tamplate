"""Voice message transcription via Groq Whisper API."""
import logging
import os
from typing import Optional
import httpx

log = logging.getLogger("lumys.voice")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def voice_enabled() -> bool:
    return bool(GROQ_API_KEY)


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> Optional[str]:
    if not voice_enabled():
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (filename, audio_bytes, "audio/ogg")},
                data={"model": "whisper-large-v3-turbo"},
            )
            resp.raise_for_status()
            return resp.json().get("text", "").strip() or None
    except Exception as e:
        log.warning("Groq transcription failed: %s", e)
        return None
