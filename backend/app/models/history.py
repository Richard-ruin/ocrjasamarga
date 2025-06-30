from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from typing import Optional, Dict, Any
from datetime import datetime
from app.utils.helpers import PyObjectId

class History(BaseModel):
    """Model untuk history/log aktivitas"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "action": "generate_excel",
                "description": "Generate Excel file untuk inspeksi lapangan",
                "data": {
                    "total_items": 5,
                    "location": "Jakarta-Cikampek KM 10-15",
                    "filename": "output-20240702-080000.xlsx"
                },
                "excel_path": "/uploads/generated/output-20240702-080000.xlsx",
                "metadata": {
                    "file_size": 2048576,
                    "processing_time": 3.5
                }
            }
        }
    )
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="ID user yang melakukan aksi")
    inspeksi_id: Optional[PyObjectId] = Field(None, description="ID inspeksi terkait")
    action: str = Field(..., description="Jenis aksi yang dilakukan")
    description: str = Field(..., description="Deskripsi aksi")
    data: Optional[Dict[str, Any]] = Field(None, description="Data tambahan")
    excel_path: Optional[str] = Field(None, description="Path file Excel jika ada")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata tambahan")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class HistoryResponse(BaseModel):
    """Response model untuk history"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "inspeksi_id": "507f1f77bcf86cd799439013",
                "action": "generate_excel",
                "description": "Generate Excel file untuk inspeksi lapangan",
                "data": {
                    "total_items": 5,
                    "location": "Jakarta-Cikampek KM 10-15",
                    "filename": "output-20240702-080000.xlsx"
                },
                "excel_path": "/uploads/generated/output-20240702-080000.xlsx",
                "metadata": {
                    "file_size": 2048576,
                    "processing_time": 3.5
                },
                "created_at": "2024-07-02T08:00:00"
            }
        }
    )
    
    id: str
    user_id: str
    inspeksi_id: Optional[str]
    action: str
    description: str
    data: Optional[Dict[str, Any]]
    excel_path: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime