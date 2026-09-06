from pathlib import Path

from fastapi.testclient import TestClient

from errors import AppError
from main import app
from services.geo import haversine_m, midpoint
from services.search_store import load_search

client = TestClient(app)

EAST_STATION = (120.212010, 30.290880)
LONGXIANGQIAO = (120.164200, 30.259800)
CENTER = midpoint(EAST_STATION, LONGXIANGQIAO)

NORMAL_REQUEST = {
    "city_a": "杭州",
    "address_a": "杭州东站",
    "city_b": "杭州",
    "address_b": "西湖龙翔桥地铁站",
    "category": "咖啡店",
}


def _geocode_item(
    location: tuple[float, float],
    formatted_address: str,
    level: str = "兴趣点",
    adcode: str = "330102",
    city: str = "杭州市",
    province: str = "浙江省",
    district: str = "上城区",
) -> dict:
    return {
        "formatted_address": formatted_address,
        "province": province,
        "city": city,
        "district": district,
        "street": [],
        "number": [],
        "adcode": adcode,
        "location": f"{location[0]},{location[1]}",
        "level": level,
    }


def _ok_geocode(*items: dict) -> dict:
    return {"status": "1", "info": "OK", "geocodes": list(items)}


def _ok_around(*pois: dict) -> dict:
    return {"status": "1", "info": "OK", "pois": list(pois)}


def _patch_store(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("services.search_store.get_search_dir", lambda: tmp_path)


def _patch_geocode_pair(monkeypatch, items_a: list[dict], items_b: list[dict]) -> None:
    def fake_geocode(address: str, city: str, timeout: float) -> dict:
        if "东站" in address:
            return _ok_geocode(*items_a)
        return _ok_geocode(*items_b)

    monkeypatch.setattr("services.geocode_resolve.fetch_geocode", fake_geocode)


def test_search_success_sorts_and_keeps_three(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item(EAST_STATION, "浙江省杭州市上城区杭州东站", "公交地铁站点")],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站", "公交地铁站点")],
    )

    far = (CENTER[0] + 0.02, CENTER[1])
    mid = (CENTER[0] + 0.008, CENTER[1])
    near = (CENTER[0] + 0.003, CENTER[1])
    extra = (CENTER[0] + 0.03, CENTER[1])
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "远一点的店",
                "address": "杭州市上城区远路1号",
                "location": f"{far[0]},{far[1]}",
                "distance": "1800",
            },
            {
                "name": "中间的店",
                "address": "杭州市上城区中路2号",
                "location": f"{mid[0]},{mid[1]}",
                "distance": "900",
            },
            {
                "name": "最近的店",
                "address": "杭州市上城区近路3号",
                "location": f"{near[0]},{near[1]}",
                "distance": "320",
            },
            {
                "name": "第四家不应返回",
                "address": "杭州市上城区外路4号",
                "location": f"{extra[0]},{extra[1]}",
                "distance": "2200",
            },
        ),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["search_id"].startswith("srch_")
    assert "storage/" not in data["search_id"]
    assert data["midpoint"]["longitude"] == CENTER[0]
    assert data["midpoint"]["latitude"] == CENTER[1]
    names = [item["name"] for item in data["pois"]]
    assert names == ["最近的店", "中间的店", "远一点的店"]
    assert [item["distance_to_midpoint_m"] for item in data["pois"]] == [320.0, 900.0, 1800.0]

    saved = load_search(data["search_id"])
    assert saved["created_at"]
    assert saved["radius_m"] == 2000
    assert saved["category"] == "咖啡店"


def test_search_accepts_amap_parenthetical_station_name(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item(EAST_STATION, "杭州东站", "门牌号")],
        [
            _geocode_item(
                LONGXIANGQIAO,
                "浙江省杭州市上城区杭州西湖(湖滨店)龙翔桥(地铁站)",
                "公交地铁站点",
            )
        ],
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "括号站名附近的店",
                "address": "杭州市上城区湖滨路1号",
                "location": f"{CENTER[0]},{CENTER[1]}",
                "distance": "30",
            }
        ),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    assert response.json()["data"]["pois"][0]["name"] == "括号站名附近的店"


def _beijing_station(address: str) -> dict:
    if "西站" in address:
        return _geocode_item(
            (116.322033, 39.894912),
            "北京市丰台区北京西站",
            "兴趣点",
            adcode="110106",
            city="北京市",
            province="北京市",
            district="丰台区",
        )
    return _geocode_item(
        (116.351644, 40.046873),
        "北京市海淀区西小口(地铁站)",
        "公交地铁站点",
        adcode="110108",
        city="北京市",
        province="北京市",
        district="海淀区",
    )


