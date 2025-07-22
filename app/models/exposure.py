from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class ExposureType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"


class Permission(str, Enum):
    READ_ONLY = "read_only"
    DOWNLOAD = "download"


class Exposure(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: int = Field(foreign_key="file.id", index=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    exposure_hash: str = Field(unique=True, index=True)
    exposure_type: ExposureType = Field(default=ExposureType.FREE)
    permission: Permission = Field(default=Permission.READ_ONLY)
    expires_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))