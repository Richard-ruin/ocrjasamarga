# app/routes/auth.py - Updated with role-based system
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ValidationError
from typing import Optional, List
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
    role: str = "petugas"  # admin atau petugas

class AdminUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class AdminListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    data: List[AdminResponse]

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

def get_admin_by_id(admin_id: str):
    """Ambil admin berdasarkan ID"""
    try:
        return admin_collection.find_one({"_id": ObjectId(admin_id)})
    except:
        return None

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

async def get_admin_only(current_admin: dict = Depends(get_current_admin)):
    """Dependency untuk memastikan hanya admin yang bisa akses"""
    if current_admin.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can access this resource"
        )
    return current_admin

@router.post("/register", response_model=AdminResponse)
async def register(admin_data: AdminCreate):
    """Register admin/petugas baru"""
    try:
        # Validasi role
        if admin_data.role not in ["admin", "petugas"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be either 'admin' or 'petugas'"
            )
        
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
            "role": admin_data.role,
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
                role=admin_doc["role"],
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
    """Login admin/petugas"""
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
                detail="Account is disabled"
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
            role=admin.get("role", "petugas"),  # Default ke petugas untuk backward compatibility
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
    """Logout admin/petugas"""
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=AdminResponse)
async def get_current_admin_info(current_admin: dict = Depends(get_current_admin)):
    """Get current admin/petugas info"""
    return AdminResponse(
        id=str(current_admin["_id"]),
        username=current_admin["username"],
        email=current_admin["email"],
        full_name=current_admin["full_name"],
        role=current_admin.get("role", "petugas"),
        is_active=current_admin["is_active"],
        created_at=current_admin["created_at"],
        last_login=current_admin.get("last_login")
    )

