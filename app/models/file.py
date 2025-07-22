from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    EXPOSED = "exposed"
    DELETED = "deleted"


class File(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    original_name: str = Field(max_length=255)
    hashed_name: str = Field(unique=True, index=True)
    file_size: int = Field(ge=0)
    mime_type: str = Field(max_length=100)
    status: FileStatus = Field(default=FileStatus.UPLOADED)
    upload_path: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))