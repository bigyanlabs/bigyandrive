from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Annotated, Optional
from datetime import datetime, timedelta, timezone

from app.database import get_session
from app.models import User, File as FileModel, Exposure, ExposureType, Permission, FileStatus
from app.schemas import ExposeFile, ExposureResponse
from app.core import (
    generate_exposure_hash,
    can_expose_file,
    validate_exposure_minutes
)
from app.api.auth import get_current_user

router = APIRouter(prefix="/expose", tags=["exposure"])


@router.post("/file", response_model=ExposureResponse)
async def expose_file(
    expose_data: ExposeFile,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> ExposureResponse:
    """Expose a file for sharing"""
    
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user session"
        )
    
    if not can_expose_file(current_user, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free users can only expose one file at a time"
        )
    
    file_record = session.exec(
        select(FileModel).where(
            FileModel.id == expose_data.file_id,
            FileModel.owner_id == current_user.id,
            # FileModel.status == FileStatus.UPLOADED
        )
    ).first()
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or not uploaded"
        )
    
    if expose_data.permission not in ["read_only", "download"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid permission. Must be 'read_only' or 'download'"
        )
    
    expires_at: Optional[datetime] = None
    exposure_type = ExposureType.FREE
    
    if current_user.user_type.value == "premium":
        exposure_type = ExposureType.PREMIUM
        if expose_data.expires_minutes:
            if not validate_exposure_minutes(expose_data.expires_minutes):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid expiration time. Must be between 1 and 1440 minutes"
                )
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=expose_data.expires_minutes)
    else:
        # Free users: maximum 5 minutes expiry
        expiry_minutes = expose_data.expires_minutes if expose_data.expires_minutes else 30
        if expiry_minutes > 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Free users can only expose files for a maximum of 5 minutes"
            )
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    
    exposure_hash = generate_exposure_hash()
    
    exposure = Exposure(
        file_id=expose_data.file_id,
        owner_id=current_user.id,
        exposure_hash=exposure_hash,
        exposure_type=exposure_type,
        permission=Permission.READ_ONLY if expose_data.permission == "read_only" else Permission.DOWNLOAD,
        expires_at=expires_at
    )
    
    session.add(exposure)
    
    file_record.status = FileStatus.EXPOSED
    session.add(file_record)
    
    if current_user.user_type.value == "free":
        current_user.current_exposed_file_id = expose_data.file_id
        session.add(current_user)
    
    session.commit()
    session.refresh(exposure)
    
    if exposure.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create exposure"
        )
    
    return ExposureResponse(
        id=exposure.id,
        exposure_hash=exposure.exposure_hash,
        file_id=exposure.file_id,
        permission=exposure.permission.value,
        exposure_type=exposure.exposure_type.value,
        expires_at=exposure.expires_at,
        is_active=exposure.is_active,
        created_at=exposure.created_at
    )


@router.get("/list")
async def list_exposures(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """List all active exposures for the current user"""
    
    exposures = session.exec(
        select(Exposure).where(
            Exposure.owner_id == current_user.id,
            Exposure.is_active == True
        )
    ).all()
    
    exposure_list = []
    for exposure in exposures:
        file_record = session.get(FileModel, exposure.file_id)
        
        exposure_list.append({
            "id": exposure.id,
            "exposure_hash": exposure.exposure_hash,
            "file_id": exposure.file_id,
            "file_name": file_record.original_name if file_record else "Unknown",
            "permission": exposure.permission.value,
            "exposure_type": exposure.exposure_type.value,
            "expires_at": exposure.expires_at,
            "created_at": exposure.created_at
        })
    
    return {"exposures": exposure_list, "total": len(exposure_list)}


def _ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert timezone-naive datetime to timezone-aware UTC datetime"""
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=timezone.utc)
    
    return dt


def cleanup_expired_exposures(session: Session) -> int:
    """Clean up expired exposures and revert file statuses"""
    from app.models import User
    
    current_time = datetime.now(timezone.utc)
    
    # Find all expired exposures
    expired_exposures = session.exec(
        select(Exposure).where(
            Exposure.is_active == True,
            Exposure.expires_at != None
        )
    ).all()
    
    cleaned_count = 0
    
    for exposure in expired_exposures:
        # Convert expires_at to timezone-aware for comparison
        expires_at = _ensure_timezone_aware(exposure.expires_at)
        
        if expires_at and current_time > expires_at:
            # Mark exposure as inactive
            exposure.is_active = False
            session.add(exposure)
            
            # Revert file status
            file_record = session.get(FileModel, exposure.file_id)
            if file_record and file_record.status == FileStatus.EXPOSED:
                file_record.status = FileStatus.UPLOADED
                session.add(file_record)
            
            # Clear user's current exposed file if this was it
            owner = session.get(User, exposure.owner_id)
            if owner and owner.current_exposed_file_id == exposure.file_id:
                owner.current_exposed_file_id = None
                session.add(owner)
                
            cleaned_count += 1
    
    if cleaned_count > 0:
        session.commit()
    
    return cleaned_count


@router.get("/info/{exposure_hash}")
async def get_exposure_info(
    exposure_hash: str,
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Get public information about an exposure (for access requests)"""
    
    exposure = session.exec(
        select(Exposure).where(
            Exposure.exposure_hash == exposure_hash,
            Exposure.is_active == True
        )
    ).first()
    
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exposure not found or expired"
        )
    
    # Check if expired and cleanup
    current_time = datetime.now(timezone.utc)
    expires_at = _ensure_timezone_aware(exposure.expires_at)
    
    if expires_at and current_time > expires_at:
        # Mark exposure as inactive
        exposure.is_active = False
        session.add(exposure)
        
        # Revert file status
        file_record = session.get(FileModel, exposure.file_id)
        if file_record:
            file_record.status = FileStatus.UPLOADED
            session.add(file_record)
            
        # Clear user's current exposed file if this was it
        from app.models import User
        owner = session.get(User, exposure.owner_id)
        if owner and owner.current_exposed_file_id == exposure.file_id:
            owner.current_exposed_file_id = None
            session.add(owner)
            
        session.commit()
        
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Exposure has expired"
        )
    
    file_record = session.get(FileModel, exposure.file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return {
        "file_name": file_record.original_name,
        "file_size": file_record.file_size,
        "permission": exposure.permission.value,
        "exposure_type": exposure.exposure_type.value,
        "expires_at": exposure.expires_at
    }


@router.delete("/file/{exposure_hash}")
async def stop_exposure(
    exposure_hash: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Stop file exposure"""
    
    exposure = session.exec(
        select(Exposure).where(
            Exposure.exposure_hash == exposure_hash,
            Exposure.owner_id == current_user.id,
            Exposure.is_active == True
        )
    ).first()
    
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exposure not found or already stopped"
        )
    
    # Mark exposure as inactive
    exposure.is_active = False
    session.add(exposure)
    
    # Revert file status
    file_record = session.get(FileModel, exposure.file_id)
    if file_record:
        file_record.status = FileStatus.UPLOADED
        session.add(file_record)
    
    # Clear current exposed file for free users
    if current_user.user_type.value == "free":
        current_user.current_exposed_file_id = None
        session.add(current_user)
    
    session.commit()
    
    return {
        "message": "Exposure stopped successfully",
        "exposure_hash": exposure_hash
    }


@router.post("/cleanup-expired")
async def cleanup_expired(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Manually trigger cleanup of expired exposures"""
    count = cleanup_expired_exposures(session)
    return {"message": f"Cleaned up {count} expired exposures"}