
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, col
from typing import Annotated

from app.database import get_session
from app.models import User, Access, AccessStatus, Exposure
from app.schemas import ApprovalRequest, PendingAccess, PendingAccessList
from app.api.auth import get_current_user

router = APIRouter(prefix="/approve", tags=["approval"])


@router.get("/pending", response_model=PendingAccessList)
async def get_pending_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> PendingAccessList:
    """Get all pending access requests for user's exposed files"""
    
    user_exposures = session.exec(
        select(Exposure).where(
            Exposure.owner_id == current_user.id,
            Exposure.is_active == True
        )
    ).all()
    
    exposure_ids = [exp.id for exp in user_exposures if exp.id is not None]
    
    if not exposure_ids:
        return PendingAccessList(pending_requests=[], total=0)
    
    # Get pending access requests for these exposures
    pending_accesses = session.exec(
        select(Access).where(
            col(Access.exposure_id).in_(exposure_ids),
            Access.status == AccessStatus.PENDING
        )
    ).all()
    
    # Create response with exposure hash lookup
    exposure_lookup = {exp.id: exp.exposure_hash for exp in user_exposures}
    
    pending_requests = [
        PendingAccess(
            id=access.id if access.id is not None else 0,
            exposure_hash=exposure_lookup.get(access.exposure_id, ""),
            requester_ip=access.requester_ip,
            user_agent=access.user_agent,
            created_at=access.created_at
        ) for access in pending_accesses
    ]
    
    return PendingAccessList(
        pending_requests=pending_requests,
        total=len(pending_requests)
    )


@router.post("/decision", response_model=dict)
async def approve_or_deny_access(
    approval_data: ApprovalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Approve or deny an access request"""
    
    # Get access request
    access_record = session.exec(
        select(Access).where(
            Access.id == approval_data.access_id,
            Access.status == AccessStatus.PENDING
        )
    ).first()
    
    if not access_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access request not found or already processed"
        )
    
    # Verify ownership through exposure
    exposure = session.get(Exposure, access_record.exposure_id)
    if not exposure or exposure.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process this request"
        )
    
    # Update access status
    if approval_data.approved:
        access_record.status = AccessStatus.APPROVED
        access_record.approved_by = current_user.id
        message = "Access request approved successfully"
    else:
        access_record.status = AccessStatus.DENIED
        message = "Access request denied successfully"
    
    session.add(access_record)
    session.commit()
    
    return {
        "message": message,
        "access_id": access_record.id,
        "approved": approval_data.approved,
        "requester_ip": access_record.requester_ip
    }


@router.post("/bulk-decision", response_model=dict)
async def bulk_approve_or_deny(
    access_ids: list[int],
    approved: bool,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Bulk approve or deny multiple access requests"""
    
    if not access_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access IDs provided"
        )
    
    # Get all access requests
    access_records = session.exec(
        select(Access).where(
            col(Access.id).in_(access_ids),
            Access.status == AccessStatus.PENDING
        )
    ).all()
    
    if not access_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid access requests found"
        )
    
    # Verify ownership for each access request
    valid_accesses = []
    for access_record in access_records:
        exposure = session.get(Exposure, access_record.exposure_id)
        if exposure and exposure.owner_id == current_user.id:
            valid_accesses.append(access_record)
    
    if not valid_accesses:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process these requests"
        )
    
    processed_count = 0
    
    for access_record in valid_accesses:
        if approved:
            access_record.status = AccessStatus.APPROVED
            access_record.approved_by = current_user.id
        else:
            access_record.status = AccessStatus.DENIED
        
        session.add(access_record)
        processed_count += 1
    
    session.commit()
    
    action = "approved" if approved else "denied"
    return {
        "message": f"Successfully {action} {processed_count} access requests",
        "processed_count": processed_count,
        "approved": approved
    }


@router.delete("/clear-denied")
async def clear_denied_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Clear all denied access requests for user's exposures"""
    
    # Get user's exposures
    user_exposures = session.exec(
        select(Exposure).where(Exposure.owner_id == current_user.id)
    ).all()
    
    exposure_ids = [exp.id for exp in user_exposures if exp.id is not None]
    
    if not exposure_ids:
        return {"message": "No denied access requests found", "deleted_count": 0}
    
    # Get denied access requests
    denied_accesses = session.exec(
        select(Access).where(
            col(Access.exposure_id).in_(exposure_ids),
            Access.status == AccessStatus.DENIED
        )
    ).all()
    
    deleted_count = 0
    for access_record in denied_accesses:
        session.delete(access_record)
        deleted_count += 1
    
    session.commit()
    
    return {
        "message": f"Cleared {deleted_count} denied access requests",
        "deleted_count": deleted_count
    }


@router.get("/history")
async def get_access_history(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    offset: int = 0
) -> dict:
    """Get access history for user's exposed files"""
    
    # Get user's exposures
    user_exposures = session.exec(
        select(Exposure).where(Exposure.owner_id == current_user.id)
    ).all()
    
    exposure_ids = [exp.id for exp in user_exposures if exp.id is not None]
    
    if not exposure_ids:
        return {"history": [], "total": 0, "limit": limit, "offset": offset}
    
    # Get access history with pagination
    access_records = session.exec(
        select(Access).where(
            col(Access.exposure_id).in_(exposure_ids)
        ).offset(offset).limit(limit)
    ).all()
    
    # Create lookup for exposure hashes
    exposure_lookup = {exp.id: exp.exposure_hash for exp in user_exposures}
    
    history_items = []
    for access_record in access_records:
        history_items.append({
            "id": access_record.id,
            "exposure_hash": exposure_lookup.get(access_record.exposure_id, ""),
            "requester_ip": access_record.requester_ip,
            "user_agent": access_record.user_agent,
            "status": access_record.status.value,
            "requested_at": access_record.created_at,
            "accessed_at": access_record.accessed_at,
            "approved_by": access_record.approved_by
        })
    
    # Get total count
    total_access_records = session.exec(
        select(Access).where(col(Access.exposure_id).in_(exposure_ids))
    ).all()
    
    return {
        "history": history_items,
        "total": len(total_access_records),
        "limit": limit,
        "offset": offset
    }