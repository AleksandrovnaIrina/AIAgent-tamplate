# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""YouTube transcript fetcher.

Primary: youtube-transcript-api (no API key, instant).
Fallback: yt-dlp + Groq Whisper (when subtitles are disabled/unavailable).
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile

import httpx
import requests as _requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

log = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip() or None
_ID_RE = re.compile(r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})")
MAX_WHISPER_MB = 24  # Groq limit is 25 MB


def _extract_video_id(url: str) -> str:
    m = _ID_RE.search(url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract YouTube video ID from: {url}")


def _get_metadata(video_id: str) -> dict:
    try:
        oembed = f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
        data = httpx.get(oembed, timeout=10, follow_redirects=True).json()
        return {"title": data.get("title", ""), "author": data.get("author_name", "")}
    except Exception:
        return {"title": "", "author": ""}


def _subtitles(video_id: str) -> list[dict] | None:
    """Try to get subtitles via youtube-transcript-api. Returns None if unavailable."""
    try:
        return YouTubeTranscriptApi.get_transcript(
            video_id, languages=["uk", "en", "ru", "pl"]
        )
    except (NoTranscriptFound, TranscriptsDisabled):
        pass
    try:
        tl = YouTubeTranscriptApi.list_transcripts(video_id)
        t = next(iter(tl), None)
        return t.fetch() if t else None
    except Exception:
        return None


def _whisper(video_id: str) -> str:
    """Download audio via yt-dlp and transcribe via Groq Whisper."""
    if not GROQ_API_KEY:
        raise ValueError(
            "Субтитри недоступні, а GROQ_API_KEY не встановлено — транскрипція неможлива."
        )

    url = f"https://youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = f"{tmpdir}/audio.mp3"
        log.info("youtube: downloading audio for %s via yt-dlp", video_id)
        result = subprocess.run(
            [
                "yt-dlp", "-x",
                "--audio-format", "mp3",
                "--audio-quality", "5",       # ~64kbps — small files
                "--match-filter", "duration <= 1800",  # max 30 min
                "-o", audio_path,
                url,
            ],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise ValueError(f"Не вдалось завантажити відео: {result.stderr[-300:]}")

        size_mb = os.path.getsize(audio_path) / 1_048_576
        if size_mb > MAX_WHISPER_MB:
            raise ValueError(
                f"Аудіо {size_mb:.1f} MB — перевищує ліміт Groq ({MAX_WHISPER_MB} MB). "
                "Спробуй коротше відео."
            )

        log.info("youtube: sending %.1f MB to Groq Whisper", size_mb)
        with open(audio_path, "rb") as f:
            resp = _requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"model": "whisper-large-v3-turbo", "response_format": "text"},
                timeout=180,
            )
        resp.raise_for_status()
        return resp.text.strip()


def get_transcript(url: str, max_chars: int = 15000) -> dict:
    """Fetch YouTube transcript + metadata.

    1. Tries subtitles (fast, free).
    2. Falls back to yt-dlp + Groq Whisper if subtitles are unavailable.
    """
    video_id = _extract_video_id(url)
    meta = _get_metadata(video_id)
    method = "subtitles"

    segments = _subtitles(video_id)
    if segments:
        full_text = " ".join(s["text"] for s in segments)
    else:
        log.info("youtube: no subtitles for %s — falling back to Whisper", video_id)
        method = "whisper"
        full_text = _whisper(video_id)

    truncated = len(full_text) > max_chars
    log.info("youtube: %s '%s' — %d chars via %s", video_id, meta["title"], len(full_text), method)

    return {
        "video_id": video_id,
        "url": f"https://youtube.com/watch?v={video_id}",
        "title": meta["title"],
        "author": meta["author"],
        "transcript": full_text[:max_chars],
        "word_count": len(full_text.split()),
        "truncated": truncated,
        "method": method,
    }
