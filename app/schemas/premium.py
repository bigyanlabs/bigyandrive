from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class PremiumExposeFile(BaseModel):
    file_id: int = Field(..., description="ID of file to expose")
    permission: str = Field(..., description="Permission level: read_only or download")
    expires_minutes: Optional[int] = Field(None, description="Expiration time in minutes (1-1440)")
    shared_with_phones: List[str] = Field(..., min_length=1, description="Phone numbers to share with")
    max_downloads_per_recipient: Optional[int] = Field(None, ge=1, description="Maximum downloads per recipient")

    @validator('permission')
    def validate_permission(cls, v):
        if v not in ['read_only', 'download']:
            raise ValueError('Permission must be read_only or download')
        return v

    @validator('expires_minutes')
    def validate_expires_minutes(cls, v):
        if v is not None and (v < 1 or v > 1440):
            raise ValueError('Expiration must be between 1 and 1440 minutes')
        return v


class PremiumAccessRequest(BaseModel):
    access_token: str = Field(..., description="Secure access token for premium share")
    phone: str = Field(..., description="Phone number for token validation")


class PremiumShareResponse(BaseModel):
    id: int
    exposure_id: int
    shared_with_phone: str
    access_token: str
    status: str
    download_count: int
    max_downloads: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class PremiumExposureResponse(BaseModel):
    id: int
    exposure_hash: str
    file_id: int
    permission: str
    exposure_type: str
    premium_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    shared_recipients: List[PremiumShareResponse]
    is_active: bool
    created_at: datetime


class AddRecipientRequest(BaseModel):
    exposure_hash: str = Field(..., description="Hash of exposure to add recipient to")
    phone: str = Field(..., description="Phone number to share with")
    max_downloads: Optional[int] = Field(None, ge=1, description="Maximum downloads for this recipient")


class RevokeShareRequest(BaseModel):
    share_id: int = Field(..., description="ID of share to revoke")