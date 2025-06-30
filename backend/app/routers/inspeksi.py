from fastapi import APIRouter, Depends, HTTPException, status, Query, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Optional, List
import logging

from app.database import get_database
from app.models.user import UserResponse
from app.models.inspeksi import Inspeksi, InspeksiResponse, InspeksiData
from app.utils.dependencies import get_current_user
from app.utils.helpers import PyObjectId, generate_session_id
from app.services.excel_service import excel_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/save-from-cache", response_model=InspeksiResponse, status_code=status.HTTP_201_CREATED)
async def save_inspeksi_from_cache(
    session_id: str = Form(...),
    title: str = Form(...),
    location: str = Form(...),
    jadwal_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Save inspeksi from cached data and clear cache"""
    try:
        # Get cached data
        cache_doc = await db.cache.find_one({
            "user_id": PyObjectId(current_user.id),
            "session_id": session_id
        })
        
        if not cache_doc or not cache_doc["data"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No cached data found for this session"
            )
        
        # Validate jadwal_id if provided
        if jadwal_id:
            jadwal_doc = await db.jadwal.find_one({
                "_id": PyObjectId(jadwal_id),
                "user_id": PyObjectId(current_user.id)
            })
            if not jadwal_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Jadwal not found"
                )
        
        # Convert cached data to InspeksiData objects
        data_list = [InspeksiData(**item) for item in cache_doc["data"]]
        
        # Generate Excel file
        excel_result = excel_service.generate_excel(data_list, title)
        
        if not excel_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate Excel: {excel_result.get('error')}"
            )
        
        # Create inspeksi document
        inspeksi_doc = {
            "_id": PyObjectId(),
            "user_id": PyObjectId(current_user.id),
            "jadwal_id": PyObjectId(jadwal_id) if jadwal_id else None,
            "session_id": session_id,
            "title": title,
            "location": location,
            "inspection_date": datetime.utcnow(),
            "data": [item.dict() for item in data_list],
            "excel_path": excel_result["relative_path"],
            "status": "completed",
            "total_items": len(data_list),
            "notes": notes,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert inspeksi
        result = await db.inspeksi.insert_one(inspeksi_doc)
        
        # Update jadwal status if linked
        if jadwal_id:
            await db.jadwal.update_one(
                {"_id": PyObjectId(jadwal_id)},
                {"$set": {"status": "completed", "updated_at": datetime.utcnow()}}
            )
        
        # Save to history
        history_data = {
            "_id": PyObjectId(),
            "user_id": PyObjectId(current_user.id),
            "inspeksi_id": result.inserted_id,
            "action": "save_inspeksi",
            "description": f"Saved inspeksi: {title}",
            "data": {
                "title": title,
                "location": location,
                "total_items": len(data_list),
                "excel_filename": excel_result["filename"]
            },
            "excel_path": excel_result["relative_path"],
            "metadata": {
                "file_size": excel_result["file_size"],
                "total_items": len(data_list)
            },
            "created_at": datetime.utcnow()
        }
        
        await db.history.insert_one(history_data)
        
        # Clear cache
        await db.cache.delete_one({
            "user_id": PyObjectId(current_user.id),
            "session_id": session_id
        })
        
        # Get created inspeksi
        created_inspeksi = await db.inspeksi.find_one({"_id": result.inserted_id})
        
        logger.info(f"Inspeksi saved by {current_user.username}: {title}")
        
        return InspeksiResponse(
            id=str(created_inspeksi["_id"]),
            user_id=str(created_inspeksi["user_id"]),
            jadwal_id=str(created_inspeksi["jadwal_id"]) if created_inspeksi["jadwal_id"] else None,
            session_id=created_inspeksi["session_id"],
            title=created_inspeksi["title"],
            location=created_inspeksi["location"],
            inspection_date=created_inspeksi["inspection_date"],
            data=[InspeksiData(**item) for item in created_inspeksi["data"]],
            excel_path=created_inspeksi["excel_path"],
            status=created_inspeksi["status"],
            total_items=created_inspeksi["total_items"],
            notes=created_inspeksi["notes"],
            created_at=created_inspeksi["created_at"],
            updated_at=created_inspeksi["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save inspeksi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save inspeksi"
        )

@router.get("/", response_model=dict)
async def get_inspeksi_list(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    search: Optional[str] = Query(None, description="Search in title and location"),
    limit: int = Query(10, ge=1, le=100, description="Limit results"),
    skip: int = Query(0, ge=0, description="Skip results"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get list inspeksi dengan filter"""
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
            filter_query["inspection_date"] = date_filter
        
        if search:
            filter_query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"location": {"$regex": search, "$options": "i"}},
                {"notes": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await db.inspeksi.count_documents(filter_query)
        
        # Get inspeksi with pagination
        cursor = db.inspeksi.find(filter_query).sort("inspection_date", -1).skip(skip).limit(limit)
        inspeksi_docs = await cursor.to_list(length=limit)
        
        # Convert to response format
        items = []
        for doc in inspeksi_docs:
            items.append({
                "id": str(doc["_id"]),
                "user_id": str(doc["user_id"]),
                "jadwal_id": str(doc["jadwal_id"]) if doc.get("jadwal_id") else None,
                "session_id": doc["session_id"],
                "title": doc["title"],
                "location": doc["location"],
                "inspection_date": doc["inspection_date"].isoformat(),
                "excel_path": doc.get("excel_path"),
                "status": doc["status"],
                "total_items": doc["total_items"],
                "notes": doc.get("notes"),
                "created_at": doc["created_at"].isoformat(),
                "updated_at": doc["updated_at"].isoformat()
            })
        
        return {
            "total": total,
            "items": items,
            "limit": limit,
            "skip": skip,
            "has_more": (skip + limit) < total
        }
        
    except Exception as e:
        logger.error(f"Failed to get inspeksi list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get inspeksi list"
        )

@router.get("/{inspeksi_id}", response_model=InspeksiResponse)
async def get_inspeksi_detail(
    inspeksi_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detail inspeksi by ID"""
    try:
        inspeksi_doc = await db.inspeksi.find_one({
            "_id": PyObjectId(inspeksi_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not inspeksi_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inspeksi not found"
            )
        
        return InspeksiResponse(
            id=str(inspeksi_doc["_id"]),
            user_id=str(inspeksi_doc["user_id"]),
            jadwal_id=str(inspeksi_doc["jadwal_id"]) if inspeksi_doc.get("jadwal_id") else None,
            session_id=inspeksi_doc["session_id"],
            title=inspeksi_doc["title"],
            location=inspeksi_doc["location"],
            inspection_date=inspeksi_doc["inspection_date"],
            data=[InspeksiData(**item) for item in inspeksi_doc["data"]],
            excel_path=inspeksi_doc.get("excel_path"),
            status=inspeksi_doc["status"],
            total_items=inspeksi_doc["total_items"],
            notes=inspeksi_doc.get("notes"),
            created_at=inspeksi_doc["created_at"],
            updated_at=inspeksi_doc["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get inspeksi detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get inspeksi detail"
        )

@router.delete("/{inspeksi_id}")
async def delete_inspeksi(
    inspeksi_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete inspeksi"""
    try:
        # Check if inspeksi exists and belongs to user
        inspeksi_doc = await db.inspeksi.find_one({
            "_id": PyObjectId(inspeksi_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not inspeksi_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inspeksi not found"
            )
        
        # Delete related files if they exist
        if inspeksi_doc.get("excel_path"):
            try:
                from pathlib import Path
                file_path = Path(inspeksi_doc["excel_path"].lstrip("/"))
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted Excel file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete Excel file: {e}")
        
        # Delete inspeksi
        result = await db.inspeksi.delete_one({"_id": PyObjectId(inspeksi_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inspeksi not found"
            )
        
        # Delete related history records
        await db.history.delete_many({"inspeksi_id": PyObjectId(inspeksi_id)})
        
        logger.info(f"Inspeksi deleted by {current_user.username}: {inspeksi_id}")
        
        return {"message": "Inspeksi deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete inspeksi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete inspeksi"
        )

@router.get("/statistics/summary")
async def get_inspeksi_statistics(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get inspeksi statistics summary"""
    try:
        # Get counts
        total_inspeksi = await db.inspeksi.count_documents({"user_id": PyObjectId(current_user.id)})
        completed_inspeksi = await db.inspeksi.count_documents({
            "user_id": PyObjectId(current_user.id),
            "status": "completed"
        })
        
        # Get this month's count
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_count = await db.inspeksi.count_documents({
            "user_id": PyObjectId(current_user.id),
            "created_at": {"$gte": start_of_month}
        })
        
        # Get total items inspected
        pipeline = [
            {"$match": {"user_id": PyObjectId(current_user.id)}},
            {"$group": {"_id": None, "total_items": {"$sum": "$total_items"}}}
        ]
        
        total_items_result = await db.inspeksi.aggregate(pipeline).to_list(1)
        total_items = total_items_result[0]["total_items"] if total_items_result else 0
        
        # Get latest inspeksi
        latest_inspeksi = await db.inspeksi.find_one(
            {"user_id": PyObjectId(current_user.id)},
            sort=[("created_at", -1)]
        )
        
        return {
            "total_inspeksi": total_inspeksi,
            "completed_inspeksi": completed_inspeksi,
            "this_month_count": this_month_count,
            "total_items_inspected": total_items,
            "latest_inspeksi": {
                "id": str(latest_inspeksi["_id"]),
                "title": latest_inspeksi["title"],
                "created_at": latest_inspeksi["created_at"].isoformat()
            } if latest_inspeksi else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get inspeksi statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get inspeksi statistics"
        )