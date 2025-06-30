from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os

class Settings(BaseSettings):
    # Database
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "ocr_jasamarga"
    
    # JWT
    secret_key: str = "your-super-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Upload
    max_file_size: int = 10485760  # 10MB
    upload_dir: str = "uploads"
    allowed_extensions_str: str = Field("jpg,jpeg,png,bmp,tiff", alias="ALLOWED_EXTENSIONS")
    
    # OCR Settings
    ocr_language: str = "id,en"
    ocr_gpu: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # App Settings
    app_name: str = "OCR Jasa Marga"
    app_version: str = "1.0.0"
    debug: bool = True

    @property
    def allowed_extensions(self) -> List[str]:
        return [ext.strip() for ext in self.allowed_extensions_str.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Ensure upload directories exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(f"{settings.upload_dir}/images", exist_ok=True)
os.makedirs(f"{settings.upload_dir}/generated", exist_ok=True)
