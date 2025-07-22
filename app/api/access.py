# access.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import Annotated
import os
from datetime import datetime, timezone

from app.database import get_session
from app.models import User, File as FileModel, Exposure, Access, AccessStatus
from app.schemas import AccessRequest, AccessResponse
from app.core import (
    can_access_file,
    should_blacklist_ip,
    blacklist_ip,
    get_path,
    sanitize_user_agent
)

router = APIRouter(prefix="/access", tags=["access"])


@router.post("/request", response_model=AccessResponse)
async def request_access(
    access_data: AccessRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)]
) -> AccessResponse:
    """Request access to an exposed file"""
    
    client_ip = request.client.host if request.client else "unknown"
    user_agent = sanitize_user_agent(request.headers.get("user-agent", ""))
    
    exposure = session.exec(
        select(Exposure).where(
            Exposure.exposure_hash == access_data.exposure_hash,
            Exposure.is_active == True
        )
    ).first()
    
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exposure not found or expired"
        )
    
    if exposure.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid exposure record"
        )
    
    # Check if access is allowed
    can_access, reason = can_access_file(client_ip, exposure, session)
    
    if not can_access:
        # Create failed access record
        failed_access = Access(
            exposure_id=exposure.id,
            requester_ip=client_ip,
            user_agent=user_agent,
            status=AccessStatus.DENIED
        )
        
        session.add(failed_access)
        session.commit()
        
        # Check if IP should be blacklisted
        if should_blacklist_ip(client_ip, exposure.id, session):
            blacklist_ip(client_ip, exposure.id, session)
            reason = "IP address has been blacklisted due to multiple failed attempts"
        
        return AccessResponse(
            access_granted=False,
            message=reason
        )
    
    # For premium users, grant immediate access
    if exposure.exposure_type.value == "premium":
        # Create successful access record
        successful_access = Access(
            exposure_id=exposure.id,
            requester_ip=client_ip,
            user_agent=user_agent,
            status=AccessStatus.APPROVED,
            accessed_at=datetime.now(timezone.utc)
        )
        
        session.add(successful_access)
        session.commit()
        
        # Get file info
        file_record = session.get(FileModel, exposure.file_id)
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return AccessResponse(
            access_granted=True,
            message="Access granted",
            file_name=file_record.original_name,
            file_size=file_record.file_size,
            permission=exposure.permission.value
        )
    
    # For free users, create pending access request
    pending_access = Access(
        exposure_id=exposure.id,
        requester_ip=client_ip,
        user_agent=user_agent,
        status=AccessStatus.PENDING
    )
    
    session.add(pending_access)
    session.commit()
    
    return AccessResponse(
        access_granted=False,
        message="Access request sent to file owner for approval"
    )


@router.get("/download/{exposure_hash}")
async def download_exposed_file(
    exposure_hash: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)]
) -> StreamingResponse:
    """Download an exposed file"""
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Get exposure
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
    
    if exposure.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid exposure record"
        )
    
    # Check if access is allowed
    can_access, reason = can_access_file(client_ip, exposure, session)
    
    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason
        )
    
    # Check if download permission is granted
    if exposure.permission.value == "read_only":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download not permitted for this file"
        )
    
    # Get file
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
    
    # Update access record with download timestamp
    access_record = session.exec(
        select(Access).where(
            Access.exposure_id == exposure.id,
            Access.requester_ip == client_ip,
            Access.status == AccessStatus.APPROVED
        )
    ).first()
    
    if access_record:
        access_record.accessed_at = datetime.now(timezone.utc)
        session.add(access_record)
        session.commit()
    
    # Stream file
    def file_generator():
        with open(file_path, "rb") as file:
            while chunk := file.read(8 * 1024 * 1024):  # 8MB chunks
                yield chunk
    
    return StreamingResponse(
        file_generator(),
        media_type=file_record.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.original_name}"',
            "Content-Length": str(file_record.file_size)
        }
    )


@router.get("/view/{exposure_hash}")
async def view_file_info(
    exposure_hash: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """View file information (read-only access)"""
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Get exposure
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
    
    if exposure.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid exposure record"
        )
    
    # Check if access is allowed
    can_access, reason = can_access_file(client_ip, exposure, session)
    
    if not can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason
        )
    
    # Get file info
    file_record = session.get(FileModel, exposure.file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Update access record with view timestamp
    access_record = session.exec(
        select(Access).where(
            Access.exposure_id == exposure.id,
            Access.requester_ip == client_ip,
            Access.status == AccessStatus.APPROVED
        )
    ).first()
    
    if access_record:
        access_record.accessed_at = datetime.now(timezone.utc)
        session.add(access_record)
        session.commit()
    
    return {
        "file_name": file_record.original_name,
        "file_size": file_record.file_size,
        "mime_type": file_record.mime_type,
        "permission": exposure.permission.value,
        "uploaded_at": file_record.created_at
    }