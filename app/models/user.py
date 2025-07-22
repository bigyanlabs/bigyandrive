from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class UserType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str = Field(unique=True, index=True)
    user_type: UserType = Field(default=UserType.FREE)
    login_hash: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    current_exposed_file_id: Optional[int] = Field(default=None, foreign_key="file.id")