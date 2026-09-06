from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    request_id: str
    data: T


class HealthData(BaseModel):
    status: str = Field(examples=["ok"])


class UploadData(BaseModel):
    audio_id: str = Field(examples=["rec_7c2e1b6a-4d11-4f0c-8a9e-2b3c4d5e6f70"])
