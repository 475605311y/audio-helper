from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from schemas import ExtractData, ExtractRequest, SuccessResponse
from services.deepseek_extract import call_extract_model, parse_model_json
from services.extract import evaluate_extract, validate_model_output

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/extract", response_model=SuccessResponse[ExtractData])
def extract_meetup(request: Request, body: ExtractRequest) -> SuccessResponse[ExtractData]:
    raw = call_extract_model(body.text, body.city)
    payload = parse_model_json(raw)
    model = validate_model_output(payload)
    data = evaluate_extract(model, body.city)
    logger.info(
        "extract ok request_id=%s party_count=%s category=%s",
        request.state.request_id,
        model.party_count,
        data.category,
    )
    return SuccessResponse(request_id=request.state.request_id, data=data)
