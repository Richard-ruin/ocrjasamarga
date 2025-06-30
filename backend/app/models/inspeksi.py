from pydantic import BaseModel, Field, field_validator, ConfigDict
from bson import ObjectId
from typing import Optional, List
from datetime import datetime
from app.utils.helpers import PyObjectId

class InspeksiData(BaseModel):
    """Model untuk data inspeksi individual"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "no": "1",
                "jalur": "Jalan Sarimanah",
                "latitude": "6°52'35,698\"S",
                "longitude": "107°34'37,321\"E",
                "kondisi": "baik",
                "keterangan": "Kondisi jalan baik, tidak ada kerusakan",
                "image_path": "/uploads/images/img_001.jpg"
            }
        }
    )
    
    no: str = Field(..., description="Nomor urut")
    jalur: str = Field(..., description="Nama jalur/ruas")
    latitude: str = Field(..., description="Koordinat lintang (DMS format)")
    longitude: str = Field(..., description="Koordinat bujur (DMS format)")
    kondisi: str = Field(..., description="Kondisi jalan")  # baik, sedang, buruk
    keterangan: str = Field(..., description="Keterangan kondisi")
    image_path: Optional[str] = Field(None, description="Path gambar dokumentasi")
    image_data: Optional[str] = Field(None, description="Base64 data gambar")
    ocr_raw_text: Optional[str] = Field(None, description="Raw text dari OCR")
    
    @field_validator('kondisi')
    @classmethod
    def validate_kondisi(cls, v):
        if v.lower() not in ['baik', 'sedang', 'buruk']:
            raise ValueError('Kondisi harus salah satu dari: baik, sedang, buruk')
        return v.lower()

class Inspeksi(BaseModel):
    """Model untuk inspeksi lapangan"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "title": "Inspeksi Tol Jakarta-Cikampek KM 10-15",
                "location": "Jakarta-Cikampek, Jawa Barat",
                "session_id": "session_123456",
                "data": [
                    {
                        "no": "1",
                        "jalur": "Jalan Sarimanah",
                        "latitude": "6°52'35,698\"S",
                        "longitude": "107°34'37,321\"E",
                        "kondisi": "baik",
                        "keterangan": "Kondisi jalan baik",
                        "image_path": "/uploads/images/img_001.jpg"
                    }
                ],
                "status": "draft",
                "total_items": 1
            }
        }
    )
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="ID user inspector")
    jadwal_id: Optional[PyObjectId] = Field(None, description="ID jadwal terkait")
    session_id: str = Field(..., description="Session ID untuk cache")
    title: str = Field(..., description="Judul inspeksi")
    location: str = Field(..., description="Lokasi inspeksi")
    inspection_date: datetime = Field(default_factory=datetime.utcnow, description="Tanggal inspeksi")
    data: List[InspeksiData] = Field(default=[], description="Data inspeksi")
    excel_path: Optional[str] = Field(None, description="Path file Excel yang digenerate")
    status: str = Field(default="draft", description="Status inspeksi")  # draft, completed
    total_items: int = Field(default=0, description="Total item yang diinspeksi")
    notes: Optional[str] = Field(None, description="Catatan tambahan")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class InspeksiResponse(BaseModel):
    """Response model untuk inspeksi"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "jadwal_id": "507f1f77bcf86cd799439013",
                "session_id": "session_123456",
                "title": "Inspeksi Tol Jakarta-Cikampek KM 10-15",
                "location": "Jakarta-Cikampek, Jawa Barat",
                "inspection_date": "2024-07-02T08:00:00",
                "data": [],
                "excel_path": None,
                "status": "draft",
                "total_items": 0,
                "notes": None,
                "created_at": "2024-07-02T08:00:00",
                "updated_at": "2024-07-02T08:00:00"
            }
        }
    )
    
    id: str
    user_id: str
    jadwal_id: Optional[str]
    session_id: str
    title: str
    location: str
    inspection_date: datetime
    data: List[InspeksiData]
    excel_path: Optional[str]
    status: str
    total_items: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime