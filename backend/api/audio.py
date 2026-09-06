from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import Response

from services.tts_store import load_tts

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/audio/{audio_id}")
def get_tts_audio(audio_id: str) -> Response:
    data, content_type = load_tts(audio_id)
    logger.info("audio ok audio_id=%s content_type=%s size=%s", audio_id, content_type, len(data))
    return Response(content=data, media_type=content_type)
