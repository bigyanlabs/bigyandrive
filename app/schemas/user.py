from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    id: int
    phone: str
    user_type: str
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    user_type: Optional[str] = Field(None, description="User type: free or premium")


class UserStats(BaseModel):
    id: int
    phone: str
    user_type: str
    total_files: int
    total_exposures: int
    current_exposed_file: Optional[str] = None
    created_at: datetime


class UserResponse(BaseModel):
    message: str
    user: UserProfile