from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Optional
import logging
from pathlib import Path

from app.database import get_database
from app.models.user import UserResponse
from app.models.history import History, HistoryResponse
from app.utils.dependencies import get_current_user
from app.utils.helpers import PyObjectId

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=dict)
async def get_history_list(
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    search: Optional[str] = Query(None, description="Search in description"),
    limit: int = Query(20, ge=1, le=100, description="Limit results"),
    skip: int = Query(0, ge=0, description="Skip results"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get history list dengan filter"""
    try:
        # Build filter query
        filter_query = {"user_id": PyObjectId(current_user.id)}
        
        if action:
            filter_query["action"] = action
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            filter_query["created_at"] = date_filter
        
        if search:
            filter_query["$or"] = [
                {"description": {"$regex": search, "$options": "i"}},
                {"action": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await db.history.count_documents(filter_query)
        
        # Get history with pagination
        cursor = db.history.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
        history_docs = await cursor.to_list(length=limit)
        
        # Convert to response format
        items = []
        for doc in history_docs:
            # Get related inspeksi title if exists
            inspeksi_title = None
            if doc.get("inspeksi_id"):
                inspeksi_doc = await db.inspeksi.find_one({"_id": doc["inspeksi_id"]})
                if inspeksi_doc:
                    inspeksi_title = inspeksi_doc["title"]
            
            items.append({
                "id": str(doc["_id"]),
                "user_id": str(doc["user_id"]),
                "inspeksi_id": str(doc["inspeksi_id"]) if doc.get("inspeksi_id") else None,
                "inspeksi_title": inspeksi_title,
                "action": doc["action"],
                "description": doc["description"],
                "data": doc.get("data", {}),
                "excel_path": doc.get("excel_path"),
                "metadata": doc.get("metadata", {}),
                "created_at": doc["created_at"].isoformat(),
                "file_exists": Path(doc["excel_path"].lstrip("/")).exists() if doc.get("excel_path") else False
            })
        
        return {
            "total": total,
            "items": items,
            "limit": limit,
            "skip": skip,
            "has_more": (skip + limit) < total
        }
        
    except Exception as e:
        logger.error(f"Failed to get history list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get history list"
        )

@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history_detail(
    history_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detail history by ID"""
    try:
        history_doc = await db.history.find_one({
            "_id": PyObjectId(history_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not history_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="History record not found"
            )
        
        return HistoryResponse(
            id=str(history_doc["_id"]),
            user_id=str(history_doc["user_id"]),
            inspeksi_id=str(history_doc["inspeksi_id"]) if history_doc.get("inspeksi_id") else None,
            action=history_doc["action"],
            description=history_doc["description"],
            data=history_doc.get("data"),
            excel_path=history_doc.get("excel_path"),
            metadata=history_doc.get("metadata"),
            created_at=history_doc["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get history detail"
        )

@router.delete("/{history_id}")
async def delete_history(
    history_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete history record and associated files"""
    try:
        # Get history document first
        history_doc = await db.history.find_one({
            "_id": PyObjectId(history_id),
            "user_id": PyObjectId(current_user.id)
        })
        
        if not history_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="History record not found"
            )
        
        # Delete associated Excel file if exists
        if history_doc.get("excel_path"):
            try:
                file_path = Path(history_doc["excel_path"].lstrip("/"))
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted Excel file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete Excel file: {e}")
        
        # Delete history record
        result = await db.history.delete_one({"_id": PyObjectId(history_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="History record not found"
            )
        
        logger.info(f"History deleted by {current_user.username}: {history_id}")
        
        return {"message": "History record deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete history record"
        )

@router.delete("/bulk/delete")
async def delete_multiple_history(
    history_ids: list[str],
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete multiple history records"""
    try:
        if not history_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No history IDs provided"
            )
        
        # Convert string IDs to ObjectIds
        object_ids = [PyObjectId(id) for id in history_ids]
        
        # Get history documents to delete files
        history_docs = await db.history.find({
            "_id": {"$in": object_ids},
            "user_id": PyObjectId(current_user.id)
        }).to_list(length=len(object_ids))
        
        # Delete associated files
        deleted_files = []
        for doc in history_docs:
            if doc.get("excel_path"):
                try:
                    file_path = Path(doc["excel_path"].lstrip("/"))
                    if file_path.exists():
                        file_path.unlink()
                        deleted_files.append(str(file_path))
                except Exception as e:
                    logger.warning(f"Failed to delete file {doc['excel_path']}: {e}")
        
        # Delete history records
        result = await db.history.delete_many({
            "_id": {"$in": object_ids},
            "user_id": PyObjectId(current_user.id)
        })
        
        logger.info(f"Bulk delete by {current_user.username}: {result.deleted_count} history records")
        
        return {
            "message": f"Successfully deleted {result.deleted_count} history records",
            "deleted_count": result.deleted_count,
            "deleted_files": deleted_files
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bulk delete history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete history records"
        )

@router.get("/statistics/summary")
async def get_history_statistics(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get history statistics"""
    try:
        # Get total history count
        total_history = await db.history.count_documents({"user_id": PyObjectId(current_user.id)})
        
        # Get count by action type
        action_pipeline = [
            {"$match": {"user_id": PyObjectId(current_user.id)}},
            {"$group": {"_id": "$action", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        action_counts = await db.history.aggregate(action_pipeline).to_list(10)
        
        # Get this week's activity
        start_of_week = datetime.utcnow() - timedelta(days=7)
        this_week_count = await db.history.count_documents({
            "user_id": PyObjectId(current_user.id),
            "created_at": {"$gte": start_of_week}
        })
        
        # Get latest activity
        latest_activity = await db.history.find_one(
            {"user_id": PyObjectId(current_user.id)},
            sort=[("created_at", -1)]
        )
        
        # Calculate total file size
        file_size_pipeline = [
            {"$match": {
                "user_id": PyObjectId(current_user.id),
                "metadata.file_size": {"$exists": True}
            }},
            {"$group": {"_id": None, "total_size": {"$sum": "$metadata.file_size"}}}
        ]
        
        file_size_result = await db.history.aggregate(file_size_pipeline).to_list(1)
        total_file_size = file_size_result[0]["total_size"] if file_size_result else 0
        
        return {
            "total_history": total_history,
            "this_week_count": this_week_count,
            "action_counts": [
                {"action": item["_id"], "count": item["count"]} 
                for item in action_counts
            ],
            "total_file_size": total_file_size,
            "latest_activity": {
                "action": latest_activity["action"],
                "description": latest_activity["description"],
                "created_at": latest_activity["created_at"].isoformat()
            } if latest_activity else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get history statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get history statistics"
        )

@router.post("/cleanup/old-files")
async def cleanup_old_files(
    days_old: int = Query(30, ge=1, le=365, description="Delete files older than X days"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Clean up old files based on age"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Find old history records with files
        old_history = await db.history.find({
            "user_id": PyObjectId(current_user.id),
            "created_at": {"$lt": cutoff_date},
            "excel_path": {"$exists": True, "$ne": None}
        }).to_list(1000)
        
        deleted_files = []
        for doc in old_history:
            try:
                file_path = Path(doc["excel_path"].lstrip("/"))
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(str(file_path))
            except Exception as e:
                logger.warning(f"Failed to delete old file {doc['excel_path']}: {e}")
        
        logger.info(f"Cleanup by {current_user.username}: deleted {len(deleted_files)} old files")
        
        return {
            "message": f"Cleaned up {len(deleted_files)} old files",
            "deleted_count": len(deleted_files),
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup old files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup old files"
        )