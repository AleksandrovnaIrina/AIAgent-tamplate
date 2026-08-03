# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Voice message transcription via Groq Whisper API."""
import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import httpx

log = logging.getLogger("lumys.voice")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Groq limit is 25MB; we split at 20MB chunks to be safe
_CHUNK_MB = 20
_CHUNK_BYTES = _CHUNK_MB * 1024 * 1024


def voice_enabled() -> bool:
    return bool(GROQ_API_KEY)


_MIME = {
    ".ogg": "audio/ogg", ".oga": "audio/ogg",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
    ".wav": "audio/wav", ".flac": "audio/flac",
}


async def _transcribe_bytes(audio_bytes: bytes, filename: str) -> Optional[str]:
    ext = os.path.splitext(filename)[1].lower()
    mime = _MIME.get(ext, "audio/ogg")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={"file": (filename, audio_bytes, mime)},
            data={"model": "whisper-large-v3-turbo", "language": "uk"},
        )
        resp.raise_for_status()
        return resp.json().get("text", "").strip() or None


def _split_audio_ffmpeg(audio_bytes: bytes, filename: str) -> list[bytes]:
    """Split audio into ~10-minute MP3 chunks using ffmpeg."""
    ext = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, f"input{ext}")
        Path(src).write_bytes(audio_bytes)
        out_pattern = os.path.join(tmpdir, "chunk_%03d.mp3")
        result = subprocess.run(
            [
                "ffmpeg", "-i", src,
                "-f", "segment", "-segment_time", "600",
                "-c:a", "libmp3lame", "-b:a", "64k",
                "-reset_timestamps", "1",
                out_pattern, "-y"
            ],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            log.warning("ffmpeg split failed: %s", result.stderr.decode())
            return [audio_bytes]
        chunks = sorted(Path(tmpdir).glob("chunk_*.mp3"))
        return [c.read_bytes() for c in chunks]


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> Optional[str]:
    if not voice_enabled():
        return None
    try:
        if len(audio_bytes) <= _CHUNK_BYTES:
            return await _transcribe_bytes(audio_bytes, filename)

        # Large file — split into chunks
        log.info("Audio too large (%dMB), splitting into chunks", len(audio_bytes) // 1024 // 1024)
        loop = asyncio.get_event_loop()
        chunks = await loop.run_in_executor(None, _split_audio_ffmpeg, audio_bytes, filename)
        parts = []
        for i, chunk in enumerate(chunks):
            log.info("Transcribing chunk %d/%d (%dKB)", i + 1, len(chunks), len(chunk) // 1024)
            text = await _transcribe_bytes(chunk, f"chunk_{i:03d}.mp3")
            if text:
                parts.append(text)
        return " ".join(parts) if parts else None
    except Exception as e:
        log.warning("Groq transcription failed: %s", e)
        return None
