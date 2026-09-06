from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

STAGE = "extract"
DEEPSEEK_TIMEOUT_SECONDS = 12.0
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract.txt"


def load_extract_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def call_extract_model(text: str, page_city: str) -> str:
    if not settings.deepseek_api_key:
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地址解析服务暂不可用，请稍后重试。",
            STAGE,
        )

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": load_extract_prompt()},
            {
                "role": "user",
                "content": f"请把下面的口述抽取为 json。\n页面选定城市：{page_city}\n用户口述：{text}",
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "max_tokens": 500,
        "stream": False,
    }

    try:
        response = httpx.post(
            settings.deepseek_url,
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=DEEPSEEK_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        logger.info("extract timeout")
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "地址解析超时，请稍后重试。",
            STAGE,
        ) from exc
    except httpx.HTTPError as exc:
        logger.info("extract upstream error type=%s", type(exc).__name__)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地址解析服务异常，请稍后重试。",
            STAGE,
        ) from exc

    if response.status_code >= 400:
        logger.info("extract upstream status=%s", response.status_code)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地址解析服务异常，请稍后重试。",
            STAGE,
        )

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        finish_reason = body["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.info("extract upstream payload invalid")
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地址解析服务返回异常，请稍后重试。",
            STAGE,
        ) from exc

    if finish_reason == "length" or content is None or not str(content).strip():
        logger.info("extract model output empty or truncated")
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地址解析服务返回异常，请稍后重试。",
            STAGE,
        )
    return str(content).strip()


def parse_model_json(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.info("extract model json invalid")
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地址解析服务返回异常，请稍后重试。",
            STAGE,
        ) from exc
    if not isinstance(parsed, dict):
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地址解析服务返回异常，请稍后重试。",
            STAGE,
        )
    return parsed
