from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class AccessStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class Access(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exposure_id: int = Field(foreign_key="exposure.id", index=True)
    requester_ip: str = Field(max_length=45, index=True)  # IPv6 support
    user_agent: Optional[str] = Field(default=None, max_length=500)
    status: AccessStatus = Field(default=AccessStatus.PENDING)
    approved_by: Optional[int] = Field(default=None, foreign_key="user.id")
    accessed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))