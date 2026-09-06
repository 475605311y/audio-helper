from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from schemas import AsrData, AsrRequest, SuccessResponse
from services.audio_store import load_recording
from services.bailian_asr import mime_for_extension, recognize_audio

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/asr", response_model=SuccessResponse[AsrData])
def create_transcript(request: Request, body: AsrRequest) -> SuccessResponse[AsrData]:
    data, metadata = load_recording(body.audio_id, stage="asr")
    mime_type = mime_for_extension(str(metadata.get("extension") or "webm"))
    text = recognize_audio(data, mime_type)
    logger.info(
        "asr ok request_id=%s audio_id=%s text_len=%s",
        request.state.request_id,
        body.audio_id,
        len(text),
    )
    return SuccessResponse(
        request_id=request.state.request_id,
        data=AsrData(text=text),
    )
