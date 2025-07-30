# app/routes/aset.py - Kelola Aset Management
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field, ValidationError

from app.routes.auth import get_current_admin
from app.config import db

router = APIRouter()

# Collections
aset_collection = db["aset"]

class AsetCreate(BaseModel):
    id_aset: str = Field(..., min_length=1, max_length=50)
    jenis_aset: str = Field(..., min_length=2, max_length=100)
    lokasi: str = Field(..., min_length=3, max_length=200)
    nama_aset: str = Field(..., min_length=2, max_length=150)
    status: str = Field(default="aktif")  # aktif, non-aktif, maintenance

class AsetUpdate(BaseModel):
    id_aset: Optional[str] = None
    jenis_aset: Optional[str] = None
    lokasi: Optional[str] = None
    nama_aset: Optional[str] = None
    status: Optional[str] = None

class AsetResponse(BaseModel):
    id: str = Field(alias="_id")
    id_aset: str
    jenis_aset: str
    lokasi: str
    nama_aset: str
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

class AsetListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    data: List[AsetResponse]

@router.get("/aset", response_model=List[AsetResponse])
async def get_all_aset(current_admin: dict = Depends(get_current_admin)):
    """Ambil semua aset"""
    try:
        aset_list = list(aset_collection.find({}))
        
        # Convert ObjectId to string
        result = []
        for aset in aset_list:
            aset["_id"] = str(aset["_id"])
            result.append(aset)
            
        return result
    except Exception as e:
        print(f"Error fetching aset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aset: {str(e)}"
        )

@router.get("/aset/paginated", response_model=AsetListResponse)
async def get_aset_paginated(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    jenis_filter: Optional[str] = Query(None),
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil aset dengan pagination dan filter"""
    try:
        # Build filter query
        filter_query = {}
        
        if search:
            filter_query["$or"] = [
                {"id_aset": {"$regex": search, "$options": "i"}},
                {"nama_aset": {"$regex": search, "$options": "i"}},
                {"lokasi": {"$regex": search, "$options": "i"}},
                {"jenis_aset": {"$regex": search, "$options": "i"}}
            ]
        
        if status_filter:
            filter_query["status"] = status_filter
            
        if jenis_filter:
            filter_query["jenis_aset"] = {"$regex": jenis_filter, "$options": "i"}
        
        # Hitung total
        total = aset_collection.count_documents(filter_query)
        
        # Hitung pagination
        skip = (page - 1) * per_page
        total_pages = (total + per_page - 1) // per_page
        
        # Ambil data
        cursor = aset_collection.find(filter_query).skip(skip).limit(per_page).sort("created_at", -1)
        aset_list = []
        
        for aset in cursor:
            aset["_id"] = str(aset["_id"])
            aset_list.append(aset)
        
        return AsetListResponse(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=aset_list
        )
        
    except Exception as e:
        print(f"Error fetching paginated aset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aset: {str(e)}"
        )

@router.get("/aset/{aset_id}", response_model=AsetResponse)
async def get_aset_by_id(
    aset_id: str, 
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil aset berdasarkan ID"""
    try:
        object_id = ObjectId(aset_id)
        aset = aset_collection.find_one({"_id": object_id})
        
        if not aset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aset not found"
            )
        
        aset["_id"] = str(aset["_id"])
        return aset
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid aset ID format"
        )
    except Exception as e:
        print(f"Error fetching aset by ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aset: {str(e)}"
        )

