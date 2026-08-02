"""Speech-to-text for voice notes — Groq Whisper primary, Gemini audio fallback.

Used by the Telegram voice-note path. WhatsApp voice notes are the production
channel; Telegram is the demo equivalent with the same shape (download the file,
transcribe, feed the text into the agent).
"""

from __future__ import annotations

import logging
import os

import httpx

from app.config import settings

log = logging.getLogger(__name__)

WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
MAX_AUDIO_BYTES = 8 * 1024 * 1024

# Groq Whisper accepts these extensions; Telegram often ships Opus as .oga.
_GROQ_SAFE_EXTS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}


def groq_safe_filename(filename: str) -> str:
    """Map Telegram / odd extensions onto a Groq-supported name (keep audio bytes)."""
    base = os.path.basename(filename or "") or "voice-note.ogg"
    root, ext = os.path.splitext(base)
    lower = ext.lower()
    if lower in _GROQ_SAFE_EXTS:
        return base if root else f"voice-note{lower}"
    # Telegram voice notes: Opus in an OGG container, frequently named .oga / .opus
    if lower in {".oga", ".opus", ".ogg"} or not lower:
        return "voice-note.ogg"
    return "voice-note.ogg"


async def transcribe_audio(data: bytes, filename: str = "voice-note.ogg") -> str:
    """Return a transcript for raw audio bytes, or an empty string on failure."""
    if not data:
        return ""
    if len(data) > MAX_AUDIO_BYTES:
        log.warning("Audio too large: %s bytes", len(data))
        return ""

    safe_name = groq_safe_filename(filename)

    if settings.GROQ_API_KEY.strip():
        text = await _transcribe_groq(data, safe_name)
        if text:
            return text

    if settings.GEMINI_API_KEY.strip():
        return await _transcribe_gemini(data, safe_name)

    log.warning("No GROQ_API_KEY or GEMINI_API_KEY — cannot transcribe")
    return ""


async def _transcribe_groq(data: bytes, filename: str) -> str:
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        # Explicit MIME helps when Telegram labels Opus as application/octet-stream.
        result = await client.audio.transcriptions.create(
            file=(filename, data, _mime_for(filename)),
            model=WHISPER_MODEL,
            response_format="json",
        )
        return (getattr(result, "text", "") or "").strip()
    except Exception as e:  # noqa: BLE001
        log.warning("Groq transcription failed: %s", e)
        return ""


def _mime_for(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".mp3"):
        return "audio/mpeg"
    if lower.endswith(".wav"):
        return "audio/wav"
    if lower.endswith(".m4a") or lower.endswith(".mp4"):
        return "audio/mp4"
    if lower.endswith(".webm"):
        return "audio/webm"
    if lower.endswith(".flac"):
        return "audio/flac"
    # .ogg / .oga / Telegram voice
    return "audio/ogg"


async def _transcribe_gemini(data: bytes, filename: str) -> str:
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text=(
                                "Transcribe this voice note verbatim. Output only the "
                                "transcript text, no commentary."
                            )
                        ),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=_mime_for(filename), data=data
                            )
                        ),
                    ],
                )
            ],
        )
        return (resp.text or "").strip()
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini transcription failed: %s", e)
        return ""


async def transcribe_telegram_voice(file_id: str) -> str:
    """Download a Telegram voice note by file_id and transcribe it."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not file_id:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            meta = await client.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id},
            )
            file_path = ((meta.json() or {}).get("result") or {}).get("file_path")
            if not file_path:
                log.warning("Telegram getFile returned no path for %s", file_id)
                return ""
            audio = await client.get(
                f"https://api.telegram.org/file/bot{token}/{file_path}"
            )
            audio.raise_for_status()
            data = audio.content
    except Exception as e:  # noqa: BLE001
        log.warning("Telegram voice download failed: %s", e)
        return ""

    filename = groq_safe_filename(os.path.basename(file_path) or "voice-note.ogg")
    return await transcribe_audio(data, filename)
