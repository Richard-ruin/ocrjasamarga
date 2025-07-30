# app/routes/jadwal.py - Fixed with proper error handling and auto ID generation
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime, date, time
from bson import ObjectId
from pydantic import BaseModel, Field, ValidationError

from app.routes.auth import get_current_admin
from app.config import db

router = APIRouter()

# Collections
jadwal_collection = db["jadwal"]
aset_collection = db["aset"]

class JadwalCreate(BaseModel):
    nama_inspektur: str = Field(..., min_length=2, max_length=100)
    tanggal: date
    waktu: time
    alamat: str = Field(..., min_length=5, max_length=500)
    id_aset: str = Field(..., min_length=1, max_length=50)
    keterangan: Optional[str] = None
    status: str = Field(default="scheduled")

class JadwalUpdate(BaseModel):
    nama_inspektur: Optional[str] = None
    tanggal: Optional[date] = None
    waktu: Optional[time] = None
    alamat: Optional[str] = None
    id_aset: Optional[str] = None
    keterangan: Optional[str] = None
    status: Optional[str] = None

class JadwalResponse(BaseModel):
    id: str = Field(alias="_id")
    nama_inspektur: str
    tanggal: str
    waktu: str
    alamat: str
    id_aset: str
    nama_aset: Optional[str] = None
    jenis_aset: Optional[str] = None
    lokasi_aset: Optional[str] = None
    keterangan: Optional[str] = None
    status: str
    admin_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

def convert_jadwal_for_response(jadwal_doc):
    """Convert jadwal document for API response with aset data"""
    if isinstance(jadwal_doc.get("tanggal"), date):
        jadwal_doc["tanggal"] = jadwal_doc["tanggal"].isoformat()
    if isinstance(jadwal_doc.get("waktu"), time):
        jadwal_doc["waktu"] = jadwal_doc["waktu"].isoformat()
    
    # Populate aset data if id_aset exists
    if "id_aset" in jadwal_doc and jadwal_doc["id_aset"]:
        aset_data = aset_collection.find_one({"id_aset": jadwal_doc["id_aset"]})
        if aset_data:
            jadwal_doc["nama_aset"] = aset_data.get("nama_aset")
            jadwal_doc["jenis_aset"] = aset_data.get("jenis_aset")
            jadwal_doc["lokasi_aset"] = aset_data.get("lokasi")
        else:
            jadwal_doc["nama_aset"] = None
            jadwal_doc["jenis_aset"] = None
            jadwal_doc["lokasi_aset"] = None
    
    return jadwal_doc

@router.get("/jadwal", response_model=List[JadwalResponse])
async def get_all_jadwal(current_admin: dict = Depends(get_current_admin)):
    """Ambil semua jadwal inspeksi dengan data aset"""
    try:
        # Petugas hanya bisa melihat jadwal mereka sendiri, admin bisa melihat semua
        if current_admin.get("role") == "admin":
            filter_query = {}
        else:
            filter_query = {"admin_id": str(current_admin["_id"])}
            
        jadwal_list = list(jadwal_collection.find(filter_query))
        
        # Convert ObjectId to string dan format tanggal + populate aset data
        result = []
        for jadwal in jadwal_list:
            jadwal["_id"] = str(jadwal["_id"])
            jadwal = convert_jadwal_for_response(jadwal)
            result.append(jadwal)
            
        return result
    except Exception as e:
        print(f"Error fetching jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch jadwal"
        )