@router.put("/profile", response_model=AdminResponse)
async def update_profile(
    admin_data: AdminUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update profile (tanpa role untuk security)"""
    try:
        update_data = {}
        
        if admin_data.full_name:
            update_data["full_name"] = admin_data.full_name
        if admin_data.email:
            # Cek email tidak digunakan user lain
            existing = get_admin_by_email(admin_data.email)
            if existing and str(existing["_id"]) != str(current_admin["_id"]):
                raise HTTPException(400, "Email already used")
            update_data["email"] = admin_data.email
        if admin_data.password:
            update_data["password"] = hash_password(admin_data.password)
        
        if not update_data:
            raise HTTPException(400, "No data to update")
        
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
                role=updated_admin.get("role", "petugas"),
                is_active=updated_admin["is_active"],
                created_at=updated_admin["created_at"],
                last_login=updated_admin.get("last_login")
            )
        else:
            raise HTTPException(400, "No changes made")
            
    except Exception as e:
        raise HTTPException(500, f"Failed to update profile: {str(e)}")

# ===== ADMIN-ONLY USER MANAGEMENT ENDPOINTS =====

@router.get("/users", response_model=AdminListResponse)
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    role_filter: Optional[str] = Query(None),
    current_admin: dict = Depends(get_admin_only)
):
    """Get list of users - ADMIN ONLY"""
    try:
        # Build filter
        filter_query = {}
        if search:
            filter_query["$or"] = [
                {"username": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"full_name": {"$regex": search, "$options": "i"}}
            ]
        if role_filter and role_filter in ["admin", "petugas"]:
            filter_query["role"] = role_filter
        
        # Hitung total
        total = admin_collection.count_documents(filter_query)
        
        # Hitung pagination
        skip = (page - 1) * per_page
        total_pages = (total + per_page - 1) // per_page
        
        # Ambil data
        cursor = admin_collection.find(filter_query).skip(skip).limit(per_page).sort("created_at", -1)
        users = []
        
        for user in cursor:
            users.append(AdminResponse(
                id=str(user["_id"]),
                username=user["username"],
                email=user["email"],
                full_name=user["full_name"],
                role=user.get("role", "petugas"),
                is_active=user["is_active"],
                created_at=user["created_at"],
                last_login=user.get("last_login")
            ))
        
        return AdminListResponse(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=users
        )
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get users: {str(e)}")

@router.get("/users/{user_id}", response_model=AdminResponse)
async def get_user(
    user_id: str,
    current_admin: dict = Depends(get_admin_only)
):
    """Get user by ID - ADMIN ONLY"""
    user = get_admin_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    return AdminResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        role=user.get("role", "petugas"),
        is_active=user["is_active"],
        created_at=user["created_at"],
        last_login=user.get("last_login")
    )

@router.post("/users", response_model=AdminResponse)
async def create_user(
    user_data: AdminCreate,
    current_admin: dict = Depends(get_admin_only)
):
    """Create new user - ADMIN ONLY"""
    try:
        # Validasi role
        if user_data.role not in ["admin", "petugas"]:
            raise HTTPException(400, "Role must be 'admin' or 'petugas'")
        
        # Cek username dan email
        if get_admin_by_username(user_data.username):
            raise HTTPException(400, "Username already exists")
        if get_admin_by_email(user_data.email):
            raise HTTPException(400, "Email already exists")
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Buat user document
        user_doc = {
            "username": user_data.username,
            "email": user_data.email,
            "password": hashed_password,
            "full_name": user_data.full_name,
            "role": user_data.role,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        }
        
        # Simpan ke database
        result = admin_collection.insert_one(user_doc)
        
        if result.inserted_id:
            user_doc["_id"] = result.inserted_id
            return AdminResponse(
                id=str(user_doc["_id"]),
                username=user_doc["username"],
                email=user_doc["email"],
                full_name=user_doc["full_name"],
                role=user_doc["role"],
                is_active=user_doc["is_active"],
                created_at=user_doc["created_at"],
                last_login=user_doc["last_login"]
            )
        else:
            raise HTTPException(500, "Failed to create user")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to create user: {str(e)}")

@router.put("/users/{user_id}", response_model=AdminResponse)
async def update_user(
    user_id: str,
    user_data: AdminUpdate,
    current_admin: dict = Depends(get_admin_only)
):
    """Update user - ADMIN ONLY"""
    try:
        # Cek apakah user ada
        user = get_admin_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        
        # Prepare update data
        update_data = {}
        
        if user_data.username:
            existing_user = get_admin_by_username(user_data.username)
            if existing_user and str(existing_user["_id"]) != user_id:
                raise HTTPException(400, "Username already exists")
            update_data["username"] = user_data.username
        
        if user_data.email:
            existing_user = get_admin_by_email(user_data.email)
            if existing_user and str(existing_user["_id"]) != user_id:
                raise HTTPException(400, "Email already exists")
            update_data["email"] = user_data.email
        
        if user_data.full_name:
            update_data["full_name"] = user_data.full_name
        
        if user_data.password:
            update_data["password"] = hash_password(user_data.password)
        
        if user_data.is_active is not None:
            update_data["is_active"] = user_data.is_active
        
        if user_data.role and user_data.role in ["admin", "petugas"]:
            update_data["role"] = user_data.role
        
        if not update_data:
            raise HTTPException(400, "No data to update")
        
        # Update di database
        result = admin_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            # Ambil data terbaru
            updated_user = admin_collection.find_one({"_id": ObjectId(user_id)})
            return AdminResponse(
                id=str(updated_user["_id"]),
                username=updated_user["username"],
                email=updated_user["email"],
                full_name=updated_user["full_name"],
                role=updated_user.get("role", "petugas"),
                is_active=updated_user["is_active"],
                created_at=updated_user["created_at"],
                last_login=updated_user.get("last_login")
            )
        else:
            raise HTTPException(400, "No changes made")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to update user: {str(e)}")

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_admin: dict = Depends(get_admin_only)
):
    """Delete user - ADMIN ONLY"""
    try:
        # Cek apakah user ada
        user = get_admin_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        
        # Tidak bisa menghapus diri sendiri
        if str(user["_id"]) == str(current_admin["_id"]):
            raise HTTPException(400, "Cannot delete yourself")
        
        # Hapus dari database
        result = admin_collection.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count > 0:
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(500, "Failed to delete user")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to delete user: {str(e)}")

@router.put("/users/{user_id}/status")
async def toggle_user_status(
    user_id: str,
    current_admin: dict = Depends(get_admin_only)
):
    """Toggle user active status - ADMIN ONLY"""
    try:
        # Cek apakah user ada
        user = get_admin_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        
        # Tidak bisa menonaktifkan diri sendiri
        if str(user["_id"]) == str(current_admin["_id"]):
            raise HTTPException(400, "Cannot deactivate yourself")
        
        # Toggle status
        new_status = not user.get("is_active", True)
        
        # Update di database
        result = admin_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": new_status}}
        )
        
        if result.modified_count > 0:
            return {
                "message": f"User {'activated' if new_status else 'deactivated'} successfully",
                "is_active": new_status
            }
        else:
            raise HTTPException(500, "Failed to update user status")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to update user status: {str(e)}")

# Endpoint untuk migrasi role existing users
@router.post("/migrate-roles")
async def migrate_existing_users_roles(current_admin: dict = Depends(get_admin_only)):
    """Migrate existing users to have roles - ADMIN ONLY"""
    try:
        # Update semua user yang belum punya role menjadi 'petugas'
        result = admin_collection.update_many(
            {"role": {"$exists": False}},
            {"$set": {"role": "petugas"}}
        )
        
        return {
            "message": "Role migration completed",
            "updated_count": result.modified_count
        }
        
    except Exception as e:
        raise HTTPException(500, f"Migration failed: {str(e)}")