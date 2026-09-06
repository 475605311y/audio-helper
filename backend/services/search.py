from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from errors import AppError
from schemas import PoiItem, SearchData, SearchRequest
from services.amap import fetch_around
from services.geo import (
    amap_text,
    format_location,
    haversine_m,
    midpoint,
    normalize_city,
    parse_location,
    parse_nonneg_number,
)
from services.geocode_resolve import CROSS_CITY_MESSAGE, ResolvedPlace, resolve_location
from services.search_store import new_search_id, save_search

logger = logging.getLogger(__name__)

STAGE = "search"
SEARCH_BUDGET_SECONDS = 12.0
GEOCODE_TIMEOUT_SECONDS = 3.5
AROUND_TIMEOUT_SECONDS = 3.5
FIRST_RADIUS_M = 2000
EXPAND_RADIUS_M = 5000
MAX_POIS = 3
NO_POI_MESSAGE = "中点附近没有找到合适的店，请换个地点类别或说得更具体。"
TIMEOUT_MESSAGE = "地点查询超时，请稍后重试。"


def run_search(body: SearchRequest) -> SearchData:
    deadline = time.monotonic() + SEARCH_BUDGET_SECONDS
    place_a, place_b = _resolve_both(body, deadline)
    if normalize_city(place_a.city) != normalize_city(place_b.city):
        raise AppError(422, "CROSS_CITY", CROSS_CITY_MESSAGE, STAGE)
    center = midpoint(place_a.location, place_b.location)
    pois, radius_m = _search_pois(center, body.category, place_a.city, deadline)
    if not pois:
        raise AppError(422, "NO_POI", NO_POI_MESSAGE, STAGE)

    created_at = datetime.now(timezone.utc).isoformat()
    search_id = new_search_id()
    payload = {
        "search_id": search_id,
        "created_at": created_at,
        "city_a": body.city_a,
        "address_a": body.address_a,
        "city_b": body.city_b,
        "address_b": body.address_b,
        "category": body.category,
        "midpoint": {"longitude": center[0], "latitude": center[1]},
        "radius_m": radius_m,
        "pois": [item.model_dump() for item in pois],
    }
    save_search(payload)
    logger.info(
        "search ok search_id=%s radius=%s poi_count=%s",
        search_id,
        radius_m,
        len(pois),
    )
    return SearchData(
        search_id=search_id,
        midpoint={"longitude": center[0], "latitude": center[1]},
        pois=pois,
    )


def _resolve_both(
    body: SearchRequest,
    deadline: float,
) -> tuple[ResolvedPlace, ResolvedPlace]:
    timeout = min(GEOCODE_TIMEOUT_SECONDS, _remaining(deadline))
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(resolve_location, body.address_a, body.city_a, timeout)
        future_b = pool.submit(resolve_location, body.address_b, body.city_b, timeout)
        place_a = future_a.result()
        place_b = future_b.result()
    return place_a, place_b


def _search_pois(
    center: tuple[float, float],
    category: str,
    city: str,
    deadline: float,
) -> tuple[list[PoiItem], int]:
    first = _around_valid(center, category, city, FIRST_RADIUS_M, deadline)
    if first:
        return first[:MAX_POIS], FIRST_RADIUS_M
    expanded = _around_valid(center, category, city, EXPAND_RADIUS_M, deadline)
    return expanded[:MAX_POIS], EXPAND_RADIUS_M


def _around_valid(
    center: tuple[float, float],
    category: str,
    city: str,
    radius: int,
    deadline: float,
) -> list[PoiItem]:
    timeout = min(AROUND_TIMEOUT_SECONDS, _remaining(deadline))
    body = fetch_around(format_location(center), category, radius, city, timeout)
    raw_pois = body.get("pois")
    if not isinstance(raw_pois, list):
        return []
    return _select_pois(raw_pois, center)


def _select_pois(raw_pois: list, center: tuple[float, float]) -> list[PoiItem]:
    items: list[PoiItem] = []
    for raw in raw_pois:
        if not isinstance(raw, dict):
            continue
        name = amap_text(raw.get("name"))
        if name is None:
            continue
        location = parse_location(raw.get("location"))
        distance = parse_nonneg_number(raw.get("distance"))
        if distance is None:
            if location is None:
                continue
            distance = haversine_m(center[0], center[1], location[0], location[1])
        items.append(
            PoiItem(
                name=name,
                address=amap_text(raw.get("address")) or "",
                distance_to_midpoint_m=round(distance, 1),
            )
        )
    items.sort(key=lambda item: item.distance_to_midpoint_m)
    return items


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise AppError(504, "UPSTREAM_TIMEOUT", TIMEOUT_MESSAGE, STAGE)
    return left
