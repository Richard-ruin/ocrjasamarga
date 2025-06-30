from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class JadwalCreate(BaseModel):
    """Schema untuk membuat jadwal baru"""
    title: str = Field(..., min_length=5, max_length=200, description="Judul jadwal inspeksi")
    description: Optional[str] = Field(None, max_length=500, description="Deskripsi jadwal")
    waktu: datetime = Field(..., description="Waktu inspeksi")
    alamat: str = Field(..., min_length=10, max_length=300, description="Alamat lokasi inspeksi")
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude lokasi")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="Longitude lokasi")
    notes: Optional[str] = Field(None, max_length=1000, description="Catatan tambahan")
    
    @validator('waktu')
    def validate_waktu(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('Waktu inspeksi harus di masa depan')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "title": "Inspeksi Ruas Tol Jakarta-Cikampek KM 10",
                "description": "Inspeksi rutin kondisi jalan tol",
                "waktu": "2024-07-03T08:00:00",
                "alamat": "Jalan Tol Jakarta-Cikampek KM 10, Bekasi, Jawa Barat",
                "location_lat": -6.2088,
                "location_lng": 106.8456,
                "notes": "Bawa peralatan dokumentasi lengkap"
            }
        }

class JadwalUpdate(BaseModel):
    """Schema untuk update jadwal"""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    waktu: Optional[datetime] = None
    alamat: Optional[str] = Field(None, min_length=10, max_length=300)
    status: Optional[str] = None
    location_lat: Optional[float] = Field(None, ge=-90, le=90)
    location_lng: Optional[float] = Field(None, ge=-180, le=180)
    notes: Optional[str] = Field(None, max_length=1000)
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            allowed_status = ['scheduled', 'completed', 'cancelled']
            if v not in allowed_status:
                raise ValueError(f'Status harus salah satu dari: {", ".join(allowed_status)}')
        return v
    
    @validator('waktu')
    def validate_waktu(cls, v):
        if v is not None and v <= datetime.utcnow():
            raise ValueError('Waktu inspeksi harus di masa depan')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "title": "Inspeksi Ruas Tol Jakarta-Cikampek KM 10 (Updated)",
                "status": "completed",
                "notes": "Inspeksi telah selesai dilakukan"
            }
        }

class JadwalFilter(BaseModel):
    """Schema untuk filter jadwal"""
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None
    limit: Optional[int] = Field(10, ge=1, le=100)
    skip: Optional[int] = Field(0, ge=0)
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            allowed_status = ['scheduled', 'completed', 'cancelled']
            if v not in allowed_status:
                raise ValueError(f'Status harus salah satu dari: {", ".join(allowed_status)}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "status": "scheduled",
                "start_date": "2024-07-01T00:00:00",
                "end_date": "2024-07-31T23:59:59",
                "search": "jakarta",
                "limit": 10,
                "skip": 0
            }
        }

class JadwalListResponse(BaseModel):
    """Schema untuk response list jadwal"""
    total: int
    items: List[dict]
    limit: int
    skip: int
    has_more: bool
    
    class Config:
        schema_extra = {
            "example": {
                "total": 25,
                "items": [],
                "limit": 10,
                "skip": 0,
                "has_more": True
            }
        }