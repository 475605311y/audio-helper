from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    request_id: str
    data: T


class HealthData(BaseModel):
    status: str = Field(examples=["ok"])


class UploadData(BaseModel):
    audio_id: str = Field(examples=["rec_7c2e1b6a-4d11-4f0c-8a9e-2b3c4d5e6f70"])


class AsrRequest(BaseModel):
    audio_id: str = Field(min_length=1)


class AsrData(BaseModel):
    text: str = Field(
        examples=["我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。"]
    )


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)
    city: str = Field(min_length=1)


class ExtractModelOutput(BaseModel):
    model_config = ConfigDict(strict=True)

    city_a: str | None
    address_a: str | None
    city_b: str | None
    address_b: str | None
    category: str | None
    party_count: int | None
    incomplete_reason: str | None


class ExtractData(BaseModel):
    city_a: str
    address_a: str
    city_b: str
    address_b: str
    category: str


class SearchRequest(BaseModel):
    city_a: str = Field(min_length=1)
    address_a: str = Field(min_length=1)
    city_b: str = Field(min_length=1)
    address_b: str = Field(min_length=1)
    category: str = Field(min_length=1)


class Midpoint(BaseModel):
    longitude: float
    latitude: float


class PoiItem(BaseModel):
    name: str
    address: str
    distance_to_midpoint_m: float


class SearchData(BaseModel):
    search_id: str = Field(examples=["srch_0e9b8a77-2c3d-4e5f-a617-89ab0c1d2e3f"])
    midpoint: Midpoint
    pois: list[PoiItem]


class FinalizeRequest(BaseModel):
    search_id: str = Field(min_length=1)


class FinalizeData(BaseModel):
    reply_text: str
    audio_url: str | None = Field(
        examples=["http://localhost:8003/audio/tts_5a6b7c8d-9e0f-41a2-b3c4-d5e6f7081920"]
    )
    warning: str | None = None
