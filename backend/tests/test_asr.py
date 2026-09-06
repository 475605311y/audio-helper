import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from errors import AppError
from main import app
from services.audio_store import write_audio_metadata
from services.audio_probe import AudioProbeResult

client = TestClient(app)


def _write_recording(tmp_path: Path, audio_id: str, created_at: datetime | None = None) -> None:
    audio_path = tmp_path / f"{audio_id}.webm"
    audio_path.write_bytes(b"fake-webm-bytes")
    write_audio_metadata(
        audio_id,
        audio_path,
        AudioProbeResult(
            container="webm",
            codec="opus",
            duration_seconds=3.2,
            extension="webm",
        ),
    )
    if created_at is not None:
        meta_path = tmp_path / f"{audio_id}.json"
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        metadata["created_at"] = created_at.isoformat()
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")


def _patch_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("services.audio_store.get_audio_dir", lambda: tmp_path)


def test_asr_success_uses_mocked_transcript(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    audio_id = "rec_11111111-1111-1111-1111-111111111111"
    _write_recording(tmp_path, audio_id)
    monkeypatch.setattr(
        "api.asr.recognize_audio",
        lambda data, mime_type: "我在杭州东站，朋友在西湖龙翔桥地铁站。",
    )

    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    assert body["data"]["text"] == "我在杭州东站，朋友在西湖龙翔桥地铁站。"


def test_asr_missing_audio_id_uses_unified_error():
    response = client.post("/asr", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "asr"


def test_asr_unknown_audio_id(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    response = client.post("/asr", json={"audio_id": "rec_missing"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "AUDIO_NOT_FOUND"
    assert body["error"]["stage"] == "asr"


def test_asr_expired_audio_id(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    audio_id = "rec_22222222-2222-2222-2222-222222222222"
    _write_recording(
        tmp_path,
        audio_id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    monkeypatch.setattr(
        "api.asr.recognize_audio",
        lambda data, mime_type: (_ for _ in ()).throw(AssertionError("expired audio")),
    )

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_asr_empty_transcript(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    audio_id = "rec_33333333-3333-3333-3333-333333333333"
    _write_recording(tmp_path, audio_id)
    monkeypatch.setattr(
        "api.asr.recognize_audio",
        lambda data, mime_type: (_ for _ in ()).throw(
            AppError(
                422,
                "EMPTY_TRANSCRIPT",
                "没有识别出有效文字，请重新说一遍。",
                "asr",
            )
        ),
    )

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "EMPTY_TRANSCRIPT"
    assert body["error"]["stage"] == "asr"


def test_asr_upstream_timeout(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    audio_id = "rec_44444444-4444-4444-4444-444444444444"
    _write_recording(tmp_path, audio_id)
    monkeypatch.setattr(
        "api.asr.recognize_audio",
        lambda data, mime_type: (_ for _ in ()).throw(
            AppError(
                504,
                "UPSTREAM_TIMEOUT",
                "语音识别超时，请稍后重试。",
                "asr",
            )
        ),
    )

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_asr_upstream_error(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    audio_id = "rec_55555555-5555-5555-5555-555555555555"
    _write_recording(tmp_path, audio_id)
    monkeypatch.setattr(
        "api.asr.recognize_audio",
        lambda data, mime_type: (_ for _ in ()).throw(
            AppError(
                502,
                "UPSTREAM_ERROR",
                "语音识别服务异常，请稍后重试。",
                "asr",
            )
        ),
    )

    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
