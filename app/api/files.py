# files.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import Annotated
import mimetypes
import os

from app.database import get_session
from app.models import File as FileModel, FileStatus, User
from app.schemas import FileUpload, FileResponse, FileList, FileDelete, FileStats
from app.core import (
    save_file,
    remove_file,
    get_path,
    get_size,
    check_size_limit,
    validate_filename,
    validate_mime_type
)
from app.api.auth import get_current_user

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    file: UploadFile = File(...)
) -> FileResponse:
    """Upload a file"""
    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    if not validate_filename(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )
    
    if not check_size_limit(file):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum limit"
        )
    
    mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    
    if not validate_mime_type(mime_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type"
        )
    
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user session"
        )
    
    file_path: str = ""
    try:
        hashed_name, file_path = await save_file(file, file.filename)
        file_size = get_size(file_path)
        
        db_file = FileModel(
            owner_id=current_user.id,
            original_name=file.filename,
            hashed_name=hashed_name,
            file_size=file_size,
            mime_type=mime_type,
            upload_path=file_path,
            status=FileStatus.UPLOADED
        )
        
        session.add(db_file)
        session.commit()
        session.refresh(db_file)
        
        if db_file.id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save file record"
            )
        
        return FileResponse(
            id=db_file.id,
            original_name=db_file.original_name,
            file_size=db_file.file_size,
            mime_type=db_file.mime_type,
            status=db_file.status.value,
            created_at=db_file.created_at
        )
        
    except Exception as e:
        if file_path:
            await remove_file(file_path)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )


@router.get("/list", response_model=FileList)
async def list_files(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    offset: int = 0
) -> FileList:
    """Get user's files with pagination"""
    
    query = select(FileModel).where(
        FileModel.owner_id == current_user.id,
        FileModel.status != FileStatus.DELETED
    ).offset(offset).limit(limit)
    
    files = session.exec(query).all()
    
    count_query = select(FileModel).where(
        FileModel.owner_id == current_user.id,
        FileModel.status != FileStatus.DELETED
    )
    total = len(session.exec(count_query).all())
    
    file_responses = [
        FileResponse(
            id=f.id if f.id is not None else 0,
            original_name=f.original_name,
            file_size=f.file_size,
            mime_type=f.mime_type,
            status=f.status.value,
            created_at=f.created_at
        ) for f in files
    ]
    
    return FileList(files=file_responses, total=total)


@router.delete("/delete", response_model=dict)
async def delete_file(
    file_data: FileDelete,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> dict:
    """Delete a file"""
    
    file_record = session.exec(
        select(FileModel).where(
            FileModel.id == file_data.file_id,
            FileModel.owner_id == current_user.id
        )
    ).first()
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file_record.upload_path:
        await remove_file(file_record.upload_path)
    
    file_record.status = FileStatus.DELETED
    session.add(file_record)
    session.commit()
    
    return {"message": "File deleted successfully"}


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)]
) -> StreamingResponse:
    """Download a file"""
    
    file_record = session.exec(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.owner_id == current_user.id,
            FileModel.status != FileStatus.DELETED
        )
    ).first()
    
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