def test_search_beijing_stations(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "services.geocode_resolve.fetch_geocode",
        lambda address, city, timeout: _ok_geocode(_beijing_station(address)),
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "北京中点附近的店",
                "address": "北京市海淀区测试路1号",
                "location": "116.336839,39.970893",
                "distance": "40",
            }
        ),
    )

    response = client.post(
        "/search",
        json={
            "city_a": "北京",
            "address_a": "北京西站",
            "city_b": "北京",
            "address_b": "西小口地铁站",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pois"][0]["name"] == "北京中点附近的店"
    assert data["midpoint"]["longitude"] == (116.322033 + 116.351644) / 2
    assert data["midpoint"]["latitude"] == (39.894912 + 40.046873) / 2


def test_search_retries_beijing_when_hangzhou_city_returns_no_data(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    calls: list[str] = []

    def fake_geocode(address: str, city: str, timeout: float) -> dict:
        calls.append(city)
        if city == "杭州":
            return {"status": "1", "info": "ENGINE_RESPONSE_DATA_ERROR", "geocodes": []}
        return _ok_geocode(_beijing_station(address))

    monkeypatch.setattr("services.geocode_resolve.fetch_geocode", fake_geocode)
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "重查后的店",
                "address": "北京市海淀区1号",
                "location": location,
                "distance": "18",
            }
        ),
    )

    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "北京西站",
            "city_b": "杭州",
            "address_b": "西小口地铁站",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 200
    assert "杭州" in calls
    assert "" in calls or "北京" in calls


def test_search_beijing_places_when_request_city_still_hangzhou(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    captured: dict = {}

    def fake_around(location, keywords, radius, city, timeout):
        captured["city"] = city
        return _ok_around(
            {
                "name": "按定位城市搜到的店",
                "address": "北京市海淀区1号",
                "location": location,
                "distance": "15",
            }
        )

    monkeypatch.setattr(
        "services.geocode_resolve.fetch_geocode",
        lambda address, city, timeout: _ok_geocode(_beijing_station(address)),
    )
    monkeypatch.setattr("services.search.fetch_around", fake_around)

    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "北京西站",
            "city_b": "杭州",
            "address_b": "西小口地铁站",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 200
    assert captured["city"] == "北京"


def test_search_city_only_beijing_asks_for_landmark(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "services.geocode_resolve.fetch_geocode",
        lambda address, city, timeout: _ok_geocode(
            _geocode_item(
                (116.407387, 39.904179),
                "北京市",
                "省",
                adcode="110000",
                city="北京市",
                province="北京市",
                district=[],
            )
        ),
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not search")),
    )

    response = client.post(
        "/search",
        json={
            "city_a": "北京",
            "address_a": "北京",
            "city_b": "北京",
            "address_b": "西小口地铁站",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "LOCATION_AMBIGUOUS"
    assert body["error"]["message"] == "地点不够具体，请说出车站或地标。"


def test_search_midpoint_is_average_of_lng_lat(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    point_a = (120.0, 30.0)
    point_b = (120.2, 30.4)
    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item(point_a, "浙江省杭州市上城区杭州东站")],
        [_geocode_item(point_b, "浙江省杭州市西湖区龙翔桥地铁站")],
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "中点附近咖啡",
                "address": "杭州市上城区测试路1号",
                "location": "120.100000,30.200000",
                "distance": "10",
            }
        ),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    mid = response.json()["data"]["midpoint"]
    assert mid["longitude"] == 120.1
    assert mid["latitude"] == 30.2


def test_search_around_uses_longitude_then_latitude(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    captured: dict = {}

    def fake_around(location, keywords, radius, city, timeout):
        captured["location"] = location
        captured["keywords"] = keywords
        captured["radius"] = radius
        return _ok_around(
            {
                "name": "一家店",
                "address": "杭州市上城区1号",
                "location": location,
                "distance": "12",
            }
        )

    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item((120.0, 30.0), "浙江省杭州市上城区杭州东站")],
        [_geocode_item((120.2, 30.4), "浙江省杭州市西湖区龙翔桥地铁站")],
    )
    monkeypatch.setattr("services.search.fetch_around", fake_around)

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    lng_text, lat_text = captured["location"].split(",")
    assert float(lng_text) == 120.1
    assert float(lat_text) == 30.2
    assert captured["keywords"] == "咖啡店"
    assert captured["radius"] == 2000


