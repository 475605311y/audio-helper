from __future__ import annotations


def detect_audio_format(data: bytes, content_type: str | None = None) -> tuple[str, str] | None:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav", "audio/wav"
    if data.startswith(b"OggS"):
        return "ogg", "audio/ogg"
    if data.startswith(b"ID3") or _looks_like_mpeg(data):
        return "mp3", "audio/mpeg"
    if _looks_like_mp4(data):
        return "m4a", "audio/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm", "audio/webm"
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime in {"audio/wav", "audio/x-wav", "audio/wave"} and data.startswith(b"RIFF"):
        return "wav", "audio/wav"
    return None


def _looks_like_mpeg(data: bytes) -> bool:
    return len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0


def _looks_like_mp4(data: bytes) -> bool:
    return len(data) >= 12 and data[4:8] == b"ftyp"
