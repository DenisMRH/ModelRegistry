import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from api.models.registry import StageEnum


class ModelCreate(BaseModel):
    name: str
    team_id: str
    description: str | None = None


class ModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    team_id: str
    description: str | None
    created_at: datetime


class VersionCreate(BaseModel):
    metrics: dict | None = None
    parameters: dict | None = None


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_id: uuid.UUID
    version: int
    stage: StageEnum | None
    artifact_uri: str
    metrics: dict | None
    parameters: dict | None
    created_at: datetime


class StageUpdate(BaseModel):
    stage: StageEnum


class UploadResponse(BaseModel):
    version_id: uuid.UUID
    version: int
    upload_url: str


class ProductionResponse(VersionResponse):
    download_url: str