@router.post("/aset", response_model=AsetResponse)
async def create_aset(
    aset_data: AsetCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Buat aset baru"""
    try:
        # Validasi status
        valid_status = ["aktif", "non-aktif", "maintenance"]
        if aset_data.status not in valid_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {valid_status}"
            )
        
        # Cek apakah ID aset sudah ada
        existing_aset = aset_collection.find_one({"id_aset": aset_data.id_aset})
        if existing_aset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID Aset sudah digunakan"
            )
        
        # Convert Pydantic model to dict
        aset_dict = aset_data.dict()
        
        # Buat document aset
        aset_doc = {
            "id_aset": aset_dict["id_aset"],
            "jenis_aset": aset_dict["jenis_aset"],
            "lokasi": aset_dict["lokasi"],
            "nama_aset": aset_dict["nama_aset"],
            "status": aset_dict["status"],
            "admin_id": str(current_admin["_id"]),
            "created_at": datetime.utcnow(),
            "updated_at": None
        }
        
        print(f"Saving aset document: {aset_doc}")  # Debug log
        
        # Simpan ke database
        result = aset_collection.insert_one(aset_doc)
        
        if result.inserted_id:
            # Ambil data yang baru disimpan
            saved_aset = aset_collection.find_one({"_id": result.inserted_id})
            saved_aset["_id"] = str(saved_aset["_id"])
            
            return saved_aset
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create aset"
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
        print(f"Error creating aset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create aset: {str(e)}"
        )

@router.put("/aset/{aset_id}", response_model=AsetResponse)
async def update_aset(
    aset_id: str,
    aset_data: AsetUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update aset"""
    try:
        object_id = ObjectId(aset_id)
        
        # Cek apakah aset ada
        existing_aset = aset_collection.find_one({"_id": object_id})
        
        if not existing_aset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aset not found"
            )
        
        # Siapkan data update (hanya field yang tidak None)
        update_data = {}
        aset_dict = aset_data.dict(exclude_unset=True)
        
        for key, value in aset_dict.items():
            if value is not None:
                if key == "status":
                    # Validasi status
                    valid_status = ["aktif", "non-aktif", "maintenance"]
                    if value not in valid_status:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Status must be one of: {valid_status}"
                        )
                    update_data[key] = value
                elif key == "id_aset":
                    # Cek apakah ID aset sudah digunakan aset lain
                    existing_with_id = aset_collection.find_one({"id_aset": value})
                    if existing_with_id and str(existing_with_id["_id"]) != aset_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="ID Aset sudah digunakan"
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
        
        print(f"Updating aset with: {update_data}")  # Debug log
        
        # Update di database
        result = aset_collection.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            # Ambil data terbaru
            updated_aset = aset_collection.find_one({"_id": object_id})
            updated_aset["_id"] = str(updated_aset["_id"])
            return updated_aset
        else:
            # Mungkin tidak ada perubahan, return data existing
            existing_aset["_id"] = str(existing_aset["_id"])
            return existing_aset
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid aset ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating aset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update aset: {str(e)}"
        )

@router.delete("/aset/{aset_id}")
async def delete_aset(
    aset_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Hapus aset"""
    try:
        object_id = ObjectId(aset_id)
        
        # Cek apakah aset ada
        existing_aset = aset_collection.find_one({"_id": object_id})
        
        if not existing_aset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aset not found"
            )
        
        # Cek apakah aset digunakan di jadwal
        from app.routes.jadwal import jadwal_collection
        jadwal_using_aset = jadwal_collection.find_one({"id_aset": existing_aset["id_aset"]})
        if jadwal_using_aset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aset sedang digunakan dalam jadwal, tidak dapat dihapus"
            )
        
        # Hapus dari database
        result = aset_collection.delete_one({"_id": object_id})
        
        if result.deleted_count > 0:
            return {"message": "Aset berhasil dihapus"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete aset"
            )
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid aset ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting aset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete aset: {str(e)}"
        )

@router.get("/aset/status/{status}")
async def get_aset_by_status(
    status: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil aset berdasarkan status"""
    try:
        valid_status = ["aktif", "non-aktif", "maintenance"]
        if status not in valid_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {valid_status}"
            )
        
        aset_list = list(aset_collection.find({"status": status}))
        
        # Convert ObjectId to string
        result = []
        for aset in aset_list:
            aset["_id"] = str(aset["_id"])
            result.append(aset)
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching aset by status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aset by status: {str(e)}"
        )

@router.get("/aset/jenis/{jenis}")
async def get_aset_by_jenis(
    jenis: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil aset berdasarkan jenis"""
    try:
        aset_list = list(aset_collection.find({
            "jenis_aset": {"$regex": jenis, "$options": "i"}
        }))
        
        # Convert ObjectId to string
        result = []
        for aset in aset_list:
            aset["_id"] = str(aset["_id"])
            result.append(aset)
            
        return result
        
    except Exception as e:
        print(f"Error fetching aset by jenis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aset by jenis: {str(e)}"
        )

@router.get("/aset/stats")
async def get_aset_stats(current_admin: dict = Depends(get_current_admin)):
    """Dapatkan statistik aset"""
    try:
        total_aset = aset_collection.count_documents({})
        aktif = aset_collection.count_documents({"status": "aktif"})
        non_aktif = aset_collection.count_documents({"status": "non-aktif"})
        maintenance = aset_collection.count_documents({"status": "maintenance"})
        
        # Hitung jenis aset
        pipeline = [
            {"$group": {"_id": "$jenis_aset", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        jenis_stats = list(aset_collection.aggregate(pipeline))
        
        return {
            "total_aset": total_aset,
            "status_breakdown": {
                "aktif": aktif,
                "non_aktif": non_aktif,
                "maintenance": maintenance
            },
            "jenis_breakdown": jenis_stats,
            "status_percentage": {
                "aktif": (aktif / total_aset * 100) if total_aset > 0 else 0,
                "non_aktif": (non_aktif / total_aset * 100) if total_aset > 0 else 0,
                "maintenance": (maintenance / total_aset * 100) if total_aset > 0 else 0
            }
        }
        
    except Exception as e:
        print(f"Error getting aset stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aset stats: {str(e)}"
        )