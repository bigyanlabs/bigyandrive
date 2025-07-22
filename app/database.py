# database.py
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings
import os


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  
    echo=settings.debug  
)


def create_db() -> None:
    """Create database and all tables"""
    os.makedirs(settings.storage_path, exist_ok=True)
    
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session