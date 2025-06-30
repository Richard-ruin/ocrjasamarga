# app/schemas/inspeksi.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.models.inspeksi import InspeksiData

class InspeksiCreate(BaseModel):
    """Schema untuk membuat inspeksi baru"""
    title: str = Field(..., min_length=5, max_length=200)
    location: str = Field(..., min_length=5, max_length=200)
    jadwal_id: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    
    class Config:
        schema_extra = {
            "example": {
                "title": "Inspeksi Tol Jakarta-Cikampek KM 10-15",
                "location": "Jakarta-Cikampek, Jawa Barat",
                "jadwal_id": "507f1f77bcf86cd799439011",
                "notes": "Inspeksi kondisi jalan tol"
            }
        }

class InspeksiDataCreate(BaseModel):
    """Schema untuk data inspeksi individual"""
    no: str = Field(..., description="Nomor urut")
    jalur: str = Field(..., description="Nama jalur")
    latitude: str = Field(..., description="Koordinat lintang DMS")
    longitude: str = Field(..., description="Koordinat bujur DMS")
    kondisi: str = Field(..., description="Kondisi jalan")
    keterangan: str = Field(..., description="Keterangan kondisi")
    image_data: Optional[str] = None
    image_path: Optional[str] = None
    
    @validator('kondisi')
    def validate_kondisi(cls, v):
        if v.lower() not in ['baik', 'sedang', 'buruk']:
            raise ValueError('Kondisi harus: baik, sedang, atau buruk')
        return v.lower()

class CacheAddRequest(BaseModel):
    """Schema untuk menambah data ke cache"""
    session_id: str
    data: InspeksiDataCreate

class ExcelGenerateRequest(BaseModel):
    """Schema untuk generate Excel"""
    session_id: str
    title: str = "Inspeksi Lapangan"

# app/schemas/history.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class HistoryFilter(BaseModel):
    """Schema untuk filter history"""
    action: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    skip: int = Field(0, ge=0)

class HistoryListResponse(BaseModel):
    """Schema untuk response list history"""
    total: int
    items: List[Dict[str, Any]]
    limit: int
    skip: int
    has_more: bool