@router.get("/jadwal/{jadwal_id}", response_model=JadwalResponse)
async def get_jadwal_by_id(
    jadwal_id: str, 
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil jadwal berdasarkan ID dengan data aset"""
    try:
        object_id = ObjectId(jadwal_id)
        
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": object_id}
        else:
            filter_query = {"_id": object_id, "admin_id": str(current_admin["_id"])}
            
        jadwal = jadwal_collection.find_one(filter_query)
        
        if not jadwal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        jadwal["_id"] = str(jadwal["_id"])
        jadwal = convert_jadwal_for_response(jadwal)
        return jadwal
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid jadwal ID format"
        )
    except Exception as e:
        print(f"Error fetching jadwal by ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch jadwal"
        )

@router.post("/jadwal", response_model=JadwalResponse)
async def create_jadwal(
    jadwal_data: JadwalCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Buat jadwal inspeksi baru dengan validasi aset"""
    try:
        # Validasi status
        valid_status = ["scheduled", "completed", "cancelled"]
        if jadwal_data.status not in valid_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {', '.join(valid_status)}"
            )
        
        # Validasi aset exists dan aktif
        aset_data = aset_collection.find_one({"id_aset": jadwal_data.id_aset})
        if not aset_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Aset dengan ID '{jadwal_data.id_aset}' tidak ditemukan"
            )
        
        if aset_data.get("status") != "aktif":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Aset '{jadwal_data.id_aset}' tidak aktif"
            )
        
        # Buat document jadwal
        jadwal_doc = {
            "nama_inspektur": jadwal_data.nama_inspektur,
            "tanggal": jadwal_data.tanggal.isoformat(),
            "waktu": jadwal_data.waktu.isoformat(),
            "alamat": jadwal_data.alamat,
            "id_aset": jadwal_data.id_aset,
            "keterangan": jadwal_data.keterangan,
            "status": jadwal_data.status,
            "admin_id": str(current_admin["_id"]),
            "created_at": datetime.utcnow(),
            "updated_at": None
        }
        
        print(f"Saving jadwal document: {jadwal_doc}")
        
        # Simpan ke database
        result = jadwal_collection.insert_one(jadwal_doc)
        
        if result.inserted_id:
            # Ambil data yang baru disimpan
            saved_jadwal = jadwal_collection.find_one({"_id": result.inserted_id})
            saved_jadwal["_id"] = str(saved_jadwal["_id"])
            saved_jadwal = convert_jadwal_for_response(saved_jadwal)
            
            return saved_jadwal
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create jadwal"
            )
            
    except HTTPException:
        raise
    except ValidationError as e:
        # Format ValidationError dengan benar
        print(f"Validation error: {e}")
        error_details = []
        for error in e.errors():
            error_details.append(f"{' -> '.join(str(x) for x in error['loc'])}: {error['msg']}")
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {'; '.join(error_details)}"
        )
    except Exception as e:
        print(f"Error creating jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create jadwal"
        )

@router.put("/jadwal/{jadwal_id}", response_model=JadwalResponse)
async def update_jadwal(
    jadwal_id: str,
    jadwal_data: JadwalUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update jadwal inspeksi dengan validasi aset"""
    try:
        object_id = ObjectId(jadwal_id)
        
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": object_id}
        else:
            filter_query = {"_id": object_id, "admin_id": str(current_admin["_id"])}
        
        # Cek apakah jadwal ada dan milik admin yang sedang login
        existing_jadwal = jadwal_collection.find_one(filter_query)
        
        if not existing_jadwal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        # Siapkan data update (hanya field yang tidak None)
        update_data = {}
        jadwal_dict = jadwal_data.dict(exclude_unset=True)
        
        for key, value in jadwal_dict.items():
            if value is not None:
                if key == "tanggal" and isinstance(value, date):
                    update_data[key] = value.isoformat()
                elif key == "waktu" and isinstance(value, time):
                    update_data[key] = value.isoformat()
                elif key == "status":
                    # Validasi status
                    valid_status = ["scheduled", "completed", "cancelled"]
                    if value not in valid_status:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Status must be one of: {', '.join(valid_status)}"
                        )
                    update_data[key] = value
                elif key == "id_aset":
                    # Validasi aset exists dan aktif
                    aset_data = aset_collection.find_one({"id_aset": value})
                    if not aset_data:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Aset dengan ID '{value}' tidak ditemukan"
                        )
                    
                    if aset_data.get("status") != "aktif":
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Aset '{value}' tidak aktif"
                        )
                    update_data[key] = value
                else:
                    update_data[key] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided for update"
            )
        
        # Tambahkan updated_at
        update_data["updated_at"] = datetime.utcnow()
        
        # Update di database
        result = jadwal_collection.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            # Ambil data terbaru
            updated_jadwal = jadwal_collection.find_one({"_id": object_id})
            updated_jadwal["_id"] = str(updated_jadwal["_id"])
            updated_jadwal = convert_jadwal_for_response(updated_jadwal)
            return updated_jadwal
        else:
            # Mungkin tidak ada perubahan, return data existing
            existing_jadwal["_id"] = str(existing_jadwal["_id"])
            existing_jadwal = convert_jadwal_for_response(existing_jadwal)
            return existing_jadwal
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid jadwal ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update jadwal"
        )

@router.delete("/jadwal/{jadwal_id}")
async def delete_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Hapus jadwal inspeksi"""
    try:
        object_id = ObjectId(jadwal_id)
        
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": object_id}
        else:
            filter_query = {"_id": object_id, "admin_id": str(current_admin["_id"])}
        
        # Cek apakah jadwal ada dan milik admin yang sedang login
        existing_jadwal = jadwal_collection.find_one(filter_query)
        
        if not existing_jadwal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jadwal not found"
            )
        
        # Hapus dari database
        result = jadwal_collection.delete_one({"_id": object_id})
        
        if result.deleted_count > 0:
            return {"message": "Jadwal berhasil dihapus"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete jadwal"
            )
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid jadwal ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete jadwal"
        )

