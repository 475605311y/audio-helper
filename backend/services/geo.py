from __future__ import annotations

import math
from typing import Any

EARTH_RADIUS_M = 6_371_000
SAME_PLACE_MAX_M = 150.0


def amap_text(value: Any) -> str | None:
    if value is None or value == [] or value == {}:
        return None
    if isinstance(value, dict):
        return amap_text(value.get("name"))
    if isinstance(value, list):
        parts = [part for item in value if (part := amap_text(item))]
        return "".join(parts) or None
    text = str(value).strip()
    return text or None


def normalize_city(value: str) -> str:
    text = value.strip()
    if text.endswith("市") and len(text) > 1:
        text = text[:-1]
    return text


def parse_location(value: Any) -> tuple[float, float] | None:
    text = amap_text(value)
    if text is None or "," not in text:
        return None
    lon_text, lat_text = text.split(",", 1)
    try:
        longitude = float(lon_text)
        latitude = float(lat_text)
    except ValueError:
        return None
    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        return None
    if math.isnan(longitude) or math.isnan(latitude):
        return None
    return longitude, latitude


def parse_nonneg_number(value: Any) -> float | None:
    text = amap_text(value)
    if text is None:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number < 0 or math.isnan(number) or math.isinf(number):
        return None
    return number


def midpoint(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> tuple[float, float]:
    return ((point_a[0] + point_b[0]) / 2.0, (point_a[1] + point_b[1]) / 2.0)


def haversine_m(
    longitude_a: float,
    latitude_a: float,
    longitude_b: float,
    latitude_b: float,
) -> float:
    lon1 = math.radians(longitude_a)
    lat1 = math.radians(latitude_a)
    lon2 = math.radians(longitude_b)
    lat2 = math.radians(latitude_b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    angle = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(angle)))


def format_location(point: tuple[float, float]) -> str:
    return f"{point[0]:.6f},{point[1]:.6f}"
