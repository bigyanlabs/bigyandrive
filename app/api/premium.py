from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import Annotated, List
import json
import os
from datetime import datetime, timedelta, timezone

from app.database import get_session
from app.models import (
    User, UserType, File as FileModel, Exposure, ExposureType, 
    Permission, PremiumShare, ShareStatus, FileStatus
)
from app.schemas import (
    PremiumExposeFile, PremiumExposureResponse, PremiumShareResponse,
    AddRecipientRequest, RevokeShareRequest
)
from app.core import (
    generate_exposure_hash, generate_premium_share_token,
    verify_premium_token_format, validate_phone, get_path,
    validate_exposure_minutes
)
from app.api.auth import get_current_user

router = APIRouter(prefix="/premium", tags=["premium"])


@router.post("/expose", response_model=PremiumExposureResponse)
async def create_premium_exposure(
    expose_data: PremiumExposeFile,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> PremiumExposureResponse:
    """Create premium exposure with phone-based sharing"""
    
    if current_user.user_type != UserType.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium features require premium subscription"
        )
    
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user session"
        )
    
    file_record = session.exec(
        select(FileModel).where(
            FileModel.id == expose_data.file_id,
            FileModel.owner_id == current_user.id,
            FileModel.status != FileStatus.DELETED
        )
    ).first()
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or not accessible"
        )
    
    validated_phones = []
    for phone in expose_data.shared_with_phones:
        is_valid, formatted_phone = validate_phone(phone)
        if not is_valid or not formatted_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid phone number format: {phone}"
            )
        if formatted_phone in validated_phones:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate phone number: {phone}"
            )
        validated_phones.append(formatted_phone)
    
    expires_at = None
    if expose_data.expires_minutes:
        if not validate_exposure_minutes(expose_data.expires_minutes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid expiration time. Must be between 1 and 1440 minutes"
            )
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expose_data.expires_minutes)
    
    exposure_hash = generate_exposure_hash()
    premium_token = generate_exposure_hash() 
    
    exposure = Exposure(
        file_id=expose_data.file_id,
        owner_id=current_user.id,
        exposure_hash=exposure_hash,
        exposure_type=ExposureType.PREMIUM,
        permission=Permission.READ_ONLY if expose_data.permission == "read_only" else Permission.DOWNLOAD,
        expires_at=expires_at,
        premium_token=premium_token,
        shared_with_phones=json.dumps(validated_phones),
        max_downloads_per_recipient=expose_data.max_downloads_per_recipient
    )
    
    session.add(exposure)
    session.flush()  
    session.refresh(exposure) 
    
    if exposure.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create exposure"
        )
    
    share_responses = []
    for phone in validated_phones:
        access_token = generate_premium_share_token(phone, exposure_hash)
        
        if exposure.id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Exposure ID is required"
            )
        
        premium_share = PremiumShare(
            exposure_id=exposure.id,  
            shared_with_phone=phone,
            access_token=access_token,
            max_downloads=expose_data.max_downloads_per_recipient,
            expires_at=expires_at
        )
        
        session.add(premium_share)
        session.flush()
        session.refresh(premium_share)
        
        if premium_share.id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create premium share"
            )
        
        share_responses.append(PremiumShareResponse(
            id=premium_share.id or 0,
            exposure_id=exposure.id or 0,
            shared_with_phone=phone,
            access_token=access_token,
            status=premium_share.status.value,
            download_count=premium_share.download_count,
            max_downloads=premium_share.max_downloads,
            expires_at=premium_share.expires_at,
            created_at=premium_share.created_at
        ))
    
    file_record.status = FileStatus.EXPOSED
    session.add(file_record)
    
    session.commit()
    
    return PremiumExposureResponse(
        id=exposure.id,
        exposure_hash=exposure.exposure_hash,
        file_id=exposure.file_id,
        permission=exposure.permission.value,
        exposure_type=exposure.exposure_type.value,
        premium_token=exposure.premium_token,
        expires_at=exposure.expires_at,
        shared_recipients=share_responses,
        is_active=exposure.is_active,
        created_at=exposure.created_at
    )


@router.post("/share/add", response_model=PremiumShareResponse)
async def add_recipient_to_exposure(
    share_data: AddRecipientRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> PremiumShareResponse:
    """Add a new recipient to an existing premium exposure"""
    
    if current_user.user_type != UserType.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium features require premium subscription"
        )
    
    is_valid, formatted_phone = validate_phone(share_data.phone)
    if not is_valid or not formatted_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    
    exposure = session.exec(
        select(Exposure).where(
            Exposure.exposure_hash == share_data.exposure_hash,
            Exposure.owner_id == current_user.id,
            Exposure.exposure_type == ExposureType.PREMIUM,
            Exposure.is_active == True
        )
    ).first()
    
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Premium exposure not found or not accessible"
        )
    
    existing_share = session.exec(
        select(PremiumShare).where(
            PremiumShare.exposure_id == exposure.id,
            PremiumShare.shared_with_phone == formatted_phone,
            PremiumShare.status == ShareStatus.ACTIVE
        )
    ).first()
    
    if existing_share:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already has active access to this file"
        )
    
    access_token = generate_premium_share_token(formatted_phone, exposure.exposure_hash)
    
    if exposure.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Exposure ID is required"
        )
    
    premium_share = PremiumShare(
        exposure_id=exposure.id,
        shared_with_phone=formatted_phone,
        access_token=access_token,
        max_downloads=share_data.max_downloads,
        expires_at=exposure.expires_at
    )
    
    session.add(premium_share)
    session.commit()
    session.refresh(premium_share)
    
    return PremiumShareResponse(
        id=premium_share.id or 0,
        exposure_id=exposure.id or 0,
        shared_with_phone=formatted_phone,
        access_token=access_token,
        status=premium_share.status.value,
        download_count=premium_share.download_count,
        max_downloads=premium_share.max_downloads,
        expires_at=premium_share.expires_at,
        created_at=premium_share.created_at
    )


