"""Voice transcription helpers — Telegram .oga → Groq-safe names."""

from __future__ import annotations

from app.services.voice import groq_safe_filename, _mime_for


def test_groq_safe_filename_normalizes_telegram_oga():
    assert groq_safe_filename("voice/file_123.oga") == "voice-note.ogg"
    assert groq_safe_filename("note.opus") == "voice-note.ogg"
    assert groq_safe_filename("clip.ogg") == "clip.ogg"
    assert groq_safe_filename("song.mp3") == "song.mp3"
    assert groq_safe_filename("noext") == "voice-note.ogg"
    assert groq_safe_filename("") == "voice-note.ogg"


def test_mime_for_ogg_family():
    assert _mime_for("voice-note.ogg") == "audio/ogg"
    assert _mime_for("a.mp3") == "audio/mpeg"
    assert _mime_for("a.webm") == "audio/webm"
