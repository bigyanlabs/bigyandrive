from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid
from typing import Optional
from app.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_login_hash() -> str:
    """Generate a secure login hash for phone-based auth"""
    return str(uuid.uuid4())


def generate_exposure_hash() -> str:
    """Generate a secure hash for file exposure"""
    return hashlib.sha256(f"{secrets.token_hex(32)}{datetime.now(timezone.utc)}".encode()).hexdigest()


def generate_file_hash(original_name: str) -> str:
    """Generate a secure hash for file storage"""
    timestamp = str(datetime.now(timezone.utc).timestamp())
    random_part = secrets.token_hex(16)
    return hashlib.sha256(f"{original_name}{timestamp}{random_part}".encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def generate_premium_share_token(phone: str, exposure_hash: str) -> str:
    """Generate secure token for premium phone-based sharing"""
    timestamp = str(datetime.now(timezone.utc).timestamp())
    data_string = f"{phone}:{exposure_hash}:{timestamp}:{secrets.token_hex(16)}"
    return hashlib.sha256(data_string.encode()).hexdigest()


def verify_premium_token_format(token: str) -> bool:
    """Verify premium share token format is valid"""
    try:
        return len(token) == 64 and all(c in '0123456789abcdef' for c in token)
    except:
        return False