from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from errors import AppError

SEARCH_TTL = timedelta(hours=24)
ROOT_DIR = Path(__file__).resolve().parent.parent
SEARCH_DIR = ROOT_DIR / "storage" / "search"


def get_search_dir() -> Path:
    return SEARCH_DIR


def new_search_id() -> str:
    return f"srch_{uuid.uuid4()}"


def _is_safe_search_id(search_id: str) -> bool:
    return search_id.startswith("srch_") and "/" not in search_id and ".." not in search_id


def save_search(payload: dict) -> str:
    search_dir = get_search_dir()
    search_dir.mkdir(parents=True, exist_ok=True)
    search_id = str(payload["search_id"])
    if not _is_safe_search_id(search_id):
        raise AppError(500, "INTERNAL_ERROR", "查询结果保存失败，请稍后重试。", "search")
    path = search_dir / f"{search_id}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return search_id


def load_search(search_id: str, stage: str = "search") -> dict:
    if not _is_safe_search_id(search_id):
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期，请重新搜索。", stage)

    path = get_search_dir() / f"{search_id}.json"
    if not path.is_file():
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期，请重新搜索。", stage)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(
            404,
            "SEARCH_NOT_FOUND",
            "查询结果不存在或已过期，请重新搜索。",
            stage,
        ) from exc

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > SEARCH_TTL:
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期，请重新搜索。", stage)
    return payload