@router.post("/share/revoke", response_model=dict)
async def revoke_premium_share(
    revoke_data: RevokeShareRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Revoke access for a specific recipient"""
    
    if current_user.user_type != UserType.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium features require premium subscription"
        )
    
    premium_share = session.exec(
        select(PremiumShare).where(PremiumShare.id == revoke_data.share_id)
    ).first()
    
    if not premium_share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )
    
    exposure = session.get(Exposure, premium_share.exposure_id)
    if not exposure or exposure.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this share"
        )
    
    premium_share.status = ShareStatus.REVOKED
    premium_share.updated_at = datetime.now(timezone.utc)
    
    session.add(premium_share)
    session.commit()
    
    return {
        "message": "Share access revoked successfully",
        "share_id": revoke_data.share_id,
        "revoked_phone": premium_share.shared_with_phone
    }


@router.get("/access/{access_token}")
async def access_premium_file(
    access_token: str,
    phone: str,
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Access premium shared file with token and phone verification"""
    
    if not verify_premium_token_format(access_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid access token format"
        )
    
    is_valid, formatted_phone = validate_phone(phone)
    if not is_valid or not formatted_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    
    premium_share = session.exec(
        select(PremiumShare).where(
            PremiumShare.access_token == access_token,
            PremiumShare.shared_with_phone == formatted_phone,
            PremiumShare.status == ShareStatus.ACTIVE
        )
    ).first()
    
    if not premium_share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid access token or phone number"
        )
    
    if premium_share.expires_at:
        current_time = datetime.now(timezone.utc)
        expires_at = premium_share.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if current_time > expires_at:
            premium_share.status = ShareStatus.EXPIRED
            session.add(premium_share)
            session.commit()
            
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Access token has expired"
            )
    
    exposure = session.get(Exposure, premium_share.exposure_id)
    if not exposure or not exposure.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File exposure no longer active"
        )
    
    file_record = session.get(FileModel, exposure.file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    premium_share.last_accessed = datetime.now(timezone.utc)
    session.add(premium_share)
    session.commit()
    
    return {
        "file_name": file_record.original_name,
        "file_size": file_record.file_size,
        "mime_type": file_record.mime_type,
        "permission": exposure.permission.value,
        "download_count": premium_share.download_count,
        "max_downloads": premium_share.max_downloads,
        "expires_at": premium_share.expires_at
    }


@router.get("/download/{access_token}")
@router.get("/download/{access_token}")
async def download_premium_file(
    access_token: str,
    phone: str,
    session: Annotated[Session, Depends(get_session)]
) -> StreamingResponse:
    
    if not verify_premium_token_format(access_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid access token format"
        )
    
    is_valid, formatted_phone = validate_phone(phone)
    if not is_valid or not formatted_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )
    
    premium_share = session.exec(
        select(PremiumShare).where(
            PremiumShare.access_token == access_token,
            PremiumShare.shared_with_phone == formatted_phone,
            PremiumShare.status == ShareStatus.ACTIVE
        )
    ).first()
    
    if not premium_share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid access token or phone number"
        )
    
    if premium_share.max_downloads and premium_share.download_count >= premium_share.max_downloads:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download limit exceeded for this recipient"
        )
    
    exposure = session.get(Exposure, premium_share.exposure_id)
    if not exposure or not exposure.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File exposure no longer active"
        )
    
    if exposure.permission != Permission.DOWNLOAD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download not permitted for this file"
        )
    
    file_record = session.get(FileModel, exposure.file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    file_path = get_path(file_record.hashed_name)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage"
        )
    
    premium_share.download_count += 1
    premium_share.last_accessed = datetime.now(timezone.utc)
    session.add(premium_share)
    session.commit()
    
    def file_generator():
        with open(file_path, "rb") as file:
            while chunk := file.read(8 * 1024 * 1024): 
                yield chunk
    
    return StreamingResponse(
        file_generator(),
        media_type=file_record.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.original_name}"',
            "Content-Length": str(file_record.file_size)
        }
    )


@router.get("/exposures", response_model=List[PremiumExposureResponse])
async def list_premium_exposures(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> List[PremiumExposureResponse]:
    """List all premium exposures for current user"""
    
    if current_user.user_type != UserType.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium features require premium subscription"
        )
    
    exposures = session.exec(
        select(Exposure).where(
            Exposure.owner_id == current_user.id,
            Exposure.exposure_type == ExposureType.PREMIUM,
            Exposure.is_active == True
        )
    ).all()
    
    results = []
    for exposure in exposures:
        shares = session.exec(
            select(PremiumShare).where(PremiumShare.exposure_id == exposure.id)
        ).all()
        
        share_responses = [
            PremiumShareResponse(
                id=share.id or 0,
                exposure_id=exposure.id or 0,
                shared_with_phone=share.shared_with_phone,
                access_token=share.access_token,
                status=share.status.value,
                download_count=share.download_count,
                max_downloads=share.max_downloads,
                expires_at=share.expires_at,
                created_at=share.created_at
            ) for share in shares
        ]
        
        results.append(PremiumExposureResponse(
            id=exposure.id or 0,
            exposure_hash=exposure.exposure_hash,
            file_id=exposure.file_id,
            permission=exposure.permission.value,
            exposure_type=exposure.exposure_type.value,
            premium_token=exposure.premium_token,
            expires_at=exposure.expires_at,
            shared_recipients=share_responses,
            is_active=exposure.is_active,
            created_at=exposure.created_at
        ))
    
    return results
