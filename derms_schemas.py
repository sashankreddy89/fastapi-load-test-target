import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from derms_models import AssetType, AssetStatus


class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class AssetCreate(BaseModel):
    name: str
    asset_type: AssetType
    status: AssetStatus


class AssetResponse(BaseModel):
    name: str
    asset_type: AssetType
    status: AssetStatus
    id: UUID
    owner_id: UUID
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class AssetStatusUpdate(BaseModel):
    status: AssetStatus

class MetricsResponse(BaseModel):
    total_assets: int
    active_count: int
    inactive_count: int
    fault_count: int
    maintenance_count: int
    solar_count: int
    battery_count: int
    ev_count: int
    wind_count: int
    