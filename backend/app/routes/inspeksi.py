from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
import json

from ..auth.auth import get_current_admin
from ..models.inspeksi import (
    InspeksiCreate, InspeksiUpdate, InspeksiResponse, InspeksiInDB,
    InspeksiDataItem, OCRResult, GenerateRequest
)
from ..models.history import HistoryCreate, HistoryInDB
from ..database import get_database
from ..services.ocr_service import OCRService
from ..services.excel_service import ExcelService
from ..services.cache_service import CacheService
from ..utils.helpers import create_response, save_uploaded_file, save_base64_image
from ..utils.validators import (
    validate_kondisi, validate_latitude_indonesia, validate_longitude_indonesia,
    validate_jalur_name, validate_keterangan, validate_base64_image
)

router = APIRouter(prefix="/inspeksi", tags=["Inspeksi"])

# Initialize services with lazy loading
ocr_service = None
excel_service = None
cache_service = None

def get_ocr_service():
    """Get OCR service instance with lazy loading"""
    global ocr_service
    if ocr_service is None:
        ocr_service = OCRService()
    return ocr_service

def get_excel_service():
    """Get Excel service instance with lazy loading"""
    global excel_service
    if excel_service is None:
        excel_service = ExcelService()
    return excel_service

def get_cache_service():
    """Get Cache service instance with lazy loading"""
    global cache_service
    if cache_service is None:
        cache_service = CacheService()
    return cache_service

