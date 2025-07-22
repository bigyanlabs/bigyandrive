from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from app.models import User, Exposure, Access, Blacklist, UserType, AccessStatus
from app.config import settings


def _ensure_timezone_aware(dt: datetime) -> datetime:
    """Convert timezone-naive datetime to timezone-aware UTC datetime"""
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


def can_expose_file(user: User, session: Session) -> bool:
    """Check if user can expose a file"""
    if user.user_type == UserType.PREMIUM:
        return True
    
    if user.current_exposed_file_id is None:
        return True
    
    exposure = session.get(Exposure, user.current_exposed_file_id)
    return exposure is None or not exposure.is_active


def is_ip_blacklisted(ip_address: str, exposure_id: int, session: Session) -> bool:
    """Check if IP is blacklisted for a specific exposure"""
    current_time = datetime.now(timezone.utc)
    
    query = select(Blacklist).where(
        Blacklist.ip_address == ip_address,
        Blacklist.exposure_id == exposure_id,
        Blacklist.is_active == True
    )
    
    blacklist_entries = session.exec(query).all()
    
    # Check each entry for expiration with proper timezone handling
    for entry in blacklist_entries:
        if entry.expires_at:
            expires_at = _ensure_timezone_aware(entry.expires_at)
            if current_time < expires_at:
                return True
    
    return False


def get_failed_attempts(ip_address: str, exposure_id: int, session: Session) -> int:
    """Get number of failed attempts for IP on specific exposure"""
    query = select(Access).where(
        Access.requester_ip == ip_address,
        Access.exposure_id == exposure_id,
        Access.status == AccessStatus.DENIED
    )
    
    failed_attempts = session.exec(query).all()
    return len(failed_attempts)


def should_blacklist_ip(ip_address: str, exposure_id: int, session: Session) -> bool:
    """Check if IP should be blacklisted after failed attempt"""
    failed_count = get_failed_attempts(ip_address, exposure_id, session)
    return failed_count >= settings.max_login_attempts


def blacklist_ip(ip_address: str, exposure_id: int, session: Session) -> bool:
    """Add IP to blacklist"""
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.blacklist_duration_hours)
        
        blacklist_entry = Blacklist(
            ip_address=ip_address,
            exposure_id=exposure_id,
            failed_attempts=get_failed_attempts(ip_address, exposure_id, session),
            expires_at=expires_at
        )
        
        session.add(blacklist_entry)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False


def is_exposure_expired(exposure: Exposure) -> bool:
    """Check if exposure has expired"""
    if exposure.expires_at is None:
        return False
    
    current_time = datetime.now(timezone.utc)
    expires_at = _ensure_timezone_aware(exposure.expires_at)
    
    return current_time > expires_at


def can_access_file(ip_address: str, exposure: Exposure, session: Session) -> tuple[bool, str]:
    """Check if IP can access file with reason"""
    if not exposure.is_active:
        return False, "Exposure is no longer active"
    
    if is_exposure_expired(exposure):
        return False, "Exposure has expired"
    
    if exposure.id is None:
        return False, "Exposure ID is missing"
        
    if is_ip_blacklisted(ip_address, exposure.id, session):
        return False, "IP address is blacklisted"
    
    if exposure.exposure_type.value == "free":
        query = select(Access).where(
            Access.exposure_id == exposure.id,
            Access.requester_ip == ip_address,
            Access.status == AccessStatus.APPROVED
        )
        
        approved_access = session.exec(query).first()
        if not approved_access:
            return False, "Access not approved by owner"
    
    return True, "Access granted"