from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import Optional
import logging

from app.database import get_database
from app.models.user import UserResponse
from app.models.jadwal import Jadwal, JadwalResponse
from app.schemas.jadwal import JadwalCreate, JadwalUpdate, JadwalFilter, JadwalListResponse
from app.utils.dependencies import get_current_user
from app.utils.helpers import PyObjectId

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=JadwalResponse, status_code=status.HTTP_201_CREATED)
async def create_jadwal(
    jadwal_data: JadwalCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Membuat jadwal inspeksi baru"""
    try:
        # Create jadwal document
        jadwal_doc = {
            "_id": PyObjectId(),
            "user_id": PyObjectId(current_user.id),
            "title": jadwal_data.title,
            "description": jadwal_data.description,
            "waktu": jadwal_data.waktu,
            "alamat": jadwal_data.alamat,
            "status": "scheduled",
            "location_lat": jadwal_data.location_lat,
            "location_lng": jadwal_data.location_lng,
            "notes": jadwal_data.notes,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert jadwal
        result = await db.jadwal.insert_one(jadwal_doc)
        
        # Get inserted jadwal
        created_jadwal = await db.jadwal.find_one({"_id": result.inserted_id})
        
        logger.info(f"Jadwal created by {current_user.username}: {jadwal_data.title}")
        
        return JadwalResponse(
            id=str(created_jadwal["_id"]),
            user_id=str(created_jadwal["user_id"]),
            title=created_jadwal["title"],
            description=created_jadwal["description"],
            waktu=created_jadwal["waktu"],
            alamat=created_jadwal["alamat"],
            status=created_jadwal["status"],
            location_lat=created_jadwal["location_lat"],
            location_lng=created_jadwal["location_lng"],
            notes=created_jadwal["notes"],
            created_at=created_jadwal["created_at"],
            updated_at=created_jadwal["updated_at"]
        )
        
    except Exception as e:
        logger.error(f"Failed to create jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create jadwal"
        )

@router.get("/", response_model=JadwalListResponse)
async def get_jadwal_list(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    search: Optional[str] = Query(None, description="Search in title and alamat"),
    limit: int = Query(10, ge=1, le=100, description="Limit results"),
    skip: int = Query(0, ge=0, description="Skip results"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get list jadwal dengan filter"""
    try:
        # Build filter query
        filter_query = {"user_id": PyObjectId(current_user.id)}
        
        if status_filter:
            filter_query["status"] = status_filter
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            filter_query["waktu"] = date_filter
        
        if search:
            filter_query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"alamat": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await db.jadwal.count_documents(filter_query)
        
        # Get jadwal with pagination
        cursor = db.jadwal.find(filter_query).sort("waktu", -1).skip(skip).limit(limit)
        jadwal_docs = await cursor.to_list(length=limit)
        
        # Convert to response format
        items = []
        for doc in jadwal_docs:
            items.append({
                "id": str(doc["_id"]),
                "user_id": str(doc["user_id"]),
                "title": doc["title"],
                "description": doc["description"],
                "waktu": doc["waktu"].isoformat(),
                "alamat": doc["alamat"],
                "status": doc["status"],
                "location_lat": doc["location_lat"],
                "location_lng": doc["location_lng"],
                "notes": doc["notes"],
                "created_at": doc["created_at"].isoformat(),
                "updated_at": doc["updated_at"].isoformat()
            })
        
        return JadwalListResponse(
            total=total,
            items=items,
            limit=limit,
            skip=skip,
            has_more=(skip + limit) < total
        )
        
    except Exception as e:
        logger.error(f"Failed to get jadwal list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get jadwal list"
        )

@router.get("/{jadwal_id}", response_model=JadwalResponse)
async def get_jadwal_detail(
    jadwal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detail jadwal by ID"""
    try:
        # Find jadwal
        jadwal_doc = await db.jadwal.find_one({
            "_id": PyObjectId(jadwal_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not jadwal_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        return JadwalResponse(
            id=str(jadwal_doc["_id"]),
            user_id=str(jadwal_doc["user_id"]),
            title=jadwal_doc["title"],
            description=jadwal_doc["description"],
            waktu=jadwal_doc["waktu"],
            alamat=jadwal_doc["alamat"],
            status=jadwal_doc["status"],
            location_lat=jadwal_doc["location_lat"],
            location_lng=jadwal_doc["location_lng"],
            notes=jadwal_doc["notes"],
            created_at=jadwal_doc["created_at"],
            updated_at=jadwal_doc["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get jadwal detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get jadwal detail"
        )

@router.put("/{jadwal_id}", response_model=JadwalResponse)
async def update_jadwal(
    jadwal_id: str,
    jadwal_update: JadwalUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update jadwal"""
    try:
        # Check if jadwal exists and belongs to user
        existing_jadwal = await db.jadwal.find_one({
            "_id": PyObjectId(jadwal_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not existing_jadwal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        # Build update data
        update_data = {}
        
        if jadwal_update.title is not None:
            update_data["title"] = jadwal_update.title
        if jadwal_update.description is not None:
            update_data["description"] = jadwal_update.description
        if jadwal_update.waktu is not None:
            update_data["waktu"] = jadwal_update.waktu
        if jadwal_update.alamat is not None:
            update_data["alamat"] = jadwal_update.alamat
        if jadwal_update.status is not None:
            update_data["status"] = jadwal_update.status
        if jadwal_update.location_lat is not None:
            update_data["location_lat"] = jadwal_update.location_lat
        if jadwal_update.location_lng is not None:
            update_data["location_lng"] = jadwal_update.location_lng
        if jadwal_update.notes is not None:
            update_data["notes"] = jadwal_update.notes
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Update jadwal
        result = await db.jadwal.update_one(
            {"_id": PyObjectId(jadwal_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found or no changes made"
            )
        
        # Get updated jadwal
        updated_jadwal = await db.jadwal.find_one({"_id": PyObjectId(jadwal_id)})
        
        logger.info(f"Jadwal updated by {current_user.username}: {jadwal_id}")
        
        return JadwalResponse(
            id=str(updated_jadwal["_id"]),
            user_id=str(updated_jadwal["user_id"]),
            title=updated_jadwal["title"],
            description=updated_jadwal["description"],
            waktu=updated_jadwal["waktu"],
            alamat=updated_jadwal["alamat"],
            status=updated_jadwal["status"],
            location_lat=updated_jadwal["location_lat"],
            location_lng=updated_jadwal["location_lng"],
            notes=updated_jadwal["notes"],
            created_at=updated_jadwal["created_at"],
            updated_at=updated_jadwal["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update jadwal"
        )

@router.delete("/{jadwal_id}")
async def delete_jadwal(
    jadwal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete jadwal"""
    try:
        # Check if jadwal exists and belongs to user
        existing_jadwal = await db.jadwal.find_one({
            "_id": PyObjectId(jadwal_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not existing_jadwal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        # Check if there are related inspeksi
        related_inspeksi = await db.inspeksi.count_documents({"jadwal_id": PyObjectId(jadwal_id)})
        if related_inspeksi > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete jadwal. There are {related_inspeksi} related inspeksi records."
            )
        
        # Delete jadwal
        result = await db.jadwal.delete_one({"_id": PyObjectId(jadwal_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        logger.info(f"Jadwal deleted by {current_user.username}: {jadwal_id}")
        
        return {"message": "Jadwal deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete jadwal"
        )

@router.get("/upcoming/count")
async def get_upcoming_jadwal_count(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get count of upcoming jadwal"""
    try:
        count = await db.jadwal.count_documents({
            "user_id": PyObjectId(current_user.id),
            "status": "scheduled",
            "waktu": {"$gte": datetime.utcnow()}
        })
        
        return {"upcoming_count": count}
        
    except Exception as e:
        logger.error(f"Failed to get upcoming jadwal count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get upcoming jadwal count"
        )