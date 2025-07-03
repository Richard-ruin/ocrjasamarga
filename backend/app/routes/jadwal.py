# app/routes/jadwal.py
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

class JadwalCreate(BaseModel):
    nama_inspektur: str = Field(..., min_length=2, max_length=100)
    tanggal: date
    waktu: time
    alamat: str = Field(..., min_length=5, max_length=500)
    keterangan: Optional[str] = None
    status: str = Field(default="scheduled")  # scheduled, completed, cancelled

class JadwalUpdate(BaseModel):
    nama_inspektur: Optional[str] = None
    tanggal: Optional[date] = None
    waktu: Optional[time] = None
    alamat: Optional[str] = None
    keterangan: Optional[str] = None
    status: Optional[str] = None

class JadwalResponse(BaseModel):
    id: str = Field(alias="_id")
    nama_inspektur: str
    tanggal: str  # Changed to string for JSON compatibility
    waktu: str    # Changed to string for JSON compatibility
    alamat: str
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
    """Convert jadwal document for API response"""
    if isinstance(jadwal_doc.get("tanggal"), date):
        jadwal_doc["tanggal"] = jadwal_doc["tanggal"].isoformat()
    if isinstance(jadwal_doc.get("waktu"), time):
        jadwal_doc["waktu"] = jadwal_doc["waktu"].isoformat()
    return jadwal_doc

def convert_jadwal_for_storage(jadwal_data):
    """Convert jadwal data for MongoDB storage"""
    storage_data = jadwal_data.copy()
    
    # Convert date and time to strings for MongoDB storage
    if isinstance(storage_data.get("tanggal"), date):
        storage_data["tanggal"] = storage_data["tanggal"].isoformat()
    if isinstance(storage_data.get("waktu"), time):
        storage_data["waktu"] = storage_data["waktu"].isoformat()
        
    return storage_data

@router.get("/jadwal", response_model=List[JadwalResponse])
async def get_all_jadwal(current_admin: dict = Depends(get_current_admin)):
    """Ambil semua jadwal inspeksi"""
    try:
        jadwal_list = list(jadwal_collection.find({"admin_id": str(current_admin["_id"])}))
        
        # Convert ObjectId to string dan format tanggal
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
            detail=f"Failed to fetch jadwal: {str(e)}"
        )

@router.get("/jadwal/{jadwal_id}", response_model=JadwalResponse)
async def get_jadwal_by_id(
    jadwal_id: str, 
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil jadwal berdasarkan ID"""
    try:
        object_id = ObjectId(jadwal_id)
        jadwal = jadwal_collection.find_one({
            "_id": object_id,
            "admin_id": str(current_admin["_id"])
        })
        
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
            detail=f"Failed to fetch jadwal: {str(e)}"
        )

@router.post("/jadwal", response_model=JadwalResponse)
async def create_jadwal(
    jadwal_data: JadwalCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Buat jadwal inspeksi baru"""
    try:
        # Validasi status
        valid_status = ["scheduled", "completed", "cancelled"]
        if jadwal_data.status not in valid_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {valid_status}"
            )
        
        # Convert Pydantic model to dict
        jadwal_dict = jadwal_data.dict()
        
        # Buat document jadwal dengan konversi format
        jadwal_doc = {
            "nama_inspektur": jadwal_dict["nama_inspektur"],
            "tanggal": jadwal_dict["tanggal"].isoformat(),  # Convert to string
            "waktu": jadwal_dict["waktu"].isoformat(),      # Convert to string  
            "alamat": jadwal_dict["alamat"],
            "keterangan": jadwal_dict["keterangan"],
            "status": jadwal_dict["status"],
            "admin_id": str(current_admin["_id"]),
            "created_at": datetime.utcnow(),
            "updated_at": None
        }
        
        print(f"Saving jadwal document: {jadwal_doc}")  # Debug log
        
        # Simpan ke database
        result = jadwal_collection.insert_one(jadwal_doc)
        
        if result.inserted_id:
            # Ambil data yang baru disimpan
            saved_jadwal = jadwal_collection.find_one({"_id": result.inserted_id})
            saved_jadwal["_id"] = str(saved_jadwal["_id"])
            
            return saved_jadwal
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create jadwal"
            )
            
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating jadwal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create jadwal: {str(e)}"
        )

@router.put("/jadwal/{jadwal_id}", response_model=JadwalResponse)
async def update_jadwal(
    jadwal_id: str,
    jadwal_data: JadwalUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update jadwal inspeksi"""
    try:
        object_id = ObjectId(jadwal_id)
        
        # Cek apakah jadwal ada dan milik admin yang sedang login
        existing_jadwal = jadwal_collection.find_one({
            "_id": object_id,
            "admin_id": str(current_admin["_id"])
        })
        
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
                            detail=f"Status must be one of: {valid_status}"
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
        
        print(f"Updating jadwal with: {update_data}")  # Debug log
        
        # Update di database
        result = jadwal_collection.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            # Ambil data terbaru
            updated_jadwal = jadwal_collection.find_one({"_id": object_id})
            updated_jadwal["_id"] = str(updated_jadwal["_id"])
            return updated_jadwal
        else:
            # Mungkin tidak ada perubahan, return data existing
            existing_jadwal["_id"] = str(existing_jadwal["_id"])
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
            detail=f"Failed to update jadwal: {str(e)}"
        )

@router.delete("/jadwal/{jadwal_id}")
async def delete_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Hapus jadwal inspeksi"""
    try:
        object_id = ObjectId(jadwal_id)
        
        # Cek apakah jadwal ada dan milik admin yang sedang login
        existing_jadwal = jadwal_collection.find_one({
            "_id": object_id,
            "admin_id": str(current_admin["_id"])
        })
        
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
            detail=f"Failed to delete jadwal: {str(e)}"
        )

@router.get("/jadwal/status/{status}")
async def get_jadwal_by_status(
    status: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil jadwal berdasarkan status"""
    try:
        valid_status = ["scheduled", "completed", "cancelled"]
        if status not in valid_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {valid_status}"
            )
        
        jadwal_list = list(jadwal_collection.find({
            "admin_id": str(current_admin["_id"]),
            "status": status
        }))
        
        # Convert ObjectId to string dan format tanggal
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
            detail=f"Failed to fetch jadwal by status: {str(e)}"
        )

@router.get("/jadwal/today")
async def get_jadwal_today(current_admin: dict = Depends(get_current_admin)):
    """Ambil jadwal hari ini"""
    try:
        today = datetime.now().date().isoformat()  # Convert to string
        
        jadwal_list = list(jadwal_collection.find({
            "admin_id": str(current_admin["_id"]),
            "tanggal": today
        }))
        
        # Convert ObjectId to string dan format tanggal
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
            detail=f"Failed to fetch today's jadwal: {str(e)}"
        )