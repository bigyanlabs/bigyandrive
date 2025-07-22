from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ExposeFile(BaseModel):
    file_id: int = Field(..., description="ID of file to expose")
    permission: str = Field(..., description="Permission level: read_only or download")
    expires_minutes: Optional[int] = Field(None, description="Expiration time in minutes (premium only)")


class ExposureResponse(BaseModel):
    id: int
    exposure_hash: str
    file_id: int
    permission: str
    exposure_type: str
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime


class ExposureAccess(BaseModel):
    exposure_hash: str = Field(..., description="Hash of the exposed file")


class AccessRequest(BaseModel):
    exposure_hash: str = Field(..., description="Hash of the exposed file")
    requester_ip: str = Field(..., description="IP address of requester")


class AccessResponse(BaseModel):
    access_granted: bool
    message: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    permission: Optional[str] = None


class ApprovalRequest(BaseModel):
    access_id: int = Field(..., description="ID of access request to approve/deny")
    approved: bool = Field(..., description="Whether to approve or deny access")


class PendingAccess(BaseModel):
    id: int
    exposure_hash: str
    requester_ip: str
    user_agent: Optional[str] = None
    created_at: datetime


class PendingAccessList(BaseModel):
    pending_requests: list[PendingAccess]
    total: int