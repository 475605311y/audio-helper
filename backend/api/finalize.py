from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from schemas import FinalizeData, FinalizeRequest, SuccessResponse
from services.finalize import run_finalize

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/finalize", response_model=SuccessResponse[FinalizeData])
def finalize_meetup(
    request: Request,
    body: FinalizeRequest,
) -> SuccessResponse[FinalizeData]:
    data = run_finalize(body.search_id)
    logger.info(
        "finalize ok request_id=%s search_id=%s has_audio=%s",
        request.state.request_id,
        body.search_id,
        data.audio_url is not None,
    )
    return SuccessResponse(request_id=request.state.request_id, data=data)
