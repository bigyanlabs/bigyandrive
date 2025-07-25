from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class ShareStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PremiumShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exposure_id: int = Field(foreign_key="exposure.id", index=True)
    shared_with_phone: str = Field(max_length=20, index=True)
    access_token: str = Field(unique=True, index=True)
    status: ShareStatus = Field(default=ShareStatus.ACTIVE)
    download_count: int = Field(default=0)
    max_downloads: Optional[int] = Field(default=None)
    last_accessed: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))