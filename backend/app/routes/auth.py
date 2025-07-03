# app/routes/auth.py
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ValidationError
from typing import Optional
from datetime import datetime, timedelta
import jwt
import bcrypt
import os
from bson import ObjectId

# Import models
from app.config import db

router = APIRouter()
security = HTTPBearer()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Collections
admin_collection = db["admins"]

class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    admin: AdminResponse

def hash_password(password: str) -> str:
    """Hash password menggunakan bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifikasi password"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Buat JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_admin_by_username(username: str):
    """Ambil admin berdasarkan username"""
    return admin_collection.find_one({"username": username})

def get_admin_by_email(email: str):
    """Ambil admin berdasarkan email"""
    return admin_collection.find_one({"email": email})

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency untuk mendapatkan admin yang sedang login"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin = get_admin_by_username(username)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return admin

@router.post("/register", response_model=AdminResponse)
async def register(admin_data: AdminCreate):
    """Register admin baru"""
    try:
        # Cek apakah username sudah ada
        if get_admin_by_username(admin_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Cek apakah email sudah ada
        if get_admin_by_email(admin_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = hash_password(admin_data.password)
        
        # Buat admin document
        admin_doc = {
            "username": admin_data.username,
            "email": admin_data.email,
            "password": hashed_password,
            "full_name": admin_data.full_name,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        }
        
        # Simpan ke database
        result = admin_collection.insert_one(admin_doc)
        
        if result.inserted_id:
            # Return admin data (tanpa password)
            admin_doc["_id"] = result.inserted_id
            return AdminResponse(
                id=str(admin_doc["_id"]),
                username=admin_doc["username"],
                email=admin_doc["email"],
                full_name=admin_doc["full_name"],
                is_active=admin_doc["is_active"],
                created_at=admin_doc["created_at"],
                last_login=admin_doc["last_login"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create admin"
            )
            
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(admin_data: AdminLogin):
    """Login admin"""
    try:
        # Cari admin berdasarkan username
        admin = get_admin_by_username(admin_data.username)
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Verifikasi password
        if not verify_password(admin_data.password, admin["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Cek apakah admin aktif
        if not admin.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account is disabled"
            )
        
        # Update last_login
        admin_collection.update_one(
            {"_id": admin["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        # Buat access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin["username"]}, 
            expires_delta=access_token_expires
        )
        
        # Return token dan admin data
        admin_response = AdminResponse(
            id=str(admin["_id"]),
            username=admin["username"],
            email=admin["email"],
            full_name=admin["full_name"],
            is_active=admin["is_active"],
            created_at=admin["created_at"],
            last_login=datetime.utcnow()
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            admin=admin_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/logout")
async def logout(current_admin: dict = Depends(get_current_admin)):
    """Logout admin"""
    # Karena JWT stateless, kita hanya perlu return success
    # Dalam implementasi production, Anda bisa menambahkan blacklist token
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=AdminResponse)
async def get_current_admin_info(current_admin: dict = Depends(get_current_admin)):
    """Get current admin info"""
    return AdminResponse(
        id=str(current_admin["_id"]),
        username=current_admin["username"],
        email=current_admin["email"],
        full_name=current_admin["full_name"],
        is_active=current_admin["is_active"],
        created_at=current_admin["created_at"],
        last_login=current_admin.get("last_login")
    )

@router.put("/profile", response_model=AdminResponse)
async def update_profile(
    admin_data: AdminCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update admin profile"""
    try:
        update_data = {
            "full_name": admin_data.full_name,
            "email": admin_data.email
        }
        
        # Update password jika diberikan
        if admin_data.password:
            update_data["password"] = hash_password(admin_data.password)
        
        # Update di database
        result = admin_collection.update_one(
            {"_id": current_admin["_id"]},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            # Ambil data terbaru
            updated_admin = admin_collection.find_one({"_id": current_admin["_id"]})
            return AdminResponse(
                id=str(updated_admin["_id"]),
                username=updated_admin["username"],
                email=updated_admin["email"],
                full_name=updated_admin["full_name"],
                is_active=updated_admin["is_active"],
                created_at=updated_admin["created_at"],
                last_login=updated_admin.get("last_login")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes made"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

# Legacy endpoint untuk backward compatibility
@router.post("/login-legacy")
def login_legacy(request: AdminLogin):
    """Legacy login endpoint untuk compatibility"""
    # Ambil username dan password dari .env sebagai fallback
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin@gmail.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
    
    if request.username == ADMIN_USERNAME and request.password == ADMIN_PASSWORD:
        return {"message": "Login berhasil"}
    raise HTTPException(status_code=401, detail="Username atau password salah")