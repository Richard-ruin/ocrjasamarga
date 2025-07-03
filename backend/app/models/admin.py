from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class AdminCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AdminUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class AdminInDB(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: str
    password: str
    full_name: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminRegister(BaseModel):
    username: str
    email: str
    password: str
    full_name: str

class AdminResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None