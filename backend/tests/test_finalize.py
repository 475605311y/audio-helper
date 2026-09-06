from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from errors import AppError
from main import app
from services.bailian_tts import TtsDegraded
from services.search_store import save_search
from services.tts_store import save_tts

client = TestClient(app)

SHOP = {
    "name": "某咖啡店湖滨店",
    "address": "杭州市西湖区延安路xxx号",
    "distance_to_midpoint_m": 420,
}
REPLY = "为你们选了距离中点较近的某咖啡店湖滨店，地址是杭州市西湖区延安路xxx号，可以先在店里会合。"


def _tiny_wav() -> bytes:
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 20


def _patch_dirs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("services.search_store.get_search_dir", lambda: tmp_path)
    monkeypatch.setattr("services.tts_store.get_tts_dir", lambda: tmp_path)


def _write_search(tmp_path: Path, pois: list | None = None, search_id: str = "srch_test-1") -> str:
    save_search(
        {
            "search_id": search_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
            "midpoint": {"longitude": 120.1, "latitude": 30.2},
            "radius_m": 2000,
            "pois": pois if pois is not None else [SHOP],
        }
    )
    return search_id


def test_finalize_success_returns_audio_url(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    search_id = _write_search(tmp_path)
    monkeypatch.setattr("services.finalize.generate_reply", lambda name, address, distance: REPLY)
    monkeypatch.setattr(
        "services.finalize.synthesize_and_store",
        lambda text: "tts_5a6b7c8d-9e0f-41a2-b3c4-d5e6f7081920",
    )

    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reply_text"] == REPLY
    assert data["audio_url"] == "http://localhost:8003/audio/tts_5a6b7c8d-9e0f-41a2-b3c4-d5e6f7081920"
    assert data["warning"] is None
    assert "某咖啡店湖滨店" in data["reply_text"]


def test_finalize_tts_failure_keeps_reply_text(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    search_id = _write_search(tmp_path)
    monkeypatch.setattr("services.finalize.generate_reply", lambda name, address, distance: REPLY)
    monkeypatch.setattr(
        "services.finalize.synthesize_and_store",
        lambda text: (_ for _ in ()).throw(TtsDegraded()),
    )

    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reply_text"] == REPLY
    assert data["audio_url"] is None
    assert data["warning"] == "推荐语已生成，但语音合成失败，请阅读文字结果。"


def test_finalize_reply_failure_is_502(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    search_id = _write_search(tmp_path)
    monkeypatch.setattr(
        "services.finalize.generate_reply",
        lambda name, address, distance: (_ for _ in ()).throw(
            AppError(502, "UPSTREAM_ERROR", "推荐语服务异常，请稍后重试。", "finalize")
        ),
    )

    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_ERROR"
    assert body["error"]["stage"] == "finalize"
    assert "data" not in body


def test_finalize_reply_timeout_is_504(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    search_id = _write_search(tmp_path)
    monkeypatch.setattr(
        "services.finalize.generate_reply",
        lambda name, address, distance: (_ for _ in ()).throw(
            AppError(504, "UPSTREAM_TIMEOUT", "推荐语生成超时，请稍后重试。", "finalize")
        ),
    )

    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_finalize_missing_search_id():
    response = client.post("/finalize", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "finalize"


def test_finalize_unknown_search_id(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    response = client.post("/finalize", json={"search_id": "srch_missing"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SEARCH_NOT_FOUND"
    assert response.json()["error"]["stage"] == "finalize"


def test_finalize_empty_pois(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    search_id = _write_search(tmp_path, pois=[])
    response = client.post("/finalize", json={"search_id": search_id})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_POI"


def test_audio_returns_real_wav_bytes(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    audio_id = save_tts(_tiny_wav(), "audio/wav", "wav")

    response = client.get(f"/audio/{audio_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content.startswith(b"RIFF")
    assert response.content[8:12] == b"WAVE"


def test_audio_unknown_id_is_json_error(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    response = client.get("/audio/tts_missing")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "AUDIO_NOT_FOUND"
    assert body["error"]["stage"] == "audio"


def test_audio_does_not_serve_recording_ids(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    response = client.get("/audio/rec_not-allowed")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_tts_uses_magic_bytes_not_url_suffix(monkeypatch, tmp_path):
    _patch_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "services.bailian_tts._request_audio_url",
        lambda text: "https://example.invalid/file.mp3",
    )
    monkeypatch.setattr(
        "services.bailian_tts._download_audio",
        lambda url: (_tiny_wav(), "audio/mpeg"),
    )

    from services.bailian_tts import synthesize_and_store
    from services.tts_store import load_tts

    audio_id = synthesize_and_store(REPLY)
    data, content_type = load_tts(audio_id)
    assert content_type == "audio/wav"
    assert data.startswith(b"RIFF")
    assert (tmp_path / f"{audio_id}.wav").is_file()
    assert not (tmp_path / f"{audio_id}.mp3").is_file()
