from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FileUpload(BaseModel):
    original_name: str = Field(..., description="Original filename")


class FileResponse(BaseModel):
    id: int
    original_name: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime


class FileList(BaseModel):
    files: list[FileResponse]
    total: int


class FileDelete(BaseModel):
    file_id: int = Field(..., description="ID of file to delete")


class FileStats(BaseModel):
    id: int
    original_name: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime
    is_exposed: bool
    exposure_hash: Optional[str] = None