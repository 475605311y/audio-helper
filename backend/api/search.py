from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from schemas import SearchData, SearchRequest, SuccessResponse
from services.search import run_search

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/search", response_model=SuccessResponse[SearchData])
def search_meetup(request: Request, body: SearchRequest) -> SuccessResponse[SearchData]:
    data = run_search(body)
    logger.info(
        "search ok request_id=%s search_id=%s poi_count=%s",
        request.state.request_id,
        data.search_id,
        len(data.pois),
    )
    return SuccessResponse(request_id=request.state.request_id, data=data)
