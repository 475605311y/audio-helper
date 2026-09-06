from __future__ import annotations

from pydantic import ValidationError

from errors import AppError
from schemas import ExtractData, ExtractModelOutput

STAGE = "extract"
VAGUE_ADDRESSES = {
    "家",
    "我家",
    "你家",
    "他家",
    "公司",
    "单位",
    "办公室",
    "学校",
}
CATEGORY_ALIASES = {
    "喝咖啡": "咖啡店",
    "咖啡": "咖啡店",
    "咖啡馆": "咖啡店",
}


def validate_model_output(payload: dict) -> ExtractModelOutput:
    try:
        return ExtractModelOutput.model_validate(payload)
    except ValidationError as exc:
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地址解析服务返回异常，请稍后重试。",
            STAGE,
        ) from exc


def evaluate_extract(model: ExtractModelOutput, page_city: str) -> ExtractData:
    if model.party_count != 2:
        raise AppError(
            422,
            "PARTY_COUNT_INVALID",
            "第一版只支持两个人碰面，请重新说你们两个人的位置。",
            STAGE,
        )

    city_a = _or_page_city(model.city_a, page_city)
    city_b = _or_page_city(model.city_b, page_city)
    address_a = _clean_address(model.address_a)
    address_b = _clean_address(model.address_b)

    if address_a is None or address_b is None or city_a is None or city_b is None:
        raise AppError(
            422,
            "INCOMPLETE_INFO",
            "没有听清两个具体地点，请说出各自所在的车站或地标。",
            STAGE,
        )

    if _normalize_city(city_a) != _normalize_city(city_b):
        raise AppError(
            422,
            "CROSS_CITY",
            "第一版只支持同一座城市内的两个人，请重新表达。",
            STAGE,
        )

    return ExtractData(
        city_a=city_a,
        address_a=address_a,
        city_b=city_b,
        address_b=address_b,
        category=_normalize_category(model.category),
    )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _or_page_city(value: str | None, page_city: str) -> str | None:
    return _clean_text(value) or _clean_text(page_city)


def _clean_address(value: str | None) -> str | None:
    address = _clean_text(value)
    if address is None or address in VAGUE_ADDRESSES:
        return None
    return address


def _normalize_city(value: str) -> str:
    text = value.strip()
    if text.endswith("市") and len(text) > 1:
        text = text[:-1]
    return text


def _normalize_category(value: str | None) -> str:
    category = _clean_text(value)
    if category is None:
        return "咖啡店"
    return CATEGORY_ALIASES.get(category, category)
