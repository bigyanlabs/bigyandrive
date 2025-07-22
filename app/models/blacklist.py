from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone


class Blacklist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ip_address: str = Field(max_length=45, index=True)  # IPv6 support
    exposure_id: int = Field(foreign_key="exposure.id", index=True)
    failed_attempts: int = Field(default=1, ge=1)
    blocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))