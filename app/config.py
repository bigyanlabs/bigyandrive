# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./drive.db"
    
    secret_key: str = "xolo"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    storage_path: str = "./storage"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    
    max_login_attempts: int = 3
    blacklist_duration_hours: int = 24
    
    premium_token_expire_minutes: int = 60
    
    app_name: str = "ExposeCloud"
    debug: bool = False
    
    class Config:
        env_file = ".env"


settings = Settings()