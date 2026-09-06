from __future__ import annotations

import logging
from pathlib import Path

import httpx

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

STAGE = "finalize"
REPLY_TIMEOUT_SECONDS = 10.0
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "finalize.txt"
MAX_REPLY_CHARS = 200


def load_finalize_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def generate_reply(name: str, address: str, distance_m: float | None) -> str:
    if not settings.deepseek_api_key:
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "推荐语服务暂不可用，请稍后重试。",
            STAGE,
        )

    distance_text = "未提供"
    if distance_m is not None:
        distance_text = f"{distance_m:g}米"

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": load_finalize_prompt()},
            {
                "role": "user",
                "content": (
                    "请根据下面这一家店写推荐语。\n"
                    f"店名：{name}\n"
                    f"地址：{address}\n"
                    f"距离中点：{distance_text}"
                ),
            },
        ],
        "thinking": {"type": "disabled"},
        "max_tokens": 220,
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
            timeout=REPLY_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        logger.info("finalize reply timeout")
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "推荐语生成超时，请稍后重试。",
            STAGE,
        ) from exc
    except httpx.HTTPError as exc:
        logger.info("finalize reply error type=%s", type(exc).__name__)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "推荐语服务异常，请稍后重试。",
            STAGE,
        ) from exc

    if response.status_code >= 400:
        logger.info("finalize reply status=%s", response.status_code)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "推荐语服务异常，请稍后重试。",
            STAGE,
        )

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        finish_reason = body["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.info("finalize reply payload invalid")
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "推荐语服务返回异常，请稍后重试。",
            STAGE,
        ) from exc

    if finish_reason == "length" or content is None or not str(content).strip():
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "推荐语服务返回异常，请稍后重试。",
            STAGE,
        )
    return validate_reply(str(content).strip(), name)


def validate_reply(text: str, name: str) -> str:
    cleaned = text.strip().strip('"').strip("“”")
    if not cleaned or len(cleaned) > MAX_REPLY_CHARS or name not in cleaned:
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "推荐语服务返回异常，请稍后重试。",
            STAGE,
        )
    return cleaned
