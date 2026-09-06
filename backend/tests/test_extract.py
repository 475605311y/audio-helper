import json

from fastapi.testclient import TestClient

from errors import AppError
from main import app
from services.extract import evaluate_extract, validate_model_output
from schemas import ExtractModelOutput

client = TestClient(app)

COMPLETE_MODEL = {
    "city_a": "杭州",
    "address_a": "杭州东站",
    "city_b": "杭州",
    "address_b": "西湖龙翔桥地铁站",
    "category": "咖啡店",
    "party_count": 2,
    "incomplete_reason": None,
}


def test_extract_success_returns_five_fields(monkeypatch):
    monkeypatch.setattr(
        "api.extract.call_extract_model",
        lambda text, city: json.dumps(COMPLETE_MODEL),
    )

    response = client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。",
            "city": "杭州",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["data"].keys()) == {
        "city_a",
        "address_a",
        "city_b",
        "address_b",
        "category",
    }
    assert "party_count" not in body["data"]
    assert body["data"]["address_a"] == "杭州东站"


def test_extract_party_count_invalid(monkeypatch):
    payload = {
        **COMPLETE_MODEL,
        "party_count": 3,
        "incomplete_reason": "party_count",
    }
    monkeypatch.setattr(
        "api.extract.call_extract_model",
        lambda text, city: json.dumps(payload),
    )

    response = client.post(
        "/extract",
        json={
            "text": "我、小王和小李，我在杭州东站，他们一个在龙翔桥一个在湖滨。",
            "city": "杭州",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PARTY_COUNT_INVALID"


def test_extract_missing_address(monkeypatch):
    payload = {
        **COMPLETE_MODEL,
        "address_a": None,
        "address_b": None,
        "incomplete_reason": "missing_address",
    }
    monkeypatch.setattr(
        "api.extract.call_extract_model",
        lambda text, city: json.dumps(payload),
    )

    response = client.post(
        "/extract",
        json={"text": "我和朋友想找个咖啡店碰面。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INCOMPLETE_INFO"


def test_extract_vague_home_address():
    model = validate_model_output(
        {
            **COMPLETE_MODEL,
            "address_a": "我家",
            "address_b": "杭州东站",
            "incomplete_reason": "missing_address",
        }
    )
    try:
        evaluate_extract(model, "杭州")
        raise AssertionError("vague address should fail")
    except AppError as exc:
        assert exc.code == "INCOMPLETE_INFO"


def test_extract_cross_city():
    model = ExtractModelOutput.model_validate(
        {
            **COMPLETE_MODEL,
            "city_a": "杭州",
            "city_b": "上海",
            "incomplete_reason": "cross_city",
        }
    )
    try:
        evaluate_extract(model, "杭州")
        raise AssertionError("cross city should fail")
    except AppError as exc:
        assert exc.code == "CROSS_CITY"


def test_extract_model_missing_field_is_502(monkeypatch):
    monkeypatch.setattr(
        "api.extract.call_extract_model",
        lambda text, city: json.dumps({"city_a": "杭州"}),
    )
    response = client.post(
        "/extract",
        json={"text": "我在杭州东站。", "city": "杭州"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MODEL_OUTPUT_INVALID"


def test_extract_invalid_json_is_502(monkeypatch):
    monkeypatch.setattr(
        "api.extract.call_extract_model",
        lambda text, city: "不是JSON",
    )
    response = client.post(
        "/extract",
        json={"text": "我在杭州东站。", "city": "杭州"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MODEL_OUTPUT_INVALID"


def test_extract_missing_request_field():
    response = client.post("/extract", json={"text": "我在杭州东站"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "extract"
