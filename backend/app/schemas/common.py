
# app/schemas/common.py
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List

class APIResponse(BaseModel):
    """Standard API response schema"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None

class PaginationParams(BaseModel):
    """Standard pagination parameters"""
    limit: int = Field(10, ge=1, le=100)
    skip: int = Field(0, ge=0)

class FileUploadResponse(BaseModel):
    """Schema untuk response upload file"""
    success: bool
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    message: str
    errors: Optional[List[str]] = None

class OCRProcessResponse(BaseModel):
    """Schema untuk response OCR processing"""
    success: bool
    coordinates: Dict[str, Any]
    extracted_info: Optional[Dict[str, Any]] = None
    ocr_result: Optional[Dict[str, Any]] = None
    message: str
    errors: Optional[List[str]] = None