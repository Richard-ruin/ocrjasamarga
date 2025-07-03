# app/routes/dashboard.py - Perbaikan error handling
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, date, timedelta
from bson import ObjectId
import logging

from app.routes.auth import get_current_admin
from app.config import db

router = APIRouter()
logger = logging.getLogger(__name__)

# Collections
jadwal_collection = db["jadwal"]
inspeksi_collection = db["inspeksi"]
history_collection = db["saved_tables"]

@router.get("/dashboard/stats")
async def get_dashboard_stats(current_admin: dict = Depends(get_current_admin)):
    """Ambil statistik untuk dashboard dengan error handling yang lebih robust"""
    try:
        admin_id = str(current_admin["_id"])
        logger.info(f"Fetching dashboard stats for admin: {admin_id}")
        
        # Initialize default stats
        stats = {
            "jadwal": {
                "total": 0,
                "scheduled": 0, 
                "completed": 0,
                "cancelled": 0,
                "today": 0
            },
            "inspeksi": {
                "total": 0,
                "draft": 0,
                "generated": 0,
                "saved": 0
            },
            "history": {
                "total": 0,
                "this_week": 0
            },
            "recent_activities": {
                "jadwal": [],
                "inspeksi": []
            }
        }
        
        # Safely fetch jadwal stats
        try:
            stats["jadwal"]["total"] = jadwal_collection.count_documents({"admin_id": admin_id})
            stats["jadwal"]["scheduled"] = jadwal_collection.count_documents({
                "admin_id": admin_id, 
                "status": "scheduled"
            })
            stats["jadwal"]["completed"] = jadwal_collection.count_documents({
                "admin_id": admin_id, 
                "status": "completed"
            })
            stats["jadwal"]["cancelled"] = jadwal_collection.count_documents({
                "admin_id": admin_id, 
                "status": "cancelled"
            })
            
            # Jadwal hari ini - handle different date formats
            today = datetime.now().date()
            today_str = today.isoformat()
            stats["jadwal"]["today"] = jadwal_collection.count_documents({
                "admin_id": admin_id,
                "$or": [
                    {"tanggal": today_str},
                    {"tanggal": today},
                    {"tanggal": {"$regex": f"^{today_str}"}}
                ]
            })
            
        except Exception as e:
            logger.error(f"Error fetching jadwal stats: {e}")
        
        # Safely fetch inspeksi stats
        try:
            stats["inspeksi"]["total"] = inspeksi_collection.count_documents({"admin_id": admin_id})
            stats["inspeksi"]["draft"] = inspeksi_collection.count_documents({
                "admin_id": admin_id,
                "status": "draft"
            })
            stats["inspeksi"]["generated"] = inspeksi_collection.count_documents({
                "admin_id": admin_id,
                "status": "generated"
            })
            stats["inspeksi"]["saved"] = inspeksi_collection.count_documents({
                "admin_id": admin_id,
                "status": "saved"
            })
        except Exception as e:
            logger.error(f"Error fetching inspeksi stats: {e}")
        
        # Safely fetch history stats
        try:
            stats["history"]["total"] = history_collection.count_documents({
                "admin_id": admin_id
            })
            
            # History minggu ini
            week_ago = datetime.now() - timedelta(days=7)
            stats["history"]["this_week"] = history_collection.count_documents({
                "admin_id": admin_id,
                "$or": [
                    {"summary.created_at": {"$gte": week_ago.isoformat()}},
                    {"created_at": {"$gte": week_ago.isoformat()}}
                ]
            })
        except Exception as e:
            logger.error(f"Error fetching history stats: {e}")
        
        # Safely fetch recent activities
        try:
            recent_jadwal = list(jadwal_collection.find(
                {"admin_id": admin_id},
                {"nama_inspektur": 1, "tanggal": 1, "status": 1, "created_at": 1}
            ).sort("created_at", -1).limit(5))
            
            # Convert ObjectId to string
            for item in recent_jadwal:
                item["_id"] = str(item["_id"])
            
            stats["recent_activities"]["jadwal"] = recent_jadwal
            
        except Exception as e:
            logger.error(f"Error fetching recent jadwal: {e}")
        
        try:
            recent_inspeksi = list(inspeksi_collection.find(
                {"admin_id": admin_id},
                {"status": 1, "created_at": 1, "data": 1}
            ).sort("created_at", -1).limit(5))
            
            # Convert ObjectId to string
            for item in recent_inspeksi:
                item["_id"] = str(item["_id"])
            
            stats["recent_activities"]["inspeksi"] = recent_inspeksi
            
        except Exception as e:
            logger.error(f"Error fetching recent inspeksi: {e}")
        
        logger.info(f"Successfully fetched dashboard stats for admin {admin_id}")
        return stats
        
    except Exception as e:
        logger.error(f"Critical error in get_dashboard_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )