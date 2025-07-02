from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class InspeksiDataItem(BaseModel):
    no: int
    jalur: str
    latitude: str
    longitude: str
    kondisi: str = Field(..., pattern="^(baik|sedang|buruk)$")
    keterangan: Optional[str] = None
    image: Optional[str] = None  # Base64 or file path
    image_filename: Optional[str] = None

class InspeksiCreate(BaseModel):
    jadwal_id: Optional[str] = None
    data: List[InspeksiDataItem] = []
    status: str = Field(default="draft")  # draft, generated, saved

class InspeksiUpdate(BaseModel):
    jadwal_id: Optional[str] = None
    data: Optional[List[InspeksiDataItem]] = None
    status: Optional[str] = None

class InspeksiResponse(BaseModel):
    id: str = Field(alias="_id")
    jadwal_id: Optional[str] = None
    data: List[InspeksiDataItem]
    status: str
    admin_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    generated_at: Optional[datetime] = None
    saved_at: Optional[datetime] = None
    excel_file_path: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class InspeksiInDB(BaseModel):
    jadwal_id: Optional[str] = None
    data: List[Dict[str, Any]] = []
    status: str
    admin_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    generated_at: Optional[datetime] = None
    saved_at: Optional[datetime] = None
    excel_file_path: Optional[str] = None

class OCRResult(BaseModel):
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    extracted_text: str
    confidence: float
    success: bool
    error_message: Optional[str] = None

class GenerateRequest(BaseModel):
    inspeksi_id: str
    image_data: str  # Base64 encoded image
    item_index: int  # Index of the data item to update