@router.get("/jadwal/status/{status}")
async def get_jadwal_by_status(
    status: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil jadwal berdasarkan status dengan data aset"""
    try:
        valid_status = ["scheduled", "completed", "cancelled"]
        if status not in valid_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {', '.join(valid_status)}"
            )
        
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"status": status}
        else:
            filter_query = {"admin_id": str(current_admin["_id"]), "status": status}
        
        jadwal_list = list(jadwal_collection.find(filter_query))
        
        # Convert ObjectId to string dan format tanggal + populate aset data
        result = []
        for jadwal in jadwal_list:
            jadwal["_id"] = str(jadwal["_id"])
            jadwal = convert_jadwal_for_response(jadwal)
            result.append(jadwal)
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching jadwal by status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch jadwal by status"
        )

@router.get("/jadwal/today")
async def get_jadwal_today(current_admin: dict = Depends(get_current_admin)):
    """Ambil jadwal hari ini dengan data aset"""
    try:
        today = datetime.now().date().isoformat()
        
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"tanggal": today}
        else:
            filter_query = {"admin_id": str(current_admin["_id"]), "tanggal": today}
        
        jadwal_list = list(jadwal_collection.find(filter_query))
        
        # Convert ObjectId to string dan format tanggal + populate aset data
        result = []
        for jadwal in jadwal_list:
            jadwal["_id"] = str(jadwal["_id"])
            jadwal = convert_jadwal_for_response(jadwal)
            result.append(jadwal)
            
        return result
        
    except Exception as e:
        print(f"Error fetching today's jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch today's jadwal"
        )

@router.get("/jadwal/aset/{id_aset}")
async def get_jadwal_by_aset(
    id_aset: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil jadwal berdasarkan ID aset"""
    try:
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"id_aset": id_aset}
        else:
            filter_query = {"admin_id": str(current_admin["_id"]), "id_aset": id_aset}
        
        jadwal_list = list(jadwal_collection.find(filter_query))
        
        # Convert ObjectId to string dan format tanggal + populate aset data
        result = []
        for jadwal in jadwal_list:
            jadwal["_id"] = str(jadwal["_id"])
            jadwal = convert_jadwal_for_response(jadwal)
            result.append(jadwal)
            
        return result
        
    except Exception as e:
        print(f"Error fetching jadwal by aset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch jadwal by aset"
        )

@router.get("/jadwal/stats")
async def get_jadwal_stats(current_admin: dict = Depends(get_current_admin)):
    """Dapatkan statistik jadwal"""
    try:
        # Build filter berdasarkan role
        if current_admin.get("role") == "admin":
            base_filter = {}
        else:
            base_filter = {"admin_id": str(current_admin["_id"])}
        
        total_jadwal = jadwal_collection.count_documents(base_filter)
        scheduled = jadwal_collection.count_documents({**base_filter, "status": "scheduled"})
        completed = jadwal_collection.count_documents({**base_filter, "status": "completed"})
        cancelled = jadwal_collection.count_documents({**base_filter, "status": "cancelled"})
        
        # Jadwal hari ini
        today = datetime.now().date().isoformat()
        today_jadwal = jadwal_collection.count_documents({**base_filter, "tanggal": today})
        
        # Jadwal bulan ini
        current_month = datetime.now().strftime("%Y-%m")
        month_jadwal = jadwal_collection.count_documents({
            **base_filter,
            "tanggal": {"$regex": f"^{current_month}"}
        })
        
        return {
            "total_jadwal": total_jadwal,
            "status_breakdown": {
                "scheduled": scheduled,
                "completed": completed,
                "cancelled": cancelled
            },
            "today_jadwal": today_jadwal,
            "month_jadwal": month_jadwal,
            "completion_rate": (completed / total_jadwal * 100) if total_jadwal > 0 else 0
        }
        
    except Exception as e:
        print(f"Error getting jadwal stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get jadwal stats"
        )