from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile

from errors import AppError
from schemas import SuccessResponse, UploadData
from services.audio_probe import probe_audio
from services.audio_store import get_audio_dir, new_audio_id, write_audio_metadata

router = APIRouter()
logger = logging.getLogger(__name__)

STAGE = "upload"
MAX_FILE_BYTES = 5 * 1024 * 1024
MIN_DURATION_SECONDS = 1.0
MAX_DURATION_SECONDS = 60.0
READ_CHUNK_BYTES = 64 * 1024


@router.post("/upload", response_model=SuccessResponse[UploadData])
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
) -> SuccessResponse[UploadData]:
    data = await _read_limited(file)
    if not data:
        raise AppError(
            413,
            "FILE_TOO_LARGE",
            "录音文件超过5MB，请缩短录音后重试。",
            STAGE,
        )

    audio_dir = get_audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=audio_dir, suffix=".bin", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        probe = probe_audio(tmp_path)
        _validate_duration(probe.duration_seconds)

        audio_id = new_audio_id()
        final_path = audio_dir / f"{audio_id}.{probe.extension}"
        tmp_path.replace(final_path)
        tmp_path = None
        try:
            write_audio_metadata(audio_id, final_path, probe)
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise

    logger.info(
        "upload ok request_id=%s audio_id=%s duration=%.3f size=%s container=%s codec=%s",
        request.state.request_id,
        audio_id,
        probe.duration_seconds,
        len(data),
        probe.container,
        probe.codec,
    )
    return SuccessResponse(
        request_id=request.state.request_id,
        data=UploadData(audio_id=audio_id),
    )


async def _read_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise AppError(
                413,
                "FILE_TOO_LARGE",
                "录音文件超过5MB，请缩短录音后重试。",
                STAGE,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_duration(duration_seconds: float) -> None:
    if duration_seconds < MIN_DURATION_SECONDS or duration_seconds > MAX_DURATION_SECONDS:
        raise AppError(
            422,
            "DURATION_INVALID",
            "录音需在1到60秒之间，请重新录制。",
            STAGE,
        )
