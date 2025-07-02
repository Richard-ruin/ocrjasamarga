from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

class HistoryCreate(BaseModel):
    action_type: str  # "generate", "save", "delete"
    inspeksi_id: str
    jadwal_id: Optional[str] = None
    data_snapshot: Optional[Dict[str, Any]] = None
    excel_file_path: Optional[str] = None
    description: Optional[str] = None

class HistoryResponse(BaseModel):
    id: str = Field(alias="_id")
    action_type: str
    inspeksi_id: str
    jadwal_id: Optional[str] = None
    data_snapshot: Optional[Dict[str, Any]] = None
    excel_file_path: Optional[str] = None
    description: Optional[str] = None
    admin_id: str
    created_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class HistoryInDB(BaseModel):
    action_type: str
    inspeksi_id: str
    jadwal_id: Optional[str] = None
    data_snapshot: Optional[Dict[str, Any]] = None
    excel_file_path: Optional[str] = None
    description: Optional[str] = None
    admin_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class HistoryFilter(BaseModel):
    action_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=50, le=100)
    skip: int = Field(default=0, ge=0)