@router.post("/", response_model=dict)
async def create_inspeksi(
    inspeksi_data: InspeksiCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Create inspeksi baru"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validasi jadwal_id jika ada
        if inspeksi_data.jadwal_id:
            if not ObjectId.is_valid(inspeksi_data.jadwal_id):
                raise HTTPException(status_code=400, detail="Invalid jadwal ID")
            
            jadwal = await db.jadwal.find_one({
                "_id": ObjectId(inspeksi_data.jadwal_id),
                "admin_id": admin_id
            })
            
            if not jadwal:
                raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Validasi data items
        for i, item in enumerate(inspeksi_data.data):
            if item.kondisi:
                kondisi_valid, kondisi_msg = validate_kondisi(item.kondisi)
                if not kondisi_valid:
                    raise HTTPException(status_code=400, detail=f"Item {i+1}: {kondisi_msg}")
            
            if item.jalur:
                jalur_valid, jalur_msg = validate_jalur_name(item.jalur)
                if not jalur_valid:
                    raise HTTPException(status_code=400, detail=f"Item {i+1}: {jalur_msg}")
            
            if item.keterangan:
                keterangan_valid, keterangan_msg = validate_keterangan(item.keterangan)
                if not keterangan_valid:
                    raise HTTPException(status_code=400, detail=f"Item {i+1}: {keterangan_msg}")
        
        # Create inspeksi document
        inspeksi_doc = InspeksiInDB(
            jadwal_id=inspeksi_data.jadwal_id,
            data=[item.model_dump() for item in inspeksi_data.data],
            status=inspeksi_data.status,
            admin_id=admin_id
        )
        
        # Insert to database
        result = await db.inspeksi.insert_one(inspeksi_doc.model_dump())
        inspeksi_id = str(result.inserted_id)
        
        # Save to cache if status is draft
        if inspeksi_data.status == "draft":
            cache_svc = get_cache_service()
            await cache_svc.set_cache(
                key=inspeksi_id,
                data=inspeksi_doc.model_dump(),
                admin_id=admin_id
            )
        
        # Get created inspeksi
        created_inspeksi = await db.inspeksi.find_one({"_id": result.inserted_id})
        
        # Convert untuk response
        inspeksi_response = InspeksiResponse(
            _id=str(created_inspeksi["_id"]),
            jadwal_id=created_inspeksi.get("jadwal_id"),
            data=[InspeksiDataItem(**item) for item in created_inspeksi["data"]],
            status=created_inspeksi["status"],
            admin_id=created_inspeksi["admin_id"],
            created_at=created_inspeksi["created_at"]
        )
        
        return create_response(
            success=True,
            message="Inspeksi berhasil dibuat",
            data=inspeksi_response.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membuat inspeksi: {str(e)}"
        )

@router.get("/", response_model=dict)
async def get_inspeksi_list(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    jadwal_id: Optional[str] = Query(None),
    current_admin: dict = Depends(get_current_admin)
):
    """Get list inspeksi dengan pagination dan filter"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Build query
        query = {"admin_id": admin_id}
        
        if status:
            allowed_statuses = ["draft", "generated", "saved"]
            if status not in allowed_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Status harus salah satu dari: {', '.join(allowed_statuses)}"
                )
            query["status"] = status
        
        if jadwal_id:
            if not ObjectId.is_valid(jadwal_id):
                raise HTTPException(status_code=400, detail="Invalid jadwal ID")
            query["jadwal_id"] = jadwal_id
        
        # Get total count
        total_count = await db.inspeksi.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        inspeksi_list = []
        
        async for inspeksi in db.inspeksi.find(query).sort("created_at", -1).skip(skip).limit(limit):
            inspeksi_response = InspeksiResponse(
                _id=str(inspeksi["_id"]),
                jadwal_id=inspeksi.get("jadwal_id"),
                data=[InspeksiDataItem(**item) for item in inspeksi["data"]],
                status=inspeksi["status"],
                admin_id=inspeksi["admin_id"],
                created_at=inspeksi["created_at"],
                updated_at=inspeksi.get("updated_at"),
                generated_at=inspeksi.get("generated_at"),
                saved_at=inspeksi.get("saved_at"),
                excel_file_path=inspeksi.get("excel_file_path")
            )
            inspeksi_list.append(inspeksi_response.model_dump())
        
        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit
        
        return create_response(
            success=True,
            message="List inspeksi berhasil diambil",
            data={
                "inspeksi": inspeksi_list,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_items": total_count,
                    "items_per_page": limit,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil list inspeksi: {str(e)}"
        )

@router.get("/{inspeksi_id}", response_model=dict)
async def get_inspeksi_detail(
    inspeksi_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Get detail inspeksi by ID"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(inspeksi_id):
            raise HTTPException(status_code=400, detail="Invalid inspeksi ID")
        
        # Get inspeksi
        inspeksi = await db.inspeksi.find_one({
            "_id": ObjectId(inspeksi_id),
            "admin_id": admin_id
        })
        
        if not inspeksi:
            raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan")
        
        # Convert untuk response
        inspeksi_response = InspeksiResponse(
            _id=str(inspeksi["_id"]),
            jadwal_id=inspeksi.get("jadwal_id"),
            data=[InspeksiDataItem(**item) for item in inspeksi["data"]],
            status=inspeksi["status"],
            admin_id=inspeksi["admin_id"],
            created_at=inspeksi["created_at"],
            updated_at=inspeksi.get("updated_at"),
            generated_at=inspeksi.get("generated_at"),
            saved_at=inspeksi.get("saved_at"),
            excel_file_path=inspeksi.get("excel_file_path")
        )
        
        return create_response(
            success=True,
            message="Detail inspeksi berhasil diambil",
            data=inspeksi_response.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil detail inspeksi: {str(e)}"
        )

@router.post("/{inspeksi_id}/generate", response_model=dict)
async def generate_coordinates(
    inspeksi_id: str,
    generate_data: GenerateRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Generate koordinat dari gambar menggunakan OCR"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(inspeksi_id):
            raise HTTPException(status_code=400, detail="Invalid inspeksi ID")
        
        # Get inspeksi
        inspeksi = await db.inspeksi.find_one({
            "_id": ObjectId(inspeksi_id),
            "admin_id": admin_id
        })
        
        if not inspeksi:
            raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan")
        
        # Validate image data
        image_valid, image_msg = validate_base64_image(generate_data.image_data)
        if not image_valid:
            raise HTTPException(status_code=400, detail=image_msg)
        
        # Validate item index
        if generate_data.item_index >= len(inspeksi["data"]):
            raise HTTPException(status_code=400, detail="Invalid item index")
        
        # Process image dengan OCR
        ocr_svc = get_ocr_service()
        ocr_result = ocr_svc.process_image(generate_data.image_data)
        
        if not ocr_result["success"]:
            return create_response(
                success=False,
                message="Gagal memproses gambar",
                error=ocr_result["error_message"]
            )
        
        # Validate koordinat jika berhasil diekstrak
        latitude = ocr_result["latitude"]
        longitude = ocr_result["longitude"]
        
        if latitude and longitude:
            lat_valid, lat_msg = validate_latitude_indonesia(latitude)
            if not lat_valid:
                return create_response(
                    success=False,
                    message=f"Koordinat tidak valid: {lat_msg}",
                    data=ocr_result
                )
            
            lon_valid, lon_msg = validate_longitude_indonesia(longitude)
            if not lon_valid:
                return create_response(
                    success=False,
                    message=f"Koordinat tidak valid: {lon_msg}",
                    data=ocr_result
                )
        
        # Save image dan update data inspeksi
        try:
            image_path = await save_base64_image(generate_data.image_data)
            
            # Update data item
            inspeksi["data"][generate_data.item_index]["latitude"] = latitude or ""
            inspeksi["data"][generate_data.item_index]["longitude"] = longitude or ""
            inspeksi["data"][generate_data.item_index]["image"] = generate_data.image_data
            inspeksi["data"][generate_data.item_index]["image_filename"] = image_path
            
            # Update inspeksi di database
            await db.inspeksi.update_one(
                {"_id": ObjectId(inspeksi_id)},
                {
                    "$set": {
                        "data": inspeksi["data"],
                        "status": "generated",
                        "generated_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Update cache
            cache_svc = get_cache_service()
            await cache_svc.set_cache(
                key=inspeksi_id,
                data=inspeksi,
                admin_id=admin_id
            )
            
            # Add to history
            history_doc = HistoryInDB(
                action_type="generate",
                inspeksi_id=inspeksi_id,
                jadwal_id=inspeksi.get("jadwal_id"),
                description=f"Generate koordinat untuk item {generate_data.item_index + 1}",
                admin_id=admin_id
            )
            await db.history.insert_one(history_doc.model_dump())
            
            return create_response(
                success=True,
                message="Koordinat berhasil di-generate",
                data={
                    "ocr_result": ocr_result,
                    "updated_item": inspeksi["data"][generate_data.item_index]
                }
            )
            
        except Exception as e:
            return create_response(
                success=False,
                message=f"Gagal menyimpan gambar: {str(e)}",
                data=ocr_result
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal generate koordinat: {str(e)}"
        )

@router.post("/{inspeksi_id}/save", response_model=dict)
async def save_inspeksi(
    inspeksi_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Save inspeksi dan generate Excel file"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(inspeksi_id):
            raise HTTPException(status_code=400, detail="Invalid inspeksi ID")
        
        # Get inspeksi
        inspeksi = await db.inspeksi.find_one({
            "_id": ObjectId(inspeksi_id),
            "admin_id": admin_id
        })
        
        if not inspeksi:
            raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan")
        
        if inspeksi["status"] == "saved":
            raise HTTPException(
                status_code=400,
                detail="Inspeksi sudah dalam status saved"
            )
        
        # Validate data sebelum save
        if not inspeksi["data"]:
            raise HTTPException(
                status_code=400,
                detail="Tidak ada data inspeksi untuk disimpan"
            )
        
        # Generate Excel file
        try:
            excel_svc = get_excel_service()
            excel_path = excel_svc.generate_excel(
                data=inspeksi["data"],
                admin_id=admin_id
            )
            
            # Update inspeksi status
            await db.inspeksi.update_one(
                {"_id": ObjectId(inspeksi_id)},
                {
                    "$set": {
                        "status": "saved",
                        "saved_at": datetime.utcnow(),
                        "excel_file_path": str(excel_path),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Clear cache
            cache_svc = get_cache_service()
            await cache_svc.delete_cache(inspeksi_id, admin_id)
            
            # Add to history
            history_doc = HistoryInDB(
                action_type="save",
                inspeksi_id=inspeksi_id,
                jadwal_id=inspeksi.get("jadwal_id"),
                data_snapshot=inspeksi,
                excel_file_path=str(excel_path),
                description="Inspeksi disimpan dan Excel di-generate",
                admin_id=admin_id
            )
            await db.history.insert_one(history_doc.model_dump())
            
            # Update jadwal status jika ada
            if inspeksi.get("jadwal_id"):
                await db.jadwal.update_one(
                    {"_id": ObjectId(inspeksi["jadwal_id"])},
                    {
                        "$set": {
                            "status": "completed",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
            
            return create_response(
                success=True,
                message="Inspeksi berhasil disimpan dan Excel di-generate",
                data={
                    "excel_file_path": str(excel_path),
                    "saved_at": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gagal generate Excel: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menyimpan inspeksi: {str(e)}"
        )

@router.put("/{inspeksi_id}", response_model=dict)
async def update_inspeksi(
    inspeksi_id: str,
    inspeksi_update: InspeksiUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update inspeksi data"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(inspeksi_id):
            raise HTTPException(status_code=400, detail="Invalid inspeksi ID")
        
        # Get existing inspeksi
        existing_inspeksi = await db.inspeksi.find_one({
            "_id": ObjectId(inspeksi_id),
            "admin_id": admin_id
        })
        
        if not existing_inspeksi:
            raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan")
        
        if existing_inspeksi["status"] == "saved":
            raise HTTPException(
                status_code=400,
                detail="Tidak dapat mengupdate inspeksi yang sudah disimpan"
            )
        
        # Prepare update data
        update_data = {}
        
        if inspeksi_update.jadwal_id is not None:
            if inspeksi_update.jadwal_id:
                if not ObjectId.is_valid(inspeksi_update.jadwal_id):
                    raise HTTPException(status_code=400, detail="Invalid jadwal ID")
                
                jadwal = await db.jadwal.find_one({
                    "_id": ObjectId(inspeksi_update.jadwal_id),
                    "admin_id": admin_id
                })
                
                if not jadwal:
                    raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
            
            update_data["jadwal_id"] = inspeksi_update.jadwal_id
        
        if inspeksi_update.data is not None:
            # Validasi data items
            for i, item in enumerate(inspeksi_update.data):
                if item.kondisi:
                    kondisi_valid, kondisi_msg = validate_kondisi(item.kondisi)
                    if not kondisi_valid:
                        raise HTTPException(status_code=400, detail=f"Item {i+1}: {kondisi_msg}")
                
                if item.jalur:
                    jalur_valid, jalur_msg = validate_jalur_name(item.jalur)
                    if not jalur_valid:
                        raise HTTPException(status_code=400, detail=f"Item {i+1}: {jalur_msg}")
                
                if item.keterangan:
                    keterangan_valid, keterangan_msg = validate_keterangan(item.keterangan)
                    if not keterangan_valid:
                        raise HTTPException(status_code=400, detail=f"Item {i+1}: {keterangan_msg}")
            
            update_data["data"] = [item.model_dump() for item in inspeksi_update.data]
        
        if inspeksi_update.status is not None:
            allowed_statuses = ["draft", "generated", "saved"]
            if inspeksi_update.status not in allowed_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Status harus salah satu dari: {', '.join(allowed_statuses)}"
                )
            update_data["status"] = inspeksi_update.status
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="Tidak ada data yang diupdate"
            )
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update inspeksi
        await db.inspeksi.update_one(
            {"_id": ObjectId(inspeksi_id)},
            {"$set": update_data}
        )
        
        # Update cache
        updated_inspeksi = await db.inspeksi.find_one({"_id": ObjectId(inspeksi_id)})
        cache_svc = get_cache_service()
        await cache_svc.set_cache(
            key=inspeksi_id,
            data=updated_inspeksi,
            admin_id=admin_id
        )
        
        # Convert untuk response
        inspeksi_response = InspeksiResponse(
            _id=str(updated_inspeksi["_id"]),
            jadwal_id=updated_inspeksi.get("jadwal_id"),
            data=[InspeksiDataItem(**item) for item in updated_inspeksi["data"]],
            status=updated_inspeksi["status"],
            admin_id=updated_inspeksi["admin_id"],
            created_at=updated_inspeksi["created_at"],
            updated_at=updated_inspeksi.get("updated_at"),
            generated_at=updated_inspeksi.get("generated_at"),
            saved_at=updated_inspeksi.get("saved_at"),
            excel_file_path=updated_inspeksi.get("excel_file_path")
        )
        
        return create_response(
            success=True,
            message="Inspeksi berhasil diupdate",
            data=inspeksi_response.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengupdate inspeksi: {str(e)}"
        )

@router.delete("/{inspeksi_id}", response_model=dict)
async def delete_inspeksi(
    inspeksi_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete inspeksi"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(inspeksi_id):
            raise HTTPException(status_code=400, detail="Invalid inspeksi ID")
        
        # Get existing inspeksi
        existing_inspeksi = await db.inspeksi.find_one({
            "_id": ObjectId(inspeksi_id),
            "admin_id": admin_id
        })
        
        if not existing_inspeksi:
            raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan")
        
        # Delete inspeksi
        result = await db.inspeksi.delete_one({"_id": ObjectId(inspeksi_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan")
        
        # Clear cache
        cache_svc = get_cache_service()
        await cache_svc.delete_cache(inspeksi_id, admin_id)
        
        # Add to history
        history_doc = HistoryInDB(
            action_type="delete",
            inspeksi_id=inspeksi_id,
            jadwal_id=existing_inspeksi.get("jadwal_id"),
            data_snapshot=existing_inspeksi,
            description="Inspeksi dihapus",
            admin_id=admin_id
        )
        await db.history.insert_one(history_doc.model_dump())
        
        return create_response(
            success=True,
            message="Inspeksi berhasil dihapus"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menghapus inspeksi: {str(e)}"
        )