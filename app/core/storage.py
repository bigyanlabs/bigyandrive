import os
import aiofiles
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from app.config import settings
from app.core.security import generate_file_hash


async def save_file(file: UploadFile, original_name: str) -> tuple[str, str]:
    """Save uploaded file and return hashed filename and full path"""
    hashed_name = generate_file_hash(original_name)
    file_extension = Path(original_name).suffix
    full_name = f"{hashed_name}{file_extension}"
    
    file_path = Path(settings.storage_path) / full_name
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(file_path, 'wb') as buffer:
        while chunk := await file.read(8 * 1024 * 1024):  # 8MB chunks
            await buffer.write(chunk)
    
    return full_name, str(file_path)


async def remove_file(file_path: str) -> bool:
    """Remove file from storage asynchronously"""
    try:
        await asyncio.to_thread(os.remove, file_path)
        return True
    except (OSError, FileNotFoundError):
        return False


def get_path(hashed_name: str) -> Optional[str]:
    """Get full path for a hashed filename"""
    file_path = Path(settings.storage_path) / hashed_name
    return str(file_path) if file_path.exists() else None


def get_size(file_path: str) -> int:
    """Get file size in bytes"""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def check_size_limit(file: UploadFile) -> bool:
    """Check if file size is within configured limits"""
    if hasattr(file, 'size') and file.size:
        return file.size <= settings.max_file_size
    return True 


def file_exists(file_path: str) -> bool:
    """Check if file exists at given path"""
    return Path(file_path).exists()


async def get_file_stats(file_path: str) -> Optional[dict]:
    """Get file statistics asynchronously"""
    try:
        stat = await asyncio.to_thread(os.stat, file_path)
        return {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime
        }
    except OSError:
        return None