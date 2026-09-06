from __future__ import annotations

import logging
import time

from config import settings
from errors import AppError
from schemas import FinalizeData
from services.bailian_tts import TtsDegraded, synthesize_and_store
from services.deepseek_finalize import generate_reply
from services.search_store import load_search

logger = logging.getLogger(__name__)

STAGE = "finalize"
FINALIZE_BUDGET_SECONDS = 25.0
NO_POI_MESSAGE = "没有可推荐的店铺，请重新搜索。"


def run_finalize(search_id: str) -> FinalizeData:
    deadline = time.monotonic() + FINALIZE_BUDGET_SECONDS
    payload = load_search(search_id, stage=STAGE)
    name, address, distance_m = _first_poi(payload)
    _ensure_budget(deadline)
    reply_text = generate_reply(name, address, distance_m)

    try:
        _ensure_budget(deadline)
        audio_id = synthesize_and_store(reply_text)
    except TtsDegraded as exc:
        logger.info("finalize tts degraded search_id=%s", search_id)
        return FinalizeData(
            reply_text=reply_text,
            audio_url=None,
            warning=exc.warning,
        )

    return FinalizeData(
        reply_text=reply_text,
        audio_url=_public_audio_url(audio_id),
        warning=None,
    )


def _first_poi(payload: dict) -> tuple[str, str, float | None]:
    pois = payload.get("pois")
    if not isinstance(pois, list):
        raise AppError(422, "NO_POI", NO_POI_MESSAGE, STAGE)
    for item in pois:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        address = str(item.get("address") or "").strip()
        if not name:
            continue
        distance = item.get("distance_to_midpoint_m")
        distance_m = distance if isinstance(distance, (int, float)) else None
        return name, address, distance_m
    raise AppError(422, "NO_POI", NO_POI_MESSAGE, STAGE)


def _public_audio_url(audio_id: str) -> str:
    return f"http://localhost:{settings.backend_port}/audio/{audio_id}"


def _ensure_budget(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "推荐语生成超时，请稍后重试。",
            STAGE,
        )