def test_search_ambiguous_when_different_places_within_300m(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    east = (120.213050, 30.290880)
    west = (120.210970, 30.290880)
    assert 150 < haversine_m(*east, *west) < 300
    _patch_geocode_pair(
        monkeypatch,
        [
            _geocode_item(east, "浙江省杭州市上城区杭州东站东广场"),
            _geocode_item(west, "浙江省杭州市上城区杭州东站西广场"),
        ],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站", "公交地铁站点")],
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not search")),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "LOCATION_AMBIGUOUS"
    assert body["error"]["stage"] == "search"
    assert "具体" in body["error"]["message"]


def test_search_ambiguous_uses_all_candidates_not_first_two(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    first = (120.212010, 30.290880)
    second = (120.212200, 30.290880)
    third = (120.220000, 30.300000)
    _patch_geocode_pair(
        monkeypatch,
        [
            _geocode_item(first, "浙江省杭州市上城区杭州东站"),
            _geocode_item(second, "浙江省杭州市上城区杭州东站地铁站", "公交地铁站点"),
            _geocode_item(third, "浙江省杭州市上城区杭州东站汽车客运站"),
        ],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站", "公交地铁站点")],
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not search")),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LOCATION_AMBIGUOUS"


def test_search_merges_same_identity_within_150m(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    first = (120.212010, 30.290880)
    second = (120.212850, 30.290880)
    assert haversine_m(*first, *second) <= 150
    _patch_geocode_pair(
        monkeypatch,
        [
            _geocode_item(first, "浙江省杭州市上城区杭州东站"),
            _geocode_item(second, "浙江省杭州市上城区杭州东站地铁站", "公交地铁站点"),
        ],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站", "公交地铁站点")],
    )
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "可合并后的店",
                "address": "杭州市上城区1号",
                "location": f"{CENTER[0]},{CENTER[1]}",
                "distance": "20",
            }
        ),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    assert response.json()["data"]["pois"][0]["name"] == "可合并后的店"


def test_search_no_poi_after_2000_and_5000(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item(EAST_STATION, "浙江省杭州市上城区杭州东站")],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站")],
    )
    radii: list[int] = []

    def fake_around(location, keywords, radius, city, timeout):
        radii.append(radius)
        return _ok_around()

    monkeypatch.setattr("services.search.fetch_around", fake_around)

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "NO_POI"
    assert body["error"]["stage"] == "search"
    assert radii == [2000, 5000]


def test_search_expands_to_5000_when_first_radius_empty(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item(EAST_STATION, "浙江省杭州市上城区杭州东站")],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站")],
    )

    def fake_around(location, keywords, radius, city, timeout):
        if radius == 2000:
            return _ok_around()
        return _ok_around(
            {
                "name": "扩大后找到的店",
                "address": "杭州市西湖区扩大路1号",
                "location": f"{CENTER[0]},{CENTER[1]}",
                "distance": "4100",
            }
        )

    monkeypatch.setattr("services.search.fetch_around", fake_around)

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pois"][0]["name"] == "扩大后找到的店"
    assert load_search(data["search_id"])["radius_m"] == 5000


def test_search_missing_distance_is_computed_not_zero(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)
    _patch_geocode_pair(
        monkeypatch,
        [_geocode_item(EAST_STATION, "浙江省杭州市上城区杭州东站")],
        [_geocode_item(LONGXIANGQIAO, "浙江省杭州市西湖区龙翔桥地铁站")],
    )
    far = (CENTER[0] + 0.015, CENTER[1])
    monkeypatch.setattr(
        "services.search.fetch_around",
        lambda location, keywords, radius, city, timeout: _ok_around(
            {
                "name": "缺距离的远店",
                "address": "杭州市上城区远路9号",
                "location": f"{far[0]},{far[1]}",
                "distance": [],
            },
            {
                "name": "有距离的近店",
                "address": "杭州市上城区近路1号",
                "location": f"{CENTER[0]},{CENTER[1]}",
                "distance": "80",
            },
            {
                "name": "无坐标也无距离应丢弃",
                "address": "未知",
                "location": [],
                "distance": [],
            },
        ),
    )

    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 200
    pois = response.json()["data"]["pois"]
    assert [item["name"] for item in pois] == ["有距离的近店", "缺距离的远店"]
    assert pois[0]["distance_to_midpoint_m"] == 80.0
    assert pois[1]["distance_to_midpoint_m"] > 1000
    assert pois[1]["distance_to_midpoint_m"] != 0


def test_search_missing_request_field():
    response = client.post("/search", json={"city_a": "杭州"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "search"


def test_search_upstream_timeout(monkeypatch, tmp_path):
    _patch_store(monkeypatch, tmp_path)

    def boom(address: str, city: str, timeout: float):
        raise AppError(504, "UPSTREAM_TIMEOUT", "地点查询超时，请稍后重试。", "search")

    monkeypatch.setattr("services.geocode_resolve.fetch_geocode", boom)
    response = client.post("/search", json=NORMAL_REQUEST)
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert response.json()["error"]["stage"] == "search"
