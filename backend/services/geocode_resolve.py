from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from errors import AppError
from services.amap import fetch_geocode
from services.geo import (
    SAME_PLACE_MAX_M,
    amap_text,
    haversine_m,
    normalize_city,
    parse_location,
)

logger = logging.getLogger(__name__)
PAREN_RE = re.compile(r"[（(][^（）()]*[）)]")

STAGE = "search"
AMBIGUOUS_MESSAGE = "有多个可能的地点，请补充更具体的站名或出入口。"
COARSE_MESSAGE = "地点不够具体，请说出车站或地标。"
UNMATCHED_MESSAGE = "无法确认这个地点，请说得更具体。"
CROSS_CITY_MESSAGE = "第一版只支持同一座城市内的两个人，请重新表达。"

REJECT_LEVELS = {
    "国家",
    "省",
    "市",
    "区县",
    "未知",
    "楼层",
    "房间",
    "道路",
    "乡镇",
    "开发区",
    "小巷",
}
ACCEPT_LEVELS = {
    "兴趣点",
    "公交地铁站点",
    "门牌号",
    "门址",
    "道路交叉路口",
    "热点商圈",
    "住宅区",
    "单元号",
    "村庄",
}
LEVEL_RANK = {
    "门牌号": 100,
    "门址": 95,
    "单元号": 90,
    "公交地铁站点": 80,
    "兴趣点": 75,
    "道路交叉路口": 70,
    "热点商圈": 60,
    "住宅区": 55,
    "村庄": 50,
}
IDENTITY_SUFFIXES = ("地铁站", "站", "广场")


@dataclass(frozen=True)
class GeoCandidate:
    location: tuple[float, float]
    level: str
    adcode: str
    joined_text: str
    identity: str
    city: str


@dataclass(frozen=True)
class ResolvedPlace:
    location: tuple[float, float]
    city: str


def resolve_location(address: str, city: str, timeout: float) -> ResolvedPlace:
    accepted, coarse = _select_candidates(fetch_geocode(address, city, timeout), address, city)
    if not accepted:
        retry_city = _city_hint_from_address(address)
        if retry_city != normalize_city(city):
            accepted, coarse = _select_candidates(
                fetch_geocode(address, retry_city, timeout),
                address,
                retry_city or city,
            )
    if not accepted:
        logger.info("geocode unmatched coarse=%s address_len=%s", coarse, len(address))
        message = COARSE_MESSAGE if coarse else UNMATCHED_MESSAGE
        raise AppError(422, "LOCATION_AMBIGUOUS", message, STAGE)
    if len(accepted) == 1:
        item = accepted[0]
        return ResolvedPlace(location=item.location, city=item.city)
    picked = _pick_same_place(accepted)
    return ResolvedPlace(location=picked.location, city=picked.city)


def _select_candidates(body: dict, address: str, city: str) -> tuple[list[GeoCandidate], int]:
    raw_items = body.get("geocodes")
    if not isinstance(raw_items, list) or not raw_items:
        return [], 0

    specific: list[GeoCandidate] = []
    coarse = 0
    for raw in raw_items:
        parsed = _parse_candidate(raw, address, city)
        if parsed is None:
            if isinstance(raw, dict) and _is_coarse_level(raw):
                coarse += 1
            continue
        specific.append(parsed)

    in_request_city = [item for item in specific if _cities_match(city, item.city, address)]
    return (in_request_city or specific), coarse


def _city_hint_from_address(address: str) -> str:
    text = address.strip()
    for name in ("北京", "上海", "天津", "重庆", "杭州"):
        if text.startswith(name) or text.startswith(f"{name}市"):
            return name
    return ""


def _candidate_city(raw: dict) -> str | None:
    return amap_text(raw.get("city")) or amap_text(raw.get("province"))


def _is_coarse_level(raw: dict) -> bool:
    level = amap_text(raw.get("level")) or "未知"
    return level in {"国家", "省", "市", "区县"}


def _cities_match(query_city: str, candidate_city: str, address: str) -> bool:
    query = normalize_city(query_city)
    candidate = normalize_city(candidate_city)
    if query == candidate:
        return True
    return candidate in address or f"{candidate}市" in address


