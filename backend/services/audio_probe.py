from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from errors import AppError

STAGE = "upload"
FFPROBE_TIMEOUT_SECONDS = 5
ALLOWED_CODECS = {"opus", "vorbis"}


@dataclass(frozen=True)
class AudioProbeResult:
    container: str
    codec: str
    duration_seconds: float
    extension: str


def probe_audio(path: Path) -> AudioProbeResult:
    if shutil.which("ffprobe") is None:
        raise AppError(
            500,
            "INTERNAL_ERROR",
            "服务器缺少音频校验工具，无法处理录音。",
            STAGE,
        )

    payload = _run_ffprobe(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            str(path),
        ]
    )
    audio_stream = _first_audio_stream(payload.get("streams") or [])
    if audio_stream is None:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "当前录音格式不受支持，请更换浏览器后重试。",
            STAGE,
        )

    container = _normalize_container((payload.get("format") or {}).get("format_name", ""))
    codec = str(audio_stream.get("codec_name") or "").strip().lower()
    if container is None or codec not in ALLOWED_CODECS:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "当前录音格式不受支持，请更换浏览器后重试。",
            STAGE,
        )

    duration = _duration_from_format_or_stream(payload.get("format") or {}, audio_stream)
    if duration is None:
        duration = _duration_from_packets(path)
    if duration is None:
        raise AppError(
            422,
            "DURATION_INVALID",
            "无法确认录音时长，请重新录制。",
            STAGE,
        )

    return AudioProbeResult(
        container=container,
        codec=codec,
        duration_seconds=duration,
        extension=container,
    )


def _run_ffprobe(command: list[str]) -> dict:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            500,
            "INTERNAL_ERROR",
            "音频校验超时，请稍后重试。",
            STAGE,
        ) from exc
    except OSError as exc:
        raise AppError(
            500,
            "INTERNAL_ERROR",
            "服务器缺少音频校验工具，无法处理录音。",
            STAGE,
        ) from exc

    if completed.returncode != 0:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "当前录音格式不受支持，请更换浏览器后重试。",
            STAGE,
        )

    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "当前录音格式不受支持，请更换浏览器后重试。",
            STAGE,
        ) from exc


def _first_audio_stream(streams: list[dict]) -> dict | None:
    for stream in streams:
        if stream.get("codec_type") == "audio":
            return stream
    return None


def _normalize_container(format_name: str) -> str | None:
    names = {item.strip().lower() for item in format_name.split(",") if item.strip()}
    if "webm" in names:
        return "webm"
    if "ogg" in names:
        return "ogg"
    return None


def _parse_seconds(value: object) -> float | None:
    if value in (None, "", "N/A", "n/a"):
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return seconds


def _duration_from_format_or_stream(format_info: dict, audio_stream: dict) -> float | None:
    return _parse_seconds(format_info.get("duration")) or _parse_seconds(
        audio_stream.get("duration")
    )


def _duration_from_packets(path: Path) -> float | None:
    try:
        payload = _run_ffprobe(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "packet=pts_time,duration_time",
                "-print_format",
                "json",
                str(path),
            ]
        )
    except AppError as exc:
        if exc.code == "UNSUPPORTED_MEDIA_TYPE":
            return None
        raise
    packets = payload.get("packets") or []
    end_times: list[float] = []
    for packet in packets:
        pts = _parse_seconds(packet.get("pts_time"))
        if pts is None:
            continue
        packet_duration = _parse_seconds(packet.get("duration_time")) or 0.0
        end_times.append(pts + packet_duration)
    if not end_times:
        return None
    return max(end_times)
