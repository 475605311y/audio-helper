from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.audio_probe import AudioProbeResult

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
