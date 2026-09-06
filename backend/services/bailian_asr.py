from __future__ import annotations

import base64
import logging

import httpx

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

STAGE = "asr"
ASR_TIMEOUT_SECONDS = 18.0
MAX_ENCODED_BYTES = 10 * 1024 * 1024
MIME_BY_EXTENSION = {
    "webm": "audio/webm",
    "ogg": "audio/ogg",
}


def mime_for_extension(extension: str) -> str:
    return MIME_BY_EXTENSION.get(extension, "audio/webm")


def encode_audio_data_uri(data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    data_uri = f"data:{mime_type};base64,{encoded}"
    if len(data_uri.encode("utf-8")) > MAX_ENCODED_BYTES:
        raise AppError(
            413,
            "FILE_TOO_LARGE",
            "录音编码后超过识别服务限制，请缩短录音后重试。",
            STAGE,
        )
    return data_uri


def recognize_audio(data: bytes, mime_type: str) -> str:
    if not settings.bailian_api_key:
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别服务暂不可用，请稍后重试。",
            STAGE,
        )

    data_uri = encode_audio_data_uri(data, mime_type)
    payload = {
        "model": settings.bailian_asr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": data_uri},
                    }
                ],
            }
        ],
        "stream": False,
        "asr_options": {
            "language": "zh",
            "enable_itn": True,
        },
    }

    try:
        response = httpx.post(
            settings.bailian_asr_url,
            headers={
                "Authorization": f"Bearer {settings.bailian_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=ASR_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        logger.info("asr timeout url=%s", settings.bailian_asr_url)
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "语音识别超时，请稍后重试。",
            STAGE,
        ) from exc
    except httpx.HTTPError as exc:
        logger.info("asr upstream error type=%s", type(exc).__name__)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别服务异常，请稍后重试。",
            STAGE,
        ) from exc

    if response.status_code >= 500:
        logger.info("asr upstream status=%s", response.status_code)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别服务异常，请稍后重试。",
            STAGE,
        )
    if response.status_code >= 400:
        logger.info("asr upstream status=%s", response.status_code)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别服务异常，请稍后重试。",
            STAGE,
        )

    try:
        body = response.json()
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.info("asr upstream payload invalid")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别服务异常，请稍后重试。",
            STAGE,
        ) from exc

    if text is None or not str(text).strip():
        raise AppError(
            422,
            "EMPTY_TRANSCRIPT",
            "没有识别出有效文字，请重新说一遍。",
            STAGE,
        )
    return str(text).strip()
