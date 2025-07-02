from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date, time
from bson import ObjectId

class JadwalCreate(BaseModel):
    nama_inspektur: str = Field(..., min_length=2, max_length=100)
    tanggal: date
    waktu: time
    alamat: str = Field(..., min_length=5, max_length=500)
    keterangan: Optional[str] = None
    status: str = Field(default="scheduled")  # scheduled, completed, cancelled

class JadwalUpdate(BaseModel):
    nama_inspektur: Optional[str] = None
    tanggal: Optional[date] = None
    waktu: Optional[time] = None
    alamat: Optional[str] = None
    keterangan: Optional[str] = None
    status: Optional[str] = None

class JadwalResponse(BaseModel):
    id: str = Field(alias="_id")
    nama_inspektur: str
    tanggal: date
    waktu: time
    alamat: str
    keterangan: Optional[str] = None
    status: str
    admin_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat()
        }

class JadwalInDB(BaseModel):
    nama_inspektur: str
    tanggal: date
    waktu: time
    alamat: str
    keterangan: Optional[str] = None
    status: str
    admin_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None