from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from typing import Annotated
from app.database import get_session
from app.models import User, UserType
from app.schemas import (
    PhoneRegister,
    PhoneLogin,
    LoginResponse,
    RegisterResponse,
)
from app.core import (
    validate_phone,
    generate_login_hash,
    create_access_token
)

router = APIRouter(prefix="/auth", tags=["authentication"])

security = HTTPBearer()


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    user_data: PhoneRegister,
    session: Annotated[Session, Depends(get_session)]
) -> RegisterResponse:
    """Register a new user with phone number"""
    
    is_valid, formatted_phone = validate_phone(user_data.phone)
    if not is_valid or not formatted_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    
    existing_user = session.exec(
        select(User).where(User.phone == formatted_phone)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this phone number already exists"
        )
    
    login_hash = generate_login_hash()
    new_user = User(
        phone=formatted_phone,
        login_hash=login_hash,
        user_type=UserType.FREE
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    if new_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user ID after registration"
        )
    
    return RegisterResponse(
        message="User registered successfully",
        user_id=new_user.id,
        login_hash=login_hash,
        phone=formatted_phone
    )


@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_data: PhoneLogin,
    session: Annotated[Session, Depends(get_session)]
) -> LoginResponse:
    """Login user with phone number and login hash"""
    
    is_valid, formatted_phone = validate_phone(login_data.phone)
    if not is_valid or not formatted_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    
    user = session.exec(
        select(User).where(
            User.phone == formatted_phone,
            User.login_hash == login_data.login_hash,
            User.is_active == True
        )
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or login hash"
        )
    
    token_data = {"user_id": user.id, "phone": user.phone}
    access_token = create_access_token(token_data)
    
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user ID during login"
        )
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        user_type=user.user_type.value,
        login_hash=user.login_hash if user.login_hash is not None else ""
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[Session, Depends(get_session)]
) -> User:
    """Get current authenticated user from token"""
    from app.core import verify_token
    
    token = credentials.credentials
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user

@router.post("/upgrade-premium", response_model=dict)
async def upgrade_to_premium(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Upgrade user to premium (for testing purposes)"""
    from datetime import datetime, timezone
    
    if current_user.user_type == UserType.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already premium"
        )
    
    current_user.user_type = UserType.PREMIUM
    current_user.updated_at = datetime.now(timezone.utc)
    
    session.add(current_user)
    session.commit()
    
    return {
        "message": "Successfully upgraded to premium",
        "user_type": current_user.user_type.value,
        "phone": current_user.phone
    }