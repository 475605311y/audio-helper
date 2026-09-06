from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from errors import AppError
from services.audio_probe import AudioProbeResult

AUDIO_TTL = timedelta(hours=24)

ROOT_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT_DIR / "storage" / "audio"


def get_audio_dir() -> Path:
    return AUDIO_DIR


def new_audio_id() -> str:
    return f"rec_{uuid.uuid4()}"


def write_audio_metadata(
    audio_id: str,
    audio_path: Path,
    probe: AudioProbeResult,
) -> None:
    meta_path = get_audio_dir() / f"{audio_id}.json"
    created_at = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(
        json.dumps(
            {
                "audio_id": audio_id,
                "created_at": created_at,
                "container": probe.container,
                "codec": probe.codec,
                "duration_seconds": probe.duration_seconds,
                "size_bytes": audio_path.stat().st_size,
                "extension": probe.extension,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _is_safe_audio_id(audio_id: str) -> bool:
    return audio_id.startswith("rec_") and "/" not in audio_id and ".." not in audio_id


def load_recording(audio_id: str, stage: str) -> tuple[bytes, dict]:
    if not _is_safe_audio_id(audio_id):
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音不存在或已过期，请重新录音。",
            stage,
        )

    meta_path = get_audio_dir() / f"{audio_id}.json"
    if not meta_path.is_file():
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音不存在或已过期，请重新录音。",
            stage,
        )

    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(str(metadata["created_at"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音不存在或已过期，请重新录音。",
            stage,
        ) from exc

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > AUDIO_TTL:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音不存在或已过期，请重新录音。",
            stage,
        )

    extension = str(metadata.get("extension") or "webm")
    audio_path = get_audio_dir() / f"{audio_id}.{extension}"
    if not audio_path.is_file():
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音不存在或已过期，请重新录音。",
            stage,
        )

    return audio_path.read_bytes(), metadata


def save_audio(
    data: bytes,
    probe: AudioProbeResult,
    audio_id: str | None = None,
) -> str:
    audio_dir = get_audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    stored_id = audio_id or new_audio_id()
    audio_path = audio_dir / f"{stored_id}.{probe.extension}"
    audio_path.write_bytes(data)
    write_audio_metadata(stored_id, audio_path, probe)
    return stored_id
