from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime

class UserRegister(BaseModel):
    """Schema for user registration"""
    model_config = ConfigDict(
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
    
    username: str = Field(..., min_length=3, max_length=50, description="Username unik")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, description="Password minimal 6 karakter")
    full_name: Optional[str] = Field(None, max_length=100, description="Nama lengkap")
    role: Optional[str] = Field("admin", description="Role user")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v.lower()
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['admin', 'inspector']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class UserLogin(BaseModel):
    """Schema for user login"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin01",
                "password": "password123"
            }
        }
    )
    
    username: str = Field(..., description="Username atau email")
    password: str = Field(..., description="Password")

class UserUpdate(BaseModel):
    """Schema for user update"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Admin Jasa Marga Updated",
                "email": "admin.updated@jasamarga.com",
                "role": "admin",
                "is_active": True
            }
        }
    )
    
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = ['admin', 'inspector']
            if v not in allowed_roles:
                raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class PasswordChange(BaseModel):
    """Schema for password change"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "oldpassword123",
                "new_password": "newpassword123"
            }
        }
    )
    
    current_password: str = Field(..., description="Password saat ini")
    new_password: str = Field(..., min_length=6, description="Password baru minimal 6 karakter")

class TokenResponse(BaseModel):
    """Schema for token response"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "id": "507f1f77bcf86cd799439011",
                    "username": "admin01",
                    "email": "admin@jasamarga.com",
                    "role": "admin"
                }
            }
        }
    )
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class UserStats(BaseModel):
    """Schema for user statistics"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_inspeksi": 15,
                "total_jadwal": 8,
                "completed_inspeksi": 12,
                "pending_jadwal": 3,
                "last_activity": "2024-07-02T08:00:00"
            }
        }
    )
    
    total_inspeksi: int = 0
    total_jadwal: int = 0
    completed_inspeksi: int = 0
    pending_jadwal: int = 0
    last_activity: Optional[datetime] = None