def _parse_candidate(raw: object, address: str, city: str) -> GeoCandidate | None:
    if not isinstance(raw, dict):
        return None
    location = parse_location(raw.get("location"))
    if location is None:
        return None

    candidate_city = _candidate_city(raw)
    if candidate_city is None:
        return None

    level = amap_text(raw.get("level")) or "未知"
    if level in REJECT_LEVELS or level not in ACCEPT_LEVELS:
        return None

    joined = _joined_address(raw)
    extra_prefixes = [
        part
        for part in (amap_text(raw.get("province")), amap_text(raw.get("district")))
        if part
    ]
    if not _text_matches(address, city, joined, extra_prefixes):
        return None

    return GeoCandidate(
        location=location,
        level=level,
        adcode=amap_text(raw.get("adcode")) or "",
        joined_text=joined,
        identity=_identity_key(raw, joined),
        city=normalize_city(candidate_city),
    )


def _joined_address(raw: dict) -> str:
    parts = [
        amap_text(raw.get("formatted_address")),
        amap_text(raw.get("province")),
        amap_text(raw.get("city")),
        amap_text(raw.get("district")),
        amap_text(raw.get("street")),
        amap_text(raw.get("number")),
        amap_text(raw.get("neighborhood")),
        amap_text(raw.get("building")),
    ]
    return "".join(part for part in parts if part)


def _fold_place_text(text: str) -> str:
    return "".join(PAREN_RE.sub("", text).split())


def _core_variants(address: str, city: str, extra_prefixes: list[str]) -> list[str]:
    core = _strip_admin_prefix(address, city, extra_prefixes)
    folded = _fold_place_text(core)
    variants = [core, folded]
    remaining = folded
    for suffix in IDENTITY_SUFFIXES:
        if remaining.endswith(suffix) and len(remaining) > len(suffix):
            remaining = remaining[: -len(suffix)]
            variants.append(remaining)
    seen: list[str] = []
    for item in variants:
        if len(item) >= 2 and item not in seen:
            seen.append(item)
    return seen


def _text_matches(
    address: str,
    city: str,
    joined: str,
    extra_prefixes: list[str],
) -> bool:
    joined_folded = _fold_place_text(joined)
    for core in _core_variants(address, city, extra_prefixes):
        if core in joined or core in joined_folded:
            return True
    joined_core = _fold_place_text(_strip_admin_prefix(joined, city, extra_prefixes))
    folded_address = _fold_place_text(address)
    return len(joined_core) >= 2 and (
        joined_core in address or joined_core in folded_address
    )


def _strip_admin_prefix(text: str, city: str, extra_prefixes: list[str]) -> str:
    remaining = text.strip()
    city_name = normalize_city(city)
    prefixes = [
        f"{city_name}市",
        city_name,
        city.strip(),
        *extra_prefixes,
        "中国",
    ]
    changed = True
    while changed and remaining:
        changed = False
        for prefix in prefixes:
            if prefix and remaining.startswith(prefix):
                remaining = remaining[len(prefix) :].lstrip()
                changed = True
                break
    return remaining


def _identity_key(raw: dict, joined: str) -> str:
    name = (
        amap_text(raw.get("formatted_address"))
        or "".join(
            part
            for part in (amap_text(raw.get("street")), amap_text(raw.get("number")))
            if part
        )
        or joined
    )
    compact = _fold_place_text(name)
    for prefix in (
        amap_text(raw.get("province")),
        amap_text(raw.get("city")),
        amap_text(raw.get("district")),
    ):
        if prefix:
            compact = compact.replace(prefix, "")
    changed = True
    while changed and compact:
        changed = False
        for suffix in IDENTITY_SUFFIXES:
            if compact.endswith(suffix) and len(compact) > len(suffix):
                compact = compact[: -len(suffix)]
                changed = True
    return compact


def _pick_same_place(candidates: list[GeoCandidate]) -> GeoCandidate:
    identities = {item.identity for item in candidates}
    adcodes = {item.adcode for item in candidates}
    same_identity = len(identities) == 1 and "" not in identities
    same_adcode = len(adcodes) == 1 and "" not in adcodes
    close_together = all(
        haversine_m(*left.location, *right.location) <= SAME_PLACE_MAX_M
        for index, left in enumerate(candidates)
        for right in candidates[index + 1 :]
    )
    if not (same_identity and same_adcode and close_together):
        raise AppError(422, "LOCATION_AMBIGUOUS", AMBIGUOUS_MESSAGE, STAGE)

    return sorted(
        candidates,
        key=lambda item: (
            -LEVEL_RANK.get(item.level, 0),
            f"{item.location[0]:.6f},{item.location[1]:.6f}",
        ),
    )[0]
