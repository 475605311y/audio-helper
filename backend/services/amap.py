from __future__ import annotations

import logging

import httpx

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

STAGE = "search"


def fetch_geocode(address: str, city: str, timeout: float) -> dict:
    return _get(
        settings.amap_geo_url,
        {
            "key": settings.amap_api_key,
            "address": address,
            "city": city,
            "output": "JSON",
        },
        timeout,
        kind="geocode",
    )


def fetch_around(
    location: str,
    keywords: str,
    radius: int,
    city: str,
    timeout: float,
) -> dict:
    return _get(
        settings.amap_around_url,
        {
            "key": settings.amap_api_key,
            "location": location,
            "keywords": keywords,
            "radius": radius,
            "city": city,
            "offset": 25,
            "page": 1,
            "extensions": "base",
            "output": "JSON",
        },
        timeout,
        kind="around",
    )


def _get(url: str, params: dict, timeout: float, kind: str) -> dict:
    if not settings.amap_api_key:
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点查询服务暂不可用，请稍后重试。",
            STAGE,
        )

    try:
        response = httpx.get(url, params=params, timeout=timeout)
    except httpx.TimeoutException as exc:
        logger.info("amap %s timeout", kind)
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "地点查询超时，请稍后重试。",
            STAGE,
        ) from exc
    except httpx.HTTPError as exc:
        logger.info("amap %s error type=%s", kind, type(exc).__name__)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点查询服务异常，请稍后重试。",
            STAGE,
        ) from exc

    if response.status_code >= 400:
        logger.info("amap %s http_status=%s", kind, response.status_code)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点查询服务异常，请稍后重试。",
            STAGE,
        )

    try:
        body = response.json()
    except ValueError as exc:
        logger.info("amap %s payload invalid", kind)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点查询服务异常，请稍后重试。",
            STAGE,
        ) from exc

    if not isinstance(body, dict):
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点查询服务异常，请稍后重试。",
            STAGE,
        )
    if str(body.get("status")) == "1":
        return body

    info = str(body.get("info") or "")
    if info == "ENGINE_RESPONSE_DATA_ERROR":
        logger.info("amap %s no data", kind)
        return {"status": "1", "info": info, "geocodes": [], "pois": []}

    logger.info("amap %s business_status=%s info=%s", kind, body.get("status"), info)
    raise AppError(
        502,
        "UPSTREAM_ERROR",
        "地点查询服务异常，请稍后重试。",
        STAGE,
    )
