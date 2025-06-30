from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from typing import Optional
from datetime import datetime
from app.utils.helpers import PyObjectId

class Jadwal(BaseModel):
    """Jadwal inspeksi model"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "title": "Inspeksi Ruas Tol Jakarta-Cikampek KM 10",
                "description": "Inspeksi rutin kondisi jalan tol",
                "waktu": "2024-07-02T08:00:00",
                "alamat": "Jalan Tol Jakarta-Cikampek KM 10, Bekasi, Jawa Barat",
                "status": "scheduled",
                "location_lat": -6.2088,
                "location_lng": 106.8456,
                "notes": "Bawa peralatan dokumentasi lengkap"
            }
        }
    )
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="ID user yang membuat jadwal")
    title: str = Field(..., min_length=5, max_length=200, description="Judul jadwal")
    description: Optional[str] = Field(None, max_length=500, description="Deskripsi jadwal")
    waktu: datetime = Field(..., description="Waktu inspeksi")
    alamat: str = Field(..., min_length=10, max_length=300, description="Alamat inspeksi")
    status: str = Field(default="scheduled", description="Status jadwal")  # scheduled, completed, cancelled
    location_lat: Optional[float] = Field(None, description="Latitude lokasi")
    location_lng: Optional[float] = Field(None, description="Longitude lokasi")
    notes: Optional[str] = Field(None, max_length=1000, description="Catatan tambahan")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class JadwalResponse(BaseModel):
    """Response model untuk jadwal"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "title": "Inspeksi Ruas Tol Jakarta-Cikampek KM 10",
                "description": "Inspeksi rutin kondisi jalan tol",
                "waktu": "2024-07-02T08:00:00",
                "alamat": "Jalan Tol Jakarta-Cikampek KM 10, Bekasi, Jawa Barat",
                "status": "scheduled",
                "location_lat": -6.2088,
                "location_lng": 106.8456,
                "notes": "Bawa peralatan dokumentasi lengkap",
                "created_at": "2024-07-01T10:00:00",
                "updated_at": "2024-07-01T10:00:00"
            }
        }
    )
    
    id: str
    user_id: str
    title: str
    description: Optional[str]
    waktu: datetime
    alamat: str
    status: str
    location_lat: Optional[float]
    location_lng: Optional[float]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime