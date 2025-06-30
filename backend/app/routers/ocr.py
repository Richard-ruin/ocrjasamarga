from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import uuid
import aiofiles
from pathlib import Path

from app.database import get_database
from app.models.user import UserResponse
from app.models.inspeksi import InspeksiData
from app.models.cache import Cache
from app.services.ocr_service import ocr_service
from app.services.excel_service import excel_service
from app.utils.dependencies import get_current_user
from app.utils.helpers import PyObjectId, generate_session_id, clean_filename
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/process-image")
async def process_image_ocr(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process image dengan OCR untuk extract koordinat GPS"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Check file size
        file_content = await file.read()
        if len(file_content) > settings.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum limit of {settings.max_file_size} bytes"
            )
        
        # Save uploaded file
        filename = clean_filename(file.filename)
        file_path = Path(settings.upload_dir) / "images" / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # Process image with OCR
        ocr_result = ocr_service.process_image(file_content)
        
        if not ocr_result["success"]:
            # Remove failed file
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"OCR processing failed: {ocr_result.get('error', 'Unknown error')}"
            )
        
        # Prepare response
        response = {
            "success": True,
            "filename": filename,
            "file_path": str(file_path),
            "file_size": len(file_content),
            "ocr_result": ocr_result,
            "coordinates": ocr_result["coordinates"],
            "extracted_info": {
                "latitude": ocr_result["coordinates"]["latitude"],
                "longitude": ocr_result["coordinates"]["longitude"],
                "address": ocr_result.get("address", {}),
                "timestamp": ocr_result.get("timestamp"),
                "compass_direction": ocr_result.get("compass_direction")
            },
            "processed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Image processed successfully by {current_user.username}: {filename}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image processing failed"
        )

@router.post("/process-base64")
async def process_base64_image(
    image_data: str = Form(...),
    session_id: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process base64 image dengan OCR"""
    try:
        # Process image with OCR
        ocr_result = ocr_service.process_base64_image(image_data)
        
        if not ocr_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"OCR processing failed: {ocr_result.get('error', 'Unknown error')}"
            )
        
        # Generate session ID if not provided
        if not session_id:
            session_id = generate_session_id()
        
        response = {
            "success": True,
            "session_id": session_id,
            "ocr_result": ocr_result,
            "coordinates": ocr_result["coordinates"],
            "extracted_info": {
                "latitude": ocr_result["coordinates"]["latitude"],
                "longitude": ocr_result["coordinates"]["longitude"],
                "address": ocr_result.get("address", {}),
                "timestamp": ocr_result.get("timestamp"),
                "compass_direction": ocr_result.get("compass_direction")
            },
            "processed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Base64 image processed successfully by {current_user.username}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Base64 image processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Base64 image processing failed"
        )

@router.post("/cache/add-data")
async def add_data_to_cache(
    session_id: str = Form(...),
    no: str = Form(...),
    jalur: str = Form(...),
    latitude: str = Form(...),
    longitude: str = Form(...),
    kondisi: str = Form(...),
    keterangan: str = Form(...),
    image_data: Optional[str] = Form(None),
    image_path: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add data to cache untuk inspeksi"""
    try:
        # Validate kondisi
        if kondisi.lower() not in ['baik', 'sedang', 'buruk']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kondisi harus salah satu dari: baik, sedang, buruk"
            )
        
        # Create inspeksi data
        inspeksi_data = InspeksiData(
            no=no,
            jalur=jalur,
            latitude=latitude,
            longitude=longitude,
            kondisi=kondisi.lower(),
            keterangan=keterangan,
            image_data=image_data,
            image_path=image_path
        )
        
        # Find existing cache or create new one
        cache_doc = await db.cache.find_one({
            "user_id": PyObjectId(current_user.id),
            "session_id": session_id
        })
        
        if cache_doc:
            # Add to existing cache
            data_list = [InspeksiData(**item) for item in cache_doc["data"]]
            data_list.append(inspeksi_data)
            
            await db.cache.update_one(
                {"_id": cache_doc["_id"]},
                {
                    "$set": {
                        "data": [item.dict() for item in data_list],
                        "updated_at": datetime.utcnow(),
                        "metadata": {
                            "total_items": len(data_list),
                            "last_update": datetime.utcnow().isoformat()
                        }
                    }
                }
            )
        else:
            # Create new cache
            cache_data = {
                "_id": PyObjectId(),
                "user_id": PyObjectId(current_user.id),
                "session_id": session_id,
                "cache_type": "inspeksi",
                "data": [inspeksi_data.dict()],
                "metadata": {
                    "total_items": 1,
                    "last_update": datetime.utcnow().isoformat()
                },
                "expires_at": datetime.utcnow() + timedelta(hours=24),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await db.cache.insert_one(cache_data)
        
        # Get updated cache
        updated_cache = await db.cache.find_one({
            "user_id": PyObjectId(current_user.id),
            "session_id": session_id
        })
        
        logger.info(f"Data added to cache by {current_user.username}: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "total_items": len(updated_cache["data"]),
            "data": updated_cache["data"],
            "message": "Data added to cache successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add data to cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add data to cache"
        )

@router.get("/cache/{session_id}")
async def get_cache_data(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get cached data for session"""
    try:
        cache_doc = await db.cache.find_one({
            "user_id": PyObjectId(current_user.id),
            "session_id": session_id
        })
        
        if not cache_doc:
            return {
                "success": True,
                "session_id": session_id,
                "total_items": 0,
                "data": [],
                "message": "No cached data found"
            }
        
        return {
            "success": True,
            "session_id": session_id,
            "total_items": len(cache_doc["data"]),
            "data": cache_doc["data"],
            "metadata": cache_doc.get("metadata", {}),
            "expires_at": cache_doc["expires_at"].isoformat(),
            "message": "Cache data retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache data"
        )

@router.post("/generate-excel")
async def generate_excel_from_cache(
    session_id: str = Form(...),
    title: str = Form("Inspeksi Lapangan"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Generate Excel file from cached data"""
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
        
        # Convert to InspeksiData objects
        data_list = [InspeksiData(**item) for item in cache_doc["data"]]
        
        # Generate Excel
        excel_result = excel_service.generate_excel(data_list, title)
        
        if not excel_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Excel generation failed: {excel_result.get('error', 'Unknown error')}"
            )
        
        # Save to history
        history_data = {
            "_id": PyObjectId(),
            "user_id": PyObjectId(current_user.id),
            "inspeksi_id": None,
            "action": "generate_excel",
            "description": f"Generated Excel file: {excel_result['filename']}",
            "data": {
                "session_id": session_id,
                "title": title,
                "total_items": excel_result["total_items"],
                "filename": excel_result["filename"],
                "file_size": excel_result["file_size"]
            },
            "excel_path": excel_result["relative_path"],
            "metadata": {
                "file_size": excel_result["file_size"],
                "total_items": excel_result["total_items"]
            },
            "created_at": datetime.utcnow()
        }
        
        await db.history.insert_one(history_data)
        
        logger.info(f"Excel generated by {current_user.username}: {excel_result['filename']}")
        
        return {
            "success": True,
            "excel_result": excel_result,
            "download_url": excel_result["relative_path"],
            "session_id": session_id,
            "history_id": str(history_data["_id"]),
            "message": "Excel file generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel generation failed"
        )

@router.delete("/cache/{session_id}")
async def clear_cache(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Clear cached data for session"""
    try:
        result = await db.cache.delete_one({
            "user_id": PyObjectId(current_user.id),
            "session_id": session_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No cached data found for this session"
            )
        
        logger.info(f"Cache cleared by {current_user.username}: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Cache cleared successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )

@router.post("/validate-coordinates")
async def validate_coordinates(
    latitude: str = Form(...),
    longitude: str = Form(...),
    current_user: UserResponse = Depends(get_current_user)
):
    """Validate if coordinates are within Indonesia bounds"""
    try:
        from app.utils.helpers import validate_indonesia_coordinates, dms_to_decimal
        
        # Validate format and Indonesia bounds
        is_valid = validate_indonesia_coordinates(latitude, longitude)
        
        response = {
            "valid": is_valid,
            "latitude": latitude,
            "longitude": longitude
        }
        
        if is_valid:
            try:
                # Convert to decimal for additional info
                lat_decimal = dms_to_decimal(latitude)
                lng_decimal = dms_to_decimal(longitude)
                
                response.update({
                    "decimal_coordinates": {
                        "latitude": lat_decimal,
                        "longitude": lng_decimal
                    },
                    "message": "Coordinates are valid for Indonesia"
                })
            except:
                response["message"] = "Coordinates format is valid but conversion failed"
        else:
            response["message"] = "Coordinates are not valid for Indonesia or have invalid format"
        
        return response
        
    except Exception as e:
        logger.error(f"Coordinate validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Coordinate validation failed"
        )

@router.get("/template/info")
async def get_template_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get Excel template information"""
    try:
        template_info = excel_service.get_template_info()
        validation_result = excel_service.validate_template()
        
        return {
            "template_info": template_info,
            "validation": validation_result,
            "message": "Template information retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get template info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get template information"
        )

@router.post("/session/new")
async def create_new_session(
    current_user: UserResponse = Depends(get_current_user)
):
    """Create new session ID for inspeksi"""
    try:
        session_id = generate_session_id()
        
        return {
            "success": True,
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "message": "New session created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create new session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create new session"
        )