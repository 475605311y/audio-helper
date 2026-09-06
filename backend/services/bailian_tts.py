from __future__ import annotations

import logging

import httpx

from config import settings
from services.audio_format import detect_audio_format
from services.tts_store import save_tts

logger = logging.getLogger(__name__)

STAGE = "finalize"
TTS_TIMEOUT_SECONDS = 10.0
DOWNLOAD_TIMEOUT_SECONDS = 4.0
TTS_WARNING = "推荐语已生成，但语音合成失败，请阅读文字结果。"


class TtsDegraded(Exception):
    def __init__(self, warning: str = TTS_WARNING):
        self.warning = warning
        super().__init__(warning)


def synthesize_and_store(text: str) -> str:
    url = _request_audio_url(text)
    data, content_type = _download_audio(url)
    detected = detect_audio_format(data, content_type)
    if detected is None:
        logger.info("tts format undetectable content_type=%s size=%s", content_type, len(data))
        raise TtsDegraded()
    extension, mime = detected
    return save_tts(data, mime, extension)


def _request_audio_url(text: str) -> str:
    if not settings.bailian_api_key:
        raise TtsDegraded()

    payload = {
        "model": settings.bailian_tts_model,
        "input": {
            "text": text,
            "voice": settings.bailian_tts_voice,
            "language_type": settings.bailian_tts_language,
        },
    }

    try:
        response = httpx.post(
            settings.bailian_tts_url,
            headers={
                "Authorization": f"Bearer {settings.bailian_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TTS_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        logger.info("tts timeout")
        raise TtsDegraded() from exc
    except httpx.HTTPError as exc:
        logger.info("tts error type=%s", type(exc).__name__)
        raise TtsDegraded() from exc

    if response.status_code >= 400:
        logger.info("tts http_status=%s", response.status_code)
        raise TtsDegraded()

    try:
        body = response.json()
        url = body["output"]["audio"]["url"]
    except (KeyError, TypeError, ValueError) as exc:
        logger.info("tts payload invalid")
        raise TtsDegraded() from exc

    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise TtsDegraded()
    return url


def _download_audio(url: str) -> tuple[bytes, str | None]:
    try:
        response = httpx.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True)
    except httpx.TimeoutException as exc:
        logger.info("tts download timeout")
        raise TtsDegraded() from exc
    except httpx.HTTPError as exc:
        logger.info("tts download error type=%s", type(exc).__name__)
        raise TtsDegraded() from exc

    if response.status_code >= 400 or not response.content:
        logger.info("tts download status=%s", response.status_code)
        raise TtsDegraded()
    return response.content, response.headers.get("content-type")
