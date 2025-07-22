from pydantic import BaseModel, Field
from typing import Optional


class PhoneRegister(BaseModel):
    phone: str = Field(..., description="Phone number in international format")


class PhoneLogin(BaseModel):
    phone: str = Field(..., description="Phone number in international format")
    login_hash: str = Field(..., description="Login hash for authentication")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    user_type: str
    login_hash: str


class RegisterResponse(BaseModel):
    message: str
    user_id: int
    login_hash: str
    phone: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    phone: Optional[str] = None