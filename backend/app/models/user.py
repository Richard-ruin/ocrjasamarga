from pydantic import BaseModel, Field, EmailStr, ConfigDict
from bson import ObjectId
from typing import Optional
from datetime import datetime
from app.utils.helpers import PyObjectId

class User(BaseModel):
    """User model for MongoDB"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "username": "admin01",
                "email": "admin@jasamarga.com",
                "password": "password123",
                "full_name": "Admin Jasa Marga",
                "role": "admin"
            }
        }
    )
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = Field(None, max_length=100)
    role: str = Field(default="admin")  # admin, inspector
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

class UserInDB(User):
    """User model with hashed password"""
    hashed_password: str
    
class UserResponse(BaseModel):
    """User response model (without password)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "username": "admin01",
                "email": "admin@jasamarga.com",
                "full_name": "Admin Jasa Marga",
                "role": "admin",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
                "last_login": "2024-01-01T12:00:00"
            }
        }
    )
    
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]