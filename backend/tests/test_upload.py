from pathlib import Path

from fastapi.testclient import TestClient

from errors import AppError
from main import app
from services.audio_probe import AudioProbeResult

client = TestClient(app)

VALID_PROBE = AudioProbeResult(
    container="webm",
    codec="opus",
    duration_seconds=3.2,
    extension="webm",
)


def _patch_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("services.audio_store.get_audio_dir", lambda: tmp_path)
    monkeypatch.setattr("api.upload.get_audio_dir", lambda: tmp_path)


def test_upload_success(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    monkeypatch.setattr("api.upload.probe_audio", lambda path: VALID_PROBE)

    response = client.post(
        "/upload",
        files={"file": ("meetup-recording.webm", b"fake-webm-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    audio_id = body["data"]["audio_id"]
    assert audio_id.startswith("rec_")
    assert (tmp_path / f"{audio_id}.webm").is_file()
    assert (tmp_path / f"{audio_id}.json").is_file()
    assert "storage/" not in audio_id
    assert "/" not in audio_id


def test_upload_rejects_oversize(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)

    def should_not_probe(_path):
        raise AssertionError("oversize files must not be probed")

    monkeypatch.setattr("api.upload.probe_audio", should_not_probe)
    too_big = b"x" * (5 * 1024 * 1024 + 1)

    response = client.post(
        "/upload",
        files={"file": ("big.webm", too_big, "audio/webm")},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "FILE_TOO_LARGE"
    assert body["error"]["stage"] == "upload"
    assert body["error"]["message"]


def test_upload_rejects_unsupported_format(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "api.upload.probe_audio",
        lambda path: (_ for _ in ()).throw(
            AppError(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "当前录音格式不受支持，请更换浏览器后重试。",
                "upload",
            )
        ),
    )

    response = client.post(
        "/upload",
        files={"file": ("clip.wav", b"not-a-real-wav", "audio/wav")},
    )

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert body["error"]["stage"] == "upload"


def test_upload_rejects_invalid_duration(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "api.upload.probe_audio",
        lambda path: AudioProbeResult(
            container="webm",
            codec="opus",
            duration_seconds=0.4,
            extension="webm",
        ),
    )

    response = client.post(
        "/upload",
        files={"file": ("short.webm", b"fake-webm-bytes", "audio/webm")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "DURATION_INVALID"
    assert body["error"]["stage"] == "upload"


def test_upload_missing_file_uses_unified_error():
    response = client.post("/upload")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "upload"
