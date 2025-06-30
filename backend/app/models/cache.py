from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from app.utils.helpers import PyObjectId
from app.models.inspeksi import InspeksiData

class Cache(BaseModel):
    """Model untuk cache data inspeksi"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "session_id": "session_123456789",
                "cache_type": "inspeksi",
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
                "metadata": {
                    "total_items": 1,
                    "last_ocr": "2024-07-02T08:00:00"
                }
            }
        }
    )
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="ID user pemilik cache")
    session_id: str = Field(..., description="Session ID unik")
    cache_type: str = Field(default="inspeksi", description="Tipe cache")
    data: List[InspeksiData] = Field(default=[], description="Data yang di-cache")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata cache")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=24),
        description="Waktu cache expire"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CacheResponse(BaseModel):
    """Response model untuk cache"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "session_id": "session_123456789",
                "cache_type": "inspeksi",
                "data": [],
                "metadata": {"total_items": 0},
                "expires_at": "2024-07-03T08:00:00",
                "created_at": "2024-07-02T08:00:00",
                "updated_at": "2024-07-02T08:00:00"
            }
        }
    )
    
    id: str
    user_id: str
    session_id: str
    cache_type: str
    data: List[InspeksiData]
    metadata: Optional[Dict[str, Any]]
    expires_at: datetime
    created_at: datetime
    updated_at: datetime