from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime, date
from bson import ObjectId

from ..auth.auth import get_current_admin
from ..models.jadwal import JadwalCreate, JadwalUpdate, JadwalResponse, JadwalInDB
from ..database import get_database
from ..utils.helpers import create_response, convert_objectid_to_str, paginate_results
from ..utils.validators import validate_alamat, validate_full_name, validate_date_range, validate_time_format, validate_status

router = APIRouter(prefix="/jadwal", tags=["Jadwal"])

@router.post("/", response_model=dict)
async def create_jadwal(
    jadwal_data: JadwalCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Create jadwal inspeksi baru"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validasi input
        name_valid, name_msg = validate_full_name(jadwal_data.nama_inspektur)
        if not name_valid:
            raise HTTPException(status_code=400, detail=name_msg)
        
        alamat_valid, alamat_msg = validate_alamat(jadwal_data.alamat)
        if not alamat_valid:
            raise HTTPException(status_code=400, detail=alamat_msg)
        
        time_valid, time_msg = validate_time_format(jadwal_data.waktu.isoformat())
        if not time_valid:
            raise HTTPException(status_code=400, detail=time_msg)
        
        # Validasi tanggal tidak boleh di masa lalu
        if jadwal_data.tanggal < date.today():
            raise HTTPException(
                status_code=400,
                detail="Tanggal jadwal tidak boleh di masa lalu"
            )
        
        # Check duplikasi jadwal pada tanggal dan waktu yang sama untuk admin
        existing_jadwal = await db.jadwal.find_one({
            "admin_id": admin_id,
            "tanggal": jadwal_data.tanggal,
            "waktu": jadwal_data.waktu.isoformat()
        })
        
        if existing_jadwal:
            raise HTTPException(
                status_code=400,
                detail="Sudah ada jadwal pada tanggal dan waktu tersebut"
            )
        
        # Create jadwal document
        jadwal_doc = JadwalInDB(
            nama_inspektur=jadwal_data.nama_inspektur,
            tanggal=jadwal_data.tanggal,
            waktu=jadwal_data.waktu,
            alamat=jadwal_data.alamat,
            keterangan=jadwal_data.keterangan,
            status=jadwal_data.status,
            admin_id=admin_id
        )
        
        # Insert to database
        result = await db.jadwal.insert_one(jadwal_doc.model_dump())
        
        # Get created jadwal
        created_jadwal = await db.jadwal.find_one({"_id": result.inserted_id})
        
        # Convert untuk response
        jadwal_response = JadwalResponse(
            _id=str(created_jadwal["_id"]),
            nama_inspektur=created_jadwal["nama_inspektur"],
            tanggal=created_jadwal["tanggal"],
            waktu=created_jadwal["waktu"],
            alamat=created_jadwal["alamat"],
            keterangan=created_jadwal.get("keterangan"),
            status=created_jadwal["status"],
            admin_id=created_jadwal["admin_id"],
            created_at=created_jadwal["created_at"]
        )
        
        return create_response(
            success=True,
            message="Jadwal berhasil dibuat",
            data=jadwal_response.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membuat jadwal: {str(e)}"
        )

@router.get("/", response_model=dict)
async def get_jadwal_list(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    current_admin: dict = Depends(get_current_admin)
):
    """Get list jadwal dengan pagination dan filter"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Build query
        query = {"admin_id": admin_id}
        
        # Filter by status
        if status:
            allowed_statuses = ["scheduled", "completed", "cancelled"]
            status_valid, status_msg = validate_status(status, allowed_statuses)
            if not status_valid:
                raise HTTPException(status_code=400, detail=status_msg)
            query["status"] = status
        
        # Filter by date range
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            
            if start_date and end_date:
                date_valid, date_msg = validate_date_range(start_date, end_date)
                if not date_valid:
                    raise HTTPException(status_code=400, detail=date_msg)
            
            query["tanggal"] = date_filter
        
        # Search in nama_inspektur or alamat
        if search:
            query["$or"] = [
                {"nama_inspektur": {"$regex": search, "$options": "i"}},
                {"alamat": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total_count = await db.jadwal.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        jadwal_list = []
        
        async for jadwal in db.jadwal.find(query).sort("tanggal", -1).skip(skip).limit(limit):
            jadwal_response = JadwalResponse(
                _id=str(jadwal["_id"]),
                nama_inspektur=jadwal["nama_inspektur"],
                tanggal=jadwal["tanggal"],
                waktu=jadwal["waktu"],
                alamat=jadwal["alamat"],
                keterangan=jadwal.get("keterangan"),
                status=jadwal["status"],
                admin_id=jadwal["admin_id"],
                created_at=jadwal["created_at"],
                updated_at=jadwal.get("updated_at")
            )
            jadwal_list.append(jadwal_response.model_dump())
        
        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit
        
        return create_response(
            success=True,
            message="List jadwal berhasil diambil",
            data={
                "jadwal": jadwal_list,
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
            detail=f"Gagal mengambil list jadwal: {str(e)}"
        )

@router.get("/{jadwal_id}", response_model=dict)
async def get_jadwal_detail(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Get detail jadwal by ID"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(jadwal_id):
            raise HTTPException(status_code=400, detail="Invalid jadwal ID")
        
        # Get jadwal
        jadwal = await db.jadwal.find_one({
            "_id": ObjectId(jadwal_id),
            "admin_id": admin_id
        })
        
        if not jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Convert untuk response
        jadwal_response = JadwalResponse(
            _id=str(jadwal["_id"]),
            nama_inspektur=jadwal["nama_inspektur"],
            tanggal=jadwal["tanggal"],
            waktu=jadwal["waktu"],
            alamat=jadwal["alamat"],
            keterangan=jadwal.get("keterangan"),
            status=jadwal["status"],
            admin_id=jadwal["admin_id"],
            created_at=jadwal["created_at"],
            updated_at=jadwal.get("updated_at")
        )
        
        return create_response(
            success=True,
            message="Detail jadwal berhasil diambil",
            data=jadwal_response.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil detail jadwal: {str(e)}"
        )

@router.put("/{jadwal_id}", response_model=dict)
async def update_jadwal(
    jadwal_id: str,
    jadwal_update: JadwalUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update jadwal by ID"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(jadwal_id):
            raise HTTPException(status_code=400, detail="Invalid jadwal ID")
        
        # Check if jadwal exists and belongs to admin
        existing_jadwal = await db.jadwal.find_one({
            "_id": ObjectId(jadwal_id),
            "admin_id": admin_id
        })
        
        if not existing_jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Prepare update data
        update_data = {}
        
        # Validasi dan update fields yang diberikan
        if jadwal_update.nama_inspektur is not None:
            name_valid, name_msg = validate_full_name(jadwal_update.nama_inspektur)
            if not name_valid:
                raise HTTPException(status_code=400, detail=name_msg)
            update_data["nama_inspektur"] = jadwal_update.nama_inspektur
        
        if jadwal_update.alamat is not None:
            alamat_valid, alamat_msg = validate_alamat(jadwal_update.alamat)
            if not alamat_valid:
                raise HTTPException(status_code=400, detail=alamat_msg)
            update_data["alamat"] = jadwal_update.alamat
        
        if jadwal_update.tanggal is not None:
            if jadwal_update.tanggal < date.today():
                raise HTTPException(
                    status_code=400,
                    detail="Tanggal jadwal tidak boleh di masa lalu"
                )
            update_data["tanggal"] = jadwal_update.tanggal
        
        if jadwal_update.waktu is not None:
            time_valid, time_msg = validate_time_format(jadwal_update.waktu.isoformat())
            if not time_valid:
                raise HTTPException(status_code=400, detail=time_msg)
            update_data["waktu"] = jadwal_update.waktu
        
        if jadwal_update.status is not None:
            allowed_statuses = ["scheduled", "completed", "cancelled"]
            status_valid, status_msg = validate_status(jadwal_update.status, allowed_statuses)
            if not status_valid:
                raise HTTPException(status_code=400, detail=status_msg)
            update_data["status"] = jadwal_update.status
        
        if jadwal_update.keterangan is not None:
            update_data["keterangan"] = jadwal_update.keterangan
        
        # Check duplikasi jika tanggal atau waktu diubah
        if "tanggal" in update_data or "waktu" in update_data:
            check_tanggal = update_data.get("tanggal", existing_jadwal["tanggal"])
            check_waktu = update_data.get("waktu", existing_jadwal["waktu"])
            
            duplicate_jadwal = await db.jadwal.find_one({
                "_id": {"$ne": ObjectId(jadwal_id)},
                "admin_id": admin_id,
                "tanggal": check_tanggal,
                "waktu": check_waktu.isoformat() if hasattr(check_waktu, 'isoformat') else check_waktu
            })
            
            if duplicate_jadwal:
                raise HTTPException(
                    status_code=400,
                    detail="Sudah ada jadwal pada tanggal dan waktu tersebut"
                )
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="Tidak ada data yang diupdate"
            )
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update jadwal
        await db.jadwal.update_one(
            {"_id": ObjectId(jadwal_id)},
            {"$set": update_data}
        )
        
        # Get updated jadwal
        updated_jadwal = await db.jadwal.find_one({"_id": ObjectId(jadwal_id)})
        
        # Convert untuk response
        jadwal_response = JadwalResponse(
            _id=str(updated_jadwal["_id"]),
            nama_inspektur=updated_jadwal["nama_inspektur"],
            tanggal=updated_jadwal["tanggal"],
            waktu=updated_jadwal["waktu"],
            alamat=updated_jadwal["alamat"],
            keterangan=updated_jadwal.get("keterangan"),
            status=updated_jadwal["status"],
            admin_id=updated_jadwal["admin_id"],
            created_at=updated_jadwal["created_at"],
            updated_at=updated_jadwal.get("updated_at")
        )
        
        return create_response(
            success=True,
            message="Jadwal berhasil diupdate",
            data=jadwal_response.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengupdate jadwal: {str(e)}"
        )

@router.delete("/{jadwal_id}", response_model=dict)
async def delete_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete jadwal by ID"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(jadwal_id):
            raise HTTPException(status_code=400, detail="Invalid jadwal ID")
        
        # Check if jadwal exists and belongs to admin
        existing_jadwal = await db.jadwal.find_one({
            "_id": ObjectId(jadwal_id),
            "admin_id": admin_id
        })
        
        if not existing_jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Check if there are inspeksi linked to this jadwal
        linked_inspeksi = await db.inspeksi.find_one({"jadwal_id": jadwal_id})
        if linked_inspeksi:
            raise HTTPException(
                status_code=400,
                detail="Tidak dapat menghapus jadwal yang sudah memiliki data inspeksi"
            )
        
        # Delete jadwal
        result = await db.jadwal.delete_one({"_id": ObjectId(jadwal_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        return create_response(
            success=True,
            message="Jadwal berhasil dihapus"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menghapus jadwal: {str(e)}"
        )

@router.get("/upcoming/list", response_model=dict)
async def get_upcoming_jadwal(
    limit: int = Query(5, ge=1, le=20),
    current_admin: dict = Depends(get_current_admin)
):
    """Get upcoming jadwal (jadwal yang akan datang)"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Get jadwal yang tanggalnya >= hari ini dan status scheduled
        today = date.today()
        
        jadwal_list = []
        async for jadwal in db.jadwal.find({
            "admin_id": admin_id,
            "tanggal": {"$gte": today},
            "status": "scheduled"
        }).sort("tanggal", 1).limit(limit):
            jadwal_response = JadwalResponse(
                _id=str(jadwal["_id"]),
                nama_inspektur=jadwal["nama_inspektur"],
                tanggal=jadwal["tanggal"],
                waktu=jadwal["waktu"],
                alamat=jadwal["alamat"],
                keterangan=jadwal.get("keterangan"),
                status=jadwal["status"],
                admin_id=jadwal["admin_id"],
                created_at=jadwal["created_at"],
                updated_at=jadwal.get("updated_at")
            )
            jadwal_list.append(jadwal_response.model_dump())
        
        return create_response(
            success=True,
            message="Upcoming jadwal berhasil diambil",
            data=jadwal_list
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil upcoming jadwal: {str(e)}"
        )

@router.post("/{jadwal_id}/complete", response_model=dict)
async def complete_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Mark jadwal as completed"""
    try:
        db = get_database()
        admin_id = str(current_admin["_id"])
        
        # Validate ObjectId
        if not ObjectId.is_valid(jadwal_id):
            raise HTTPException(status_code=400, detail="Invalid jadwal ID")
        
        # Check if jadwal exists and belongs to admin
        existing_jadwal = await db.jadwal.find_one({
            "_id": ObjectId(jadwal_id),
            "admin_id": admin_id
        })
        
        if not existing_jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        if existing_jadwal["status"] == "completed":
            raise HTTPException(
                status_code=400,
                detail="Jadwal sudah dalam status completed"
            )
        
        # Update status to completed
        await db.jadwal.update_one(
            {"_id": ObjectId(jadwal_id)},
            {
                "$set": {
                    "status": "completed",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return create_response(
            success=True,
            message="Jadwal berhasil ditandai sebagai completed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengupdate status jadwal: {str(e)}"
        )