from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from errors import AppError

TTS_TTL = timedelta(hours=24)
ROOT_DIR = Path(__file__).resolve().parent.parent
TTS_DIR = ROOT_DIR / "storage" / "tts"


def get_tts_dir() -> Path:
    return TTS_DIR


def new_tts_id() -> str:
    return f"tts_{uuid.uuid4()}"


def _is_safe_tts_id(audio_id: str) -> bool:
    return audio_id.startswith("tts_") and "/" not in audio_id and ".." not in audio_id


def save_tts(data: bytes, content_type: str, extension: str) -> str:
    tts_dir = get_tts_dir()
    tts_dir.mkdir(parents=True, exist_ok=True)
    audio_id = new_tts_id()
    audio_path = tts_dir / f"{audio_id}.{extension}"
    audio_path.write_bytes(data)
    meta_path = tts_dir / f"{audio_id}.json"
    meta_path.write_text(
        json.dumps(
            {
                "audio_id": audio_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "content_type": content_type,
                "extension": extension,
                "size_bytes": len(data),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return audio_id


def load_tts(audio_id: str) -> tuple[bytes, str]:
    if not _is_safe_tts_id(audio_id):
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "语音文件不存在或已过期。",
            "audio",
        )

    meta_path = get_tts_dir() / f"{audio_id}.json"
    if not meta_path.is_file():
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "语音文件不存在或已过期。",
            "audio",
        )

    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(str(metadata["created_at"]))
        extension = str(metadata["extension"])
        content_type = str(metadata["content_type"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "语音文件不存在或已过期。",
            "audio",
        ) from exc

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > TTS_TTL:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "语音文件不存在或已过期。",
            "audio",
        )

    audio_path = get_tts_dir() / f"{audio_id}.{extension}"
    if not audio_path.is_file():
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "语音文件不存在或已过期。",
            "audio",
        )
    return audio_path.read_bytes(), content_type
