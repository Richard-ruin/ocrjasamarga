from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
import logging

from app.database import get_database
from app.services.auth_service import auth_service
from app.schemas.user import UserRegister, UserLogin, UserUpdate, PasswordChange, TokenResponse, UserStats
from app.models.user import User, UserResponse
from app.utils.dependencies import get_current_user, get_current_admin_user
from app.utils.helpers import PyObjectId
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Register new user"""
    try:
        # Check if username already exists
        existing_user = await db.users.find_one({"username": user_data.username})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = await db.users.find_one({"email": user_data.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password strength
        password_validation = auth_service.validate_password_strength(user_data.password)
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "errors": password_validation["errors"]
                }
            )
        
        # Hash password
        hashed_password = auth_service.get_password_hash(user_data.password)
        
        # Create user document
        user_doc = {
            "_id": PyObjectId(),
            "username": user_data.username,
            "email": user_data.email,
            "hashed_password": hashed_password,
            "full_name": user_data.full_name,
            "role": user_data.role,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_login": None
        }
        
        # Insert user
        result = await db.users.insert_one(user_doc)
        
        logger.info(f"New user registered: {user_data.username}")
        
        return {
            "message": "User registered successfully",
            "user_id": str(result.inserted_id),
            "username": user_data.username,
            "email": user_data.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """User login"""
    try:
        # Find user by username or email
        user_doc = await db.users.find_one({
            "$or": [
                {"username": login_data.username},
                {"email": login_data.username}
            ]
        })
        
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Check if user is active
        if not user_doc.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Verify password
        if not auth_service.verify_password(login_data.password, user_doc["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create token data
        token_data = auth_service.create_user_token_data(
            user_id=str(user_doc["_id"]),
            username=user_doc["username"],
            email=user_doc["email"],
            role=user_doc["role"]
        )
        
        # Generate access token
        access_token = auth_service.create_access_token(data=token_data)
        
        # Update last login
        await db.users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        logger.info(f"User logged in: {user_doc['username']}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            user={
                "id": str(user_doc["_id"]),
                "username": user_doc["username"],
                "email": user_doc["email"],
                "full_name": user_doc.get("full_name"),
                "role": user_doc["role"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get current user information"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update current user profile"""
    try:
        update_data = {}
        
        # Build update data
        if user_update.full_name is not None:
            update_data["full_name"] = user_update.full_name
        
        if user_update.email is not None:
            # Check if email is already taken by another user
            existing_email = await db.users.find_one({
                "email": user_update.email,
                "_id": {"$ne": current_user.id}
            })
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already taken"
                )
            update_data["email"] = user_update.email
        
        # Only admin can change role and active status
        if current_user.role == "admin":
            if user_update.role is not None:
                update_data["role"] = user_update.role
            if user_update.is_active is not None:
                update_data["is_active"] = user_update.is_active
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Update user
        result = await db.users.update_one(
            {"_id": current_user.id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get updated user
        updated_user = await db.users.find_one({"_id": current_user.id})
        
        return UserResponse(
            id=str(updated_user["_id"]),
            username=updated_user["username"],
            email=updated_user["email"],
            full_name=updated_user.get("full_name"),
            role=updated_user["role"],
            is_active=updated_user["is_active"],
            created_at=updated_user["created_at"],
            updated_at=updated_user["updated_at"],
            last_login=updated_user.get("last_login")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Update failed"
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Change user password"""
    try:
        # Get user document
        user_doc = await db.users.find_one({"_id": current_user.id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not auth_service.verify_password(password_data.current_password, user_doc["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )
        
        # Validate new password
        password_validation = auth_service.validate_password_strength(password_data.new_password)
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "New password does not meet requirements",
                    "errors": password_validation["errors"]
                }
            )
        
        # Hash new password
        new_hashed_password = auth_service.get_password_hash(password_data.new_password)
        
        # Update password
        await db.users.update_one(
            {"_id": current_user.id},
            {"$set": {
                "hashed_password": new_hashed_password,
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"Password changed for user: {current_user.username}")
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user statistics"""
    try:
        # Get counts
        total_jadwal = await db.jadwal.count_documents({"user_id": current_user.id})
        total_inspeksi = await db.inspeksi.count_documents({"user_id": current_user.id})
        completed_inspeksi = await db.inspeksi.count_documents({
            "user_id": current_user.id,
            "status": "completed"
        })
        pending_jadwal = await db.jadwal.count_documents({
            "user_id": current_user.id,
            "status": "scheduled"
        })
        
        # Get last activity from history
        last_history = await db.history.find_one(
            {"user_id": current_user.id},
            sort=[("created_at", -1)]
        )
        
        last_activity = last_history["created_at"] if last_history else None
        
        return UserStats(
            total_inspeksi=total_inspeksi,
            total_jadwal=total_jadwal,
            completed_inspeksi=completed_inspeksi,
            pending_jadwal=pending_jadwal,
            last_activity=last_activity
        )
        
    except Exception as e:
        logger.error(f"Failed to get user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )

@router.post("/logout")
async def logout():
    """User logout - client should remove token"""
    return {"message": "Logged out successfully"}