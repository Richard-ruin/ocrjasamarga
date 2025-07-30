# app/routes/inspeksi.py - Complete implementation with jadwal-based workflow
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
from pathlib import Path
import shutil, uuid
import json
import logging
from datetime import datetime

# Import services yang sudah diperbaiki dengan Tesseract
from app.services.ocr_service import extract_coordinates_from_image, get_extractor, EnhancedTesseractExtractor
from app.services.excel_service import generate_excel
from app.ocr_config import CoordinateOCRConfig, enhance_image_for_coordinates, is_coordinate_in_indonesia, extract_coordinates_from_text
from app.config import db
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR
from app.routes.auth import get_current_admin
from fastapi.responses import FileResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Collections
temp_collection = db["temp_entries"]
history_collection = db["saved_tables"]
jadwal_collection = db["jadwal"]
aset_collection = db["aset"]

# Inisialisasi OCR config dengan Tesseract
ocr_config = CoordinateOCRConfig()

def extract_coordinates_with_validation(image_path: str) -> tuple[str, str]:
    """
    Ekstrak koordinat dengan multiple validation dan enhancement menggunakan Tesseract
    """
    try:
        logger.info(f"Extracting coordinates from: {image_path}")
        
        # Get extractor instance
        extractor = get_extractor()
        
        # Step 1: Multiple enhancement attempts
        coordinates_attempts = []
        
        # Attempt 1: Direct extraction dengan extractor
        try:
            lat1, lon1 = extractor.extract_coordinates_from_image(image_path)
            if lat1 and lon1:
                coordinates_attempts.append((lat1, lon1, "enhanced_tesseract"))
                logger.debug(f"Enhanced Tesseract result: {lat1}, {lon1}")
        except Exception as e:
            logger.debug(f"Enhanced Tesseract failed: {e}")
        
        # Attempt 2: OCR dengan enhanced image
        try:
            enhanced_path = enhance_image_for_coordinates(image_path)
            if enhanced_path != image_path:
                lat2, lon2 = extractor.extract_coordinates_from_image(enhanced_path)
                if lat2 and lon2:
                    coordinates_attempts.append((lat2, lon2, "enhanced_image"))
                    logger.debug(f"Enhanced image result: {lat2}, {lon2}")
        except Exception as e:
            logger.debug(f"Enhanced image OCR failed: {e}")
        
        # Attempt 3: OCR dengan konfigurasi yang dioptimalkan
        try:
            optimized_result = ocr_config.read_coordinates_optimized(image_path)
            if optimized_result:
                for text_optimized in optimized_result:
                    coords = extract_coordinates_from_text(text_optimized)
                    if coords:
                        lat3, lon3 = coords['latitude'], coords['longitude']
                        coordinates_attempts.append((lat3, lon3, "optimized_config"))
                        logger.debug(f"Optimized config result: {lat3}, {lon3}")
                        break
        except Exception as e:
            logger.debug(f"Optimized config OCR failed: {e}")
        
        # Step 2: Pilih hasil terbaik berdasarkan prioritas dan validasi
        if coordinates_attempts:
            # Prioritas: enhanced_tesseract > enhanced_image > optimized_config
            priority_order = ["enhanced_tesseract", "enhanced_image", "optimized_config"]
            
            # Cari koordinat yang valid untuk wilayah Indonesia
            for method in priority_order:
                for lat, lon, source in coordinates_attempts:
                    if source == method:
                        if is_coordinate_in_indonesia(lat, lon):
                            logger.info(f"Selected valid coordinates from {source}: {lat}, {lon}")
                            return lat, lon
                        else:
                            logger.warning(f"Coordinates from {source} outside Indonesia: {lat}, {lon}")
            
            # Jika tidak ada yang valid untuk Indonesia, ambil yang pertama
            lat, lon, source = coordinates_attempts[0]
            logger.info(f"Selected coordinates (fallback) from {source}: {lat}, {lon}")
            return lat, lon
        
        logger.warning(f"No coordinates found in image: {image_path}")
        return "", ""
        
    except Exception as e:
        logger.error(f"Error in extract_coordinates_with_validation: {e}")
        return "", ""

# 🆕 ENDPOINT BARU: Daftar Jadwal untuk Inspeksi
@router.get("/inspeksi/jadwal")
async def get_jadwal_for_inspeksi(current_admin: dict = Depends(get_current_admin)):
    """
    Ambil daftar jadwal yang siap untuk inspeksi (status scheduled)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter jadwal berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"status": "scheduled"}
        else:
            filter_query = {"admin_id": admin_id, "status": "scheduled"}
        
        jadwal_list = list(jadwal_collection.find(filter_query).sort("tanggal", 1).sort("waktu", 1))
        
        # Populate dengan data aset dan format response
        result = []
        for jadwal in jadwal_list:
            # Get aset data
            aset_data = None
            if jadwal.get("id_aset"):
                aset_data = aset_collection.find_one({"id_aset": jadwal["id_aset"]})
            
            jadwal_response = {
                "id": str(jadwal["_id"]),
                "nama_inspektur": jadwal["nama_inspektur"],
                "tanggal": jadwal["tanggal"],
                "waktu": jadwal["waktu"],
                "alamat": jadwal["alamat"],
                "id_aset": jadwal.get("id_aset", ""),
                "nama_aset": aset_data["nama_aset"] if aset_data else "Aset tidak ditemukan",
                "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                "lokasi_aset": aset_data["lokasi"] if aset_data else "",
                "keterangan": jadwal.get("keterangan", ""),
                "status": jadwal["status"],
                "created_at": jadwal["created_at"].isoformat()
            }
            result.append(jadwal_response)
        
        logger.info(f"Retrieved {len(result)} scheduled jadwal for inspeksi")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving jadwal for inspeksi: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jadwal for inspeksi")

# 🆕 ENDPOINT BARU: Mulai Inspeksi dari Jadwal
@router.post("/inspeksi/start/{jadwal_id}")
async def start_inspeksi_from_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Mulai inspeksi berdasarkan jadwal tertentu
    """
    try:
        from bson import ObjectId
        admin_id = str(current_admin["_id"])
        
        # Ambil data jadwal
        jadwal_object_id = ObjectId(jadwal_id)
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": jadwal_object_id}
        else:
            filter_query = {"_id": jadwal_object_id, "admin_id": admin_id}
            
        jadwal = jadwal_collection.find_one(filter_query)
        
        if not jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        if jadwal["status"] != "scheduled":
            raise HTTPException(status_code=400, detail="Jadwal tidak dalam status scheduled")
        
        # Ambil data aset
        aset_data = None
        if jadwal.get("id_aset"):
            aset_data = aset_collection.find_one({"id_aset": jadwal["id_aset"]})
        
        # Update status jadwal menjadi "in_progress" (optional)
        # jadwal_collection.update_one(
        #     {"_id": jadwal_object_id},
        #     {"$set": {"status": "in_progress", "updated_at": datetime.utcnow()}}
        # )
        
        # Return data untuk inspeksi
        inspeksi_data = {
            "jadwal_id": jadwal_id,
            "nama_inspektur": jadwal["nama_inspektur"],
            "tanggal": jadwal["tanggal"],
            "waktu": jadwal["waktu"],
            "alamat": jadwal["alamat"],
            "id_aset": jadwal.get("id_aset", ""),
            "nama_aset": aset_data["nama_aset"] if aset_data else "Aset tidak ditemukan",
            "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
            "lokasi_aset": aset_data["lokasi"] if aset_data else "",
            "keterangan": jadwal.get("keterangan", ""),
            "current_cache_count": temp_collection.count_documents({"admin_id": admin_id, "jadwal_id": jadwal_id})
        }
        
        logger.info(f"Started inspeksi for jadwal {jadwal_id}")
        return {
            "message": "Inspeksi dimulai",
            "inspeksi_data": inspeksi_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting inspeksi from jadwal: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start inspeksi: {str(e)}")

# 🔄 UPDATED: Upload dan Tambah Data dengan Jadwal ID
@router.post("/inspeksi/add")
async def add_entry(
    jadwal_id: str = Form(...),
    jalur: str = Form(...),
    kondisi: str = Form(...), 
    keterangan: str = Form(...),
    foto: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Tambah entry baru dengan OCR koordinat dan reference ke jadwal
    """
    try:
        from bson import ObjectId
        admin_id = str(current_admin["_id"])
        
        # Validasi jadwal exists
        jadwal_object_id = ObjectId(jadwal_id)
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": jadwal_object_id}
        else:
            filter_query = {"_id": jadwal_object_id, "admin_id": admin_id}
            
        jadwal = jadwal_collection.find_one(filter_query)
        if not jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Validasi format file
        ext = Path(foto.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            raise HTTPException(status_code=400, detail="Format gambar tidak didukung")

        # Simpan file gambar ke temp
        filename = f"{uuid.uuid4().hex}{ext}"
        saved_path = IMAGE_TEMP_DIR / filename
        
        # Pastikan direktori exists
        IMAGE_TEMP_DIR.mkdir(parents=True, exist_ok=True)

        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

        # Ekstrak koordinat dengan validasi menggunakan Tesseract
        logger.info(f"Processing image with Tesseract: {foto.filename}")
        lintang, bujur = extract_coordinates_with_validation(str(saved_path))
        
        # Log hasil ekstraksi
        if lintang and bujur:
            logger.info(f"Successfully extracted coordinates: {lintang}, {bujur}")
            
            # Validasi koordinat Indonesia
            if is_coordinate_in_indonesia(lintang, bujur):
                logger.info("Coordinates are within Indonesia bounds")
            else:
                logger.warning("Coordinates may be outside Indonesia bounds")
        else:
            logger.warning(f"Failed to extract coordinates from {foto.filename}")

        # Buat entry baru untuk cache dengan jadwal_id
        entry_count = temp_collection.count_documents({"admin_id": admin_id, "jadwal_id": jadwal_id})
        entry = {
            "no": entry_count + 1,
            "jadwal_id": jadwal_id,
            "jalur": jalur,
            "kondisi": kondisi,
            "keterangan": keterangan,
            "latitude": lintang,
            "longitude": bujur,
            "foto_path": str(saved_path),
            "foto_filename": filename,
            "admin_id": admin_id,
            "created_at": datetime.now().isoformat(),
            "ocr_method": "tesseract_enhanced"
        }

        temp_collection.insert_one(entry)
        
        return {
            "message": "Data berhasil ditambahkan ke cache",
            "coordinates": {
                "latitude": lintang,
                "longitude": bujur
            },
            "entry": {
                "no": entry["no"],
                "jadwal_id": jadwal_id,
                "jalur": jalur,
                "kondisi": kondisi,
                "keterangan": keterangan,
                "foto_filename": filename
            },
            "ocr_info": {
                "method": "tesseract_enhanced",
                "coordinates_found": bool(lintang and bujur),
                "in_indonesia": is_coordinate_in_indonesia(lintang, bujur) if lintang and bujur else False
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_entry: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🔄 UPDATED: Ambil Data Cache berdasarkan Jadwal
@router.get("/inspeksi/cache/{jadwal_id}")
async def get_cache_by_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Ambil semua data cache untuk jadwal tertentu
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"jadwal_id": jadwal_id}
        else:
            filter_query = {"admin_id": admin_id, "jadwal_id": jadwal_id}
            
        data = list(temp_collection.find(filter_query, {"_id": 0}).sort("no", 1))
        logger.info(f"Retrieved {len(data)} cache entries for jadwal {jadwal_id}")
        return data
    except Exception as e:
        logger.error(f"Error retrieving cache data for jadwal: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache data")

# 🔄 UPDATED: Hapus Data Cache dengan Jadwal consideration
@router.delete("/inspeksi/delete/{jadwal_id}/{no}")
async def delete_entry_by_jadwal(
    jadwal_id: str,
    no: int, 
    current_admin: dict = Depends(get_current_admin)
):
    """
    Hapus entry cache berdasarkan jadwal dan nomor
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"no": no, "jadwal_id": jadwal_id}
        else:
            filter_query = {"no": no, "jadwal_id": jadwal_id, "admin_id": admin_id}
        
        # Ambil data untuk mendapatkan path gambar
        entry = temp_collection.find_one(filter_query)
        if not entry:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        # Hapus file gambar jika ada
        if "foto_path" in entry:
            try:
                foto_path = Path(entry["foto_path"])
                if foto_path.exists():
                    foto_path.unlink()
                    logger.info(f"Deleted image file: {foto_path}")
            except Exception as e:
                logger.warning(f"Failed to delete image file: {e}")
        
        # Hapus dari database
        result = temp_collection.delete_one(filter_query)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        logger.info(f"Deleted entry no: {no} for jadwal {jadwal_id}")
        return {"message": "Data berhasil dihapus"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entry {no} for jadwal {jadwal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete entry")

# 🔄 UPDATED: Generate Excel dengan Jadwal Info
@router.post("/inspeksi/generate/{jadwal_id}")
async def generate_file_by_jadwal(
    jadwal_id: str,
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate Excel file dengan OCR koordinat berdasarkan jadwal tertentu
    """
    try:
        from bson import ObjectId
        admin_id = str(current_admin["_id"])
        
        # Validasi jadwal
        jadwal_object_id = ObjectId(jadwal_id)
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": jadwal_object_id}
        else:
            filter_query = {"_id": jadwal_object_id, "admin_id": admin_id}
            
        jadwal = jadwal_collection.find_one(filter_query)
        if not jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Get aset data
        aset_data = None
        if jadwal.get("id_aset"):
            aset_data = aset_collection.find_one({"id_aset": jadwal["id_aset"]})
        
        # Parse JSON entries dari FormData
        parsed = [json.loads(e) for e in entries]
        if not parsed or len(parsed) != len(images):
            raise HTTPException(400, "Jumlah entries dan images tidak cocok")

        logger.info(f"Generating Excel for jadwal {jadwal_id} with {len(images)} images using Tesseract")

        # Get extractor instance
        extractor = get_extractor()

        # Siapkan data lengkap untuk excel
        full_entries = []
        for i, (entry, img) in enumerate(zip(parsed, images), start=1):
            try:
                logger.info(f"Processing image {i}/{len(images)}: {img.filename}")
                
                # Validasi format file
                ext = Path(img.filename).suffix.lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                    logger.warning(f"Unsupported file format: {ext}")
                    continue
                
                # Simpan gambar sementara
                fname = f"{uuid.uuid4().hex}{ext}"
                save_path = IMAGE_TEMP_DIR / fname
                
                # Pastikan direktori exists
                IMAGE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
                
                with save_path.open("wb") as f:
                    shutil.copyfileobj(img.file, f)

                # OCR: ambil lintang & bujur dengan validasi menggunakan Tesseract
                lintang, bujur = extract_coordinates_with_validation(str(save_path))
                
                # Log hasil untuk setiap gambar
                if lintang and bujur:
                    logger.info(f"Image {i} coordinates: {lintang}, {bujur}")
                    
                    # Validasi tambahan untuk wilayah Indonesia
                    if not is_coordinate_in_indonesia(lintang, bujur):
                        logger.warning(f"Image {i} coordinates outside Indonesia: {lintang}, {bujur}")
                else:
                    logger.warning(f"Failed to extract coordinates from image {i}")

                # Lengkapi entry dengan data jadwal dan aset
                entry_complete = {
                    "no": i,
                    "jalur": entry.get("jalur", ""),
                    "latitude": lintang,
                    "longitude": bujur,
                    "kondisi": entry.get("kondisi", ""),
                    "keterangan": entry.get("keterangan", ""),
                    "foto_path": str(save_path),
                    "image": str(save_path),  # Untuk compatibility dengan excel service
                    "ocr_method": "tesseract_enhanced",
                    # Data jadwal dan aset untuk Excel
                    "jadwal_id": jadwal_id,
                    "nama_inspektur": jadwal.get("nama_inspektur", ""),
                    "tanggal_inspeksi": jadwal.get("tanggal", ""),
                    "waktu_inspeksi": jadwal.get("waktu", ""),
                    "alamat_inspeksi": jadwal.get("alamat", ""),
                    "id_aset": jadwal.get("id_aset", ""),
                    "nama_aset": aset_data["nama_aset"] if aset_data else "",
                    "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                    "lokasi_aset": aset_data["lokasi"] if aset_data else ""
                }
                full_entries.append(entry_complete)
                
            except Exception as e:
                logger.error(f"Error processing image {i}: {e}")
                # Tetap lanjutkan dengan entry kosong untuk koordinat
                entry_complete = {
                    "no": i,
                    "jalur": entry.get("jalur", ""),
                    "latitude": "",
                    "longitude": "",
                    "kondisi": entry.get("kondisi", ""),
                    "keterangan": entry.get("keterangan", ""),
                    "foto_path": "",
                    "image": "",
                    "ocr_method": "tesseract_enhanced",
                    # Data jadwal dan aset
                    "jadwal_id": jadwal_id,
                    "nama_inspektur": jadwal.get("nama_inspektur", ""),
                    "tanggal_inspeksi": jadwal.get("tanggal", ""),
                    "waktu_inspeksi": jadwal.get("waktu", ""),
                    "alamat_inspeksi": jadwal.get("alamat", ""),
                    "id_aset": jadwal.get("id_aset", ""),
                    "nama_aset": aset_data["nama_aset"] if aset_data else "",
                    "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                    "lokasi_aset": aset_data["lokasi"] if aset_data else ""
                }
                full_entries.append(entry_complete)

        if not full_entries:
            raise HTTPException(400, "Tidak ada data yang berhasil diproses")

        # Generate Excel dan kirim file sebagai response download
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = generate_excel(full_entries, save_dir)

        logger.info(f"Excel file generated successfully for jadwal {jadwal_id}: {output_path}")
        
        return FileResponse(
            path=str(output_path),
            filename=f"inspeksi-jadwal-{jadwal_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_file_by_jadwal: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")

# 🔄 UPDATED: Simpan Data dengan Jadwal Completion
@router.post("/inspeksi/save/{jadwal_id}")
async def save_data_by_jadwal(
    jadwal_id: str,
    entries: List[str] = Form(...),
    images: List[UploadFile] = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Simpan data dari inspeksi ke history dan update status jadwal
    """
    try:
        from bson import ObjectId
        admin_id = str(current_admin["_id"])
        
        # Validasi jadwal
        jadwal_object_id = ObjectId(jadwal_id)
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"_id": jadwal_object_id}
        else:
            filter_query = {"_id": jadwal_object_id, "admin_id": admin_id}
            
        jadwal = jadwal_collection.find_one(filter_query)
        if not jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Get aset data
        aset_data = None
        if jadwal.get("id_aset"):
            aset_data = aset_collection.find_one({"id_aset": jadwal["id_aset"]})
        
        # Parse entries dari JSON string
        parsed_entries = []
        for entry_str in entries:
            try:
                entry_data = json.loads(entry_str)
                parsed_entries.append(entry_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse entry: {entry_str}, error: {e}")
                continue

        if not parsed_entries:
            raise HTTPException(status_code=400, detail="Tidak ada data valid untuk disimpan")

        # Validasi jumlah images sesuai dengan entries
        if len(images) != len(parsed_entries):
            raise HTTPException(
                status_code=400, 
                detail=f"Jumlah gambar ({len(images)}) tidak sesuai dengan jumlah entries ({len(parsed_entries)})"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path = IMAGE_SAVED_DIR / f"jadwal_{jadwal_id}_{timestamp}"
        folder_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving {len(parsed_entries)} entries for jadwal {jadwal_id}: {timestamp}")

        # Get extractor instance
        extractor = get_extractor()

        # Simpan gambar dan update path
        saved_data = []
        successful_saves = 0
        
        for i, (entry, image) in enumerate(zip(parsed_entries, images)):
            try:
                # Validasi gambar
                if not image.content_type.startswith('image/'):
                    logger.warning(f"File {image.filename} bukan gambar valid")
                    continue

                # Generate nama file unik
                file_extension = Path(image.filename).suffix if image.filename else '.jpg'
                new_filename = f"img_{i+1:03d}_{timestamp}{file_extension}"
                image_path = folder_path / new_filename

                # Simpan gambar
                content = await image.read()
                with open(image_path, "wb") as f:
                    f.write(content)

                logger.info(f"Saved image {i+1}: {image_path}")

                # Extract coordinates menggunakan Tesseract OCR
                latitude = ""
                longitude = ""
                try:
                    latitude, longitude = extract_coordinates_with_validation(str(image_path))
                    if latitude and longitude:
                        logger.info(f"Extracted coordinates for image {i+1}: {latitude}, {longitude}")
                        
                        # Validasi Indonesia
                        if is_coordinate_in_indonesia(latitude, longitude):
                            logger.info(f"Coordinates {i+1} are within Indonesia bounds")
                        else:
                            logger.warning(f"Coordinates {i+1} may be outside Indonesia bounds")
                    else:
                        logger.warning(f"Failed to extract coordinates for image {i+1}")
                except Exception as ocr_error:
                    logger.error(f"Tesseract OCR error for image {i+1}: {ocr_error}")

                # Update entry dengan path gambar, koordinat, dan data jadwal/aset
                entry_with_all_data = {
                    **entry,
                    "foto_path": str(image_path),
                    "foto_filename": new_filename,
                    "original_filename": image.filename,
                    "latitude": latitude,
                    "longitude": longitude,
                    "ocr_method": "tesseract_enhanced",
                    "coordinates_found": bool(latitude and longitude),
                    "in_indonesia_bounds": is_coordinate_in_indonesia(latitude, longitude) if latitude and longitude else False,
                    # Data jadwal
                    "jadwal_id": jadwal_id,
                    "nama_inspektur": jadwal.get("nama_inspektur", ""),
                    "tanggal_inspeksi": jadwal.get("tanggal", ""),
                    "waktu_inspeksi": jadwal.get("waktu", ""),
                    "alamat_inspeksi": jadwal.get("alamat", ""),
                    # Data aset
                    "id_aset": jadwal.get("id_aset", ""),
                    "nama_aset": aset_data["nama_aset"] if aset_data else "",
                    "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                    "lokasi_aset": aset_data["lokasi"] if aset_data else "",
                    "saved_at": datetime.now().isoformat()
                }
                
                saved_data.append(entry_with_all_data)
                successful_saves += 1
                
            except Exception as e:
                logger.error(f"Failed to save entry {i}: {e}")
                # Tetap simpan entry tanpa gambar jika terjadi error
                entry_with_error = {
                    **entry,
                    "foto_path": "",
                    "foto_filename": image.filename if image else "",
                    "original_filename": image.filename if image else "",
                    "latitude": "",
                    "longitude": "",
                    "ocr_method": "tesseract_enhanced",
                    "coordinates_found": False,
                    "in_indonesia_bounds": False,
                    "error": str(e),
                    # Data jadwal
                    "jadwal_id": jadwal_id,
                    "nama_inspektur": jadwal.get("nama_inspektur", ""),
                    "tanggal_inspeksi": jadwal.get("tanggal", ""),
                    "waktu_inspeksi": jadwal.get("waktu", ""),
                    "alamat_inspeksi": jadwal.get("alamat", ""),
                    # Data aset
                    "id_aset": jadwal.get("id_aset", ""),
                    "nama_aset": aset_data["nama_aset"] if aset_data else "",
                    "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                    "lokasi_aset": aset_data["lokasi"] if aset_data else "",
                    "saved_at": datetime.now().isoformat()
                }
                saved_data.append(entry_with_error)

        if not saved_data:
            raise HTTPException(status_code=400, detail="Tidak ada data yang berhasil disimpan")

        # Simpan ke history collection
        history_entry = {
            "timestamp": timestamp,
            "jadwal_id": jadwal_id,
            "data": saved_data,
            "admin_id": admin_id,
            "ocr_method": "tesseract_enhanced",
            "jadwal_info": {
                "nama_inspektur": jadwal.get("nama_inspektur", ""),
                "tanggal": jadwal.get("tanggal", ""),
                "waktu": jadwal.get("waktu", ""),
                "alamat": jadwal.get("alamat", ""),
                "id_aset": jadwal.get("id_aset", ""),
                "nama_aset": aset_data["nama_aset"] if aset_data else "",
                "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                "lokasi_aset": aset_data["lokasi"] if aset_data else ""
            },
            "summary": {
                "total_entries": len(saved_data),
                "successful_saves": successful_saves,
                "images_saved": successful_saves,
                "coordinates_extracted": sum(1 for d in saved_data if d.get("coordinates_found", False)),
                "indonesia_coordinates": sum(1 for d in saved_data if d.get("in_indonesia_bounds", False)),
                "folder_path": str(folder_path),
                "created_at": datetime.now().isoformat()
            }
        }

        # Insert ke MongoDB
        result = history_collection.insert_one(history_entry)
        
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Gagal menyimpan ke database")

        # ✅ UPDATE STATUS JADWAL menjadi COMPLETED
        jadwal_collection.update_one(
            {"_id": jadwal_object_id},
            {"$set": {"status": "completed", "updated_at": datetime.utcnow(), "completed_at": datetime.utcnow()}}
        )

        # ✅ HAPUS CACHE untuk jadwal ini setelah berhasil disimpan
        temp_collection.delete_many({"jadwal_id": jadwal_id})
        logger.info(f"Cache cleared for jadwal {jadwal_id}")

        logger.info(f"Successfully saved history entry with ID: {result.inserted_id}")
        
        return {
            "message": "Inspeksi berhasil diselesaikan dan data disimpan",
            "timestamp": timestamp,
            "jadwal_id": jadwal_id,
            "jadwal_status": "completed",
            "total_saved": len(saved_data),
            "successful_images": successful_saves,
            "coordinates_extracted": sum(1 for d in saved_data if d.get("coordinates_found", False)),
            "indonesia_coordinates": sum(1 for d in saved_data if d.get("in_indonesia_bounds", False)),
            "history_id": str(result.inserted_id),
            "ocr_method": "tesseract_enhanced",
            "action": "inspeksi_completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in save_data_by_jadwal: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🆕 Generate from cache dengan Jadwal ID
@router.post("/inspeksi/generate-from-cache/{jadwal_id}")
async def generate_from_cache_by_jadwal(
    jadwal_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate Excel file dari data cache untuk jadwal tertentu
    """
    try:
        from bson import ObjectId
        admin_id = str(current_admin["_id"])
        logger.info(f"=== GENERATE FROM CACHE FOR JADWAL {jadwal_id} START ===")
        
        # Validasi jadwal
        jadwal_object_id = ObjectId(jadwal_id)
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            jadwal_filter = {"_id": jadwal_object_id}
        else:
            jadwal_filter = {"_id": jadwal_object_id, "admin_id": admin_id}
            
        jadwal = jadwal_collection.find_one(jadwal_filter)
        if not jadwal:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
        # Get aset data
        aset_data = None
        if jadwal.get("id_aset"):
            aset_data = aset_collection.find_one({"id_aset": jadwal["id_aset"]})
        
        # Ambil data cache untuk jadwal ini
        try:
            logger.info("Fetching cache data for jadwal...")
            
            # Filter berdasarkan role
            if current_admin.get("role") == "admin":
                cache_filter = {"jadwal_id": jadwal_id}
            else:
                cache_filter = {"admin_id": admin_id, "jadwal_id": jadwal_id}
                
            cache_data = list(temp_collection.find(cache_filter, {"_id": 0}))
            logger.info(f"Cache data count for jadwal {jadwal_id}: {len(cache_data)}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        
        if not cache_data:
            logger.warning(f"No cache data found for jadwal {jadwal_id}")
            raise HTTPException(status_code=400, detail="Tidak ada data cache untuk jadwal ini")

        # Process data dengan informasi jadwal dan aset
        try:
            logger.info(f"=== PROCESSING DATA FOR EXCEL (Jadwal {jadwal_id}) ===")
            processed_data = []
            
            for i, item in enumerate(cache_data):
                try:
                    # Ambil koordinat dari cache dengan validasi
                    cached_latitude = item.get("latitude", "")
                    cached_longitude = item.get("longitude", "")
                    
                    # Pastikan tidak ada leading/trailing spaces
                    if cached_latitude:
                        cached_latitude = str(cached_latitude).strip()
                    if cached_longitude:
                        cached_longitude = str(cached_longitude).strip()
                    
                    processed_item = {
                        "no": item.get("no", i + 1),
                        "jalur": item.get("jalur", ""),
                        "kondisi": item.get("kondisi", ""),
                        "keterangan": item.get("keterangan", ""),
                        "latitude": cached_latitude,
                        "longitude": cached_longitude,
                        "foto_path": item.get("foto_path", ""),
                        "image": item.get("foto_path", ""),
                        "ocr_method": item.get("ocr_method", "tesseract_enhanced"),
                        "coordinates_found": bool(cached_latitude and cached_longitude),
                        "in_indonesia_bounds": is_coordinate_in_indonesia(cached_latitude, cached_longitude) if cached_latitude and cached_longitude else False,
                        # Data jadwal dan aset untuk Excel
                        "jadwal_id": jadwal_id,
                        "nama_inspektur": jadwal.get("nama_inspektur", ""),
                        "tanggal_inspeksi": jadwal.get("tanggal", ""),
                        "waktu_inspeksi": jadwal.get("waktu", ""),
                        "alamat_inspeksi": jadwal.get("alamat", ""),
                        "id_aset": jadwal.get("id_aset", ""),
                        "nama_aset": aset_data["nama_aset"] if aset_data else "",
                        "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                        "lokasi_aset": aset_data["lokasi"] if aset_data else ""
                    }
                    
                    processed_data.append(processed_item)
                    
                    if i < 3:  # Log first 3 items
                        logger.info(f"Processed item {i+1}: lat='{cached_latitude}', lon='{cached_longitude}'")
                    
                except Exception as item_error:
                    logger.error(f"Error processing item {i+1}: {item_error}")
                    # Add item with empty coordinates if error
                    processed_item = {
                        "no": i + 1,
                        "jalur": item.get("jalur", ""),
                        "kondisi": item.get("kondisi", ""),
                        "keterangan": item.get("keterangan", ""),
                        "latitude": "",
                        "longitude": "",
                        "foto_path": "",
                        "image": "",
                        "ocr_method": "tesseract_enhanced",
                        "coordinates_found": False,
                        "in_indonesia_bounds": False,
                        # Data jadwal dan aset
                        "jadwal_id": jadwal_id,
                        "nama_inspektur": jadwal.get("nama_inspektur", ""),
                        "tanggal_inspeksi": jadwal.get("tanggal", ""),
                        "waktu_inspeksi": jadwal.get("waktu", ""),
                        "alamat_inspeksi": jadwal.get("alamat", ""),
                        "id_aset": jadwal.get("id_aset", ""),
                        "nama_aset": aset_data["nama_aset"] if aset_data else "",
                        "jenis_aset": aset_data["jenis_aset"] if aset_data else "",
                        "lokasi_aset": aset_data["lokasi"] if aset_data else ""
                    }
                    processed_data.append(processed_item)
                    
        except Exception as process_error:
            logger.error(f"Data processing error: {process_error}")
            raise HTTPException(status_code=500, detail=f"Data processing error: {str(process_error)}")

        logger.info(f"Total processed items: {len(processed_data)}")

        # Check and create save directory
        try:
            save_dir = UPLOAD_DIR
            save_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Save directory ready: {save_dir}")
        except Exception as dir_error:
            logger.error(f"Directory creation error: {dir_error}")
            raise HTTPException(status_code=500, detail=f"Directory error: {str(dir_error)}")

        # Generate Excel
        try:
            logger.info(f"=== CALLING GENERATE_EXCEL FOR JADWAL {jadwal_id} ===")
            output_path = generate_excel(processed_data, save_dir)
            logger.info(f"Excel generation completed: {output_path}")
        except Exception as excel_error:
            logger.error(f"Excel generation error: {excel_error}")
            import traceback
            logger.error(f"Excel error traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Excel generation error: {str(excel_error)}")

        # Verify file exists
        try:
            if not output_path.exists():
                logger.error(f"Generated file does not exist: {output_path}")
                raise HTTPException(status_code=500, detail="Generated file not found")
            
            file_size = output_path.stat().st_size
            logger.info(f"File verified, size: {file_size} bytes")
            
            if file_size == 0:
                logger.error("Generated file is empty")
                raise HTTPException(status_code=500, detail="Generated file is empty")
                
        except Exception as verify_error:
            logger.error(f"File verification error: {verify_error}")
            raise HTTPException(status_code=500, detail=f"File verification error: {str(verify_error)}")

        # Return file
        try:
            logger.info("Returning FileResponse...")
            return FileResponse(
                path=str(output_path),
                filename=f"inspeksi-jadwal-{jadwal_id}-cache-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as response_error:
            logger.error(f"FileResponse error: {response_error}")
            raise HTTPException(status_code=500, detail=f"File response error: {str(response_error)}")
        
    except HTTPException as he:
        logger.error(f"HTTP Exception: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"=== UNEXPECTED ERROR ===")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ===== LEGACY/BACKWARD COMPATIBILITY ENDPOINTS =====

# 🔄 UPDATED: Ambil Semua Data Cache (untuk backward compatibility)
@router.get("/inspeksi/all")
async def get_all_temp(current_admin: dict = Depends(get_current_admin)):
    """
    Ambil semua data cache untuk inspeksi (backward compatibility)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {}
        else:
            filter_query = {"admin_id": admin_id}
            
        data = list(temp_collection.find(filter_query, {"_id": 0}))
        logger.info(f"Retrieved {len(data)} total temporary entries")
        return data
    except Exception as e:
        logger.error(f"Error retrieving temporary data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve data")

# 🔴 Hapus Data Cache Berdasarkan No (Legacy)
@router.delete("/inspeksi/delete/{no}")
async def delete_entry(no: int, current_admin: dict = Depends(get_current_admin)):
    """
    Hapus entry cache berdasarkan nomor (Legacy endpoint)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {"no": no}
        else:
            filter_query = {"no": no, "admin_id": admin_id}
        
        # Ambil data untuk mendapatkan path gambar
        entry = temp_collection.find_one(filter_query)
        if not entry:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        # Hapus file gambar jika ada
        if "foto_path" in entry:
            try:
                foto_path = Path(entry["foto_path"])
                if foto_path.exists():
                    foto_path.unlink()
                    logger.info(f"Deleted image file: {foto_path}")
            except Exception as e:
                logger.warning(f"Failed to delete image file: {e}")
        
        # Hapus dari database
        result = temp_collection.delete_one(filter_query)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        logger.info(f"Deleted entry no: {no}")
        return {"message": "Data berhasil dihapus"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entry {no}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete entry")

# 🟡 Generate File Excel (Legacy - Bisa berulang kali)
@router.post("/inspeksi/generate")
async def generate_file(
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate Excel file dengan OCR koordinat (Legacy endpoint)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Parse JSON entries dari FormData
        parsed = [json.loads(e) for e in entries]
        if not parsed or len(parsed) != len(images):
            raise HTTPException(400, "Jumlah entries dan images tidak cocok")

        logger.info(f"Generating Excel for {len(images)} images using Tesseract for admin {admin_id}")

        # Get extractor instance
        extractor = get_extractor()

        # Siapkan data lengkap untuk excel
        full_entries = []
        for i, (entry, img) in enumerate(zip(parsed, images), start=1):
            try:
                logger.info(f"Processing image {i}/{len(images)}: {img.filename}")
                
                # Validasi format file
                ext = Path(img.filename).suffix.lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                    logger.warning(f"Unsupported file format: {ext}")
                    continue
                
                # Simpan gambar sementara
                fname = f"{uuid.uuid4().hex}{ext}"
                save_path = IMAGE_TEMP_DIR / fname
                
                # Pastikan direktori exists
                IMAGE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
                
                with save_path.open("wb") as f:
                    shutil.copyfileobj(img.file, f)

                # OCR: ambil lintang & bujur dengan validasi menggunakan Tesseract
                lintang, bujur = extract_coordinates_with_validation(str(save_path))
                
                # Log hasil untuk setiap gambar
                if lintang and bujur:
                    logger.info(f"Image {i} coordinates: {lintang}, {bujur}")
                    
                    # Validasi tambahan untuk wilayah Indonesia
                    if not is_coordinate_in_indonesia(lintang, bujur):
                        logger.warning(f"Image {i} coordinates outside Indonesia: {lintang}, {bujur}")
                else:
                    logger.warning(f"Failed to extract coordinates from image {i}")

                # Lengkapi entry
                entry_complete = {
                    "no": i,
                    "jalur": entry.get("jalur", ""),
                    "latitude": lintang,
                    "longitude": bujur,
                    "kondisi": entry.get("kondisi", ""),
                    "keterangan": entry.get("keterangan", ""),
                    "foto_path": str(save_path),
                    "image": str(save_path),  # Untuk compatibility dengan excel service
                    "ocr_method": "tesseract_enhanced"
                }
                full_entries.append(entry_complete)
                
            except Exception as e:
                logger.error(f"Error processing image {i}: {e}")
                # Tetap lanjutkan dengan entry kosong untuk koordinat
                entry_complete = {
                    "no": i,
                    "jalur": entry.get("jalur", ""),
                    "latitude": "",
                    "longitude": "",
                    "kondisi": entry.get("kondisi", ""),
                    "keterangan": entry.get("keterangan", ""),
                    "foto_path": "",
                    "image": "",
                    "ocr_method": "tesseract_enhanced"
                }
                full_entries.append(entry_complete)

        if not full_entries:
            raise HTTPException(400, "Tidak ada data yang berhasil diproses")

        # Generate Excel dan kirim file sebagai response download
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = generate_excel(full_entries, save_dir)

        logger.info(f"Excel file generated successfully using Tesseract: {output_path}")
        
        return FileResponse(
            path=str(output_path),
            filename=f"inspeksi-tesseract-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")

# 🟣 Simpan Data dan Pindahkan ke History (Legacy)
@router.post("/inspeksi/save")
async def save_data(
    entries: List[str] = Form(...),
    images: List[UploadFile] = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Simpan data dari inspeksi ke history dan hapus cache (Legacy endpoint)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Parse entries dari JSON string
        parsed_entries = []
        for entry_str in entries:
            try:
                entry_data = json.loads(entry_str)
                parsed_entries.append(entry_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse entry: {entry_str}, error: {e}")
                continue

        if not parsed_entries:
            raise HTTPException(status_code=400, detail="Tidak ada data valid untuk disimpan")

        # Validasi jumlah images sesuai dengan entries
        if len(images) != len(parsed_entries):
            raise HTTPException(
                status_code=400, 
                detail=f"Jumlah gambar ({len(images)}) tidak sesuai dengan jumlah entries ({len(parsed_entries)})"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path = IMAGE_SAVED_DIR / timestamp
        folder_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving {len(parsed_entries)} entries to history using Tesseract: {timestamp}")

        # Get extractor instance
        extractor = get_extractor()

        # Simpan gambar dan update path
        saved_data = []
        successful_saves = 0
        
        for i, (entry, image) in enumerate(zip(parsed_entries, images)):
            try:
                # Validasi gambar
                if not image.content_type.startswith('image/'):
                    logger.warning(f"File {image.filename} bukan gambar valid")
                    continue

                # Generate nama file unik
                file_extension = Path(image.filename).suffix if image.filename else '.jpg'
                new_filename = f"img_{i+1:03d}_{timestamp}{file_extension}"
                image_path = folder_path / new_filename

                # Simpan gambar
                content = await image.read()
                with open(image_path, "wb") as f:
                    f.write(content)

                logger.info(f"Saved image {i+1}: {image_path}")

                # Extract coordinates menggunakan Tesseract OCR
                latitude = ""
                longitude = ""
                try:
                    latitude, longitude = extract_coordinates_with_validation(str(image_path))
                    if latitude and longitude:
                        logger.info(f"Extracted coordinates for image {i+1}: {latitude}, {longitude}")
                        
                        # Validasi Indonesia
                        if is_coordinate_in_indonesia(latitude, longitude):
                            logger.info(f"Coordinates {i+1} are within Indonesia bounds")
                        else:
                            logger.warning(f"Coordinates {i+1} may be outside Indonesia bounds")
                    else:
                        logger.warning(f"Failed to extract coordinates for image {i+1}")
                except Exception as ocr_error:
                    logger.error(f"Tesseract OCR error for image {i+1}: {ocr_error}")

                # Update entry dengan path gambar dan koordinat
                entry_with_image = {
                    **entry,
                    "foto_path": str(image_path),
                    "foto_filename": new_filename,
                    "original_filename": image.filename,
                    "latitude": latitude,
                    "longitude": longitude,
                    "ocr_method": "tesseract_enhanced",
                    "coordinates_found": bool(latitude and longitude),
                    "in_indonesia_bounds": is_coordinate_in_indonesia(latitude, longitude) if latitude and longitude else False,
                    "saved_at": datetime.now().isoformat()
                }
                
                saved_data.append(entry_with_image)
                successful_saves += 1
                
            except Exception as e:
                logger.error(f"Failed to save entry {i}: {e}")
                # Tetap simpan entry tanpa gambar jika terjadi error
                entry_with_error = {
                    **entry,
                    "foto_path": "",
                    "foto_filename": image.filename if image else "",
                    "original_filename": image.filename if image else "",
                    "latitude": "",
                    "longitude": "",
                    "ocr_method": "tesseract_enhanced",
                    "coordinates_found": False,
                    "in_indonesia_bounds": False,
                    "error": str(e),
                    "saved_at": datetime.now().isoformat()
                }
                saved_data.append(entry_with_error)

        if not saved_data:
            raise HTTPException(status_code=400, detail="Tidak ada data yang berhasil disimpan")

        # Simpan ke history collection
        history_entry = {
            "timestamp": timestamp,
            "data": saved_data,
            "admin_id": admin_id,
            "ocr_method": "tesseract_enhanced",
            "summary": {
                "total_entries": len(saved_data),
                "successful_saves": successful_saves,
                "images_saved": successful_saves,
                "coordinates_extracted": sum(1 for d in saved_data if d.get("coordinates_found", False)),
                "indonesia_coordinates": sum(1 for d in saved_data if d.get("in_indonesia_bounds", False)),
                "folder_path": str(folder_path),
                "created_at": datetime.now().isoformat()
            }
        }

        # Insert ke MongoDB
        result = history_collection.insert_one(history_entry)
        
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Gagal menyimpan ke database")

        # ✅ HAPUS CACHE setelah berhasil disimpan (Refresh halaman)
        temp_collection.delete_many({"admin_id": admin_id})
        logger.info(f"Cache cleared for admin {admin_id} - halaman akan refresh")

        logger.info(f"Successfully saved history entry with ID: {result.inserted_id}")
        
        return {
            "message": "Data berhasil disimpan ke history dan cache dibersihkan",
            "timestamp": timestamp,
            "total_saved": len(saved_data),
            "successful_images": successful_saves,
            "coordinates_extracted": sum(1 for d in saved_data if d.get("coordinates_found", False)),
            "indonesia_coordinates": sum(1 for d in saved_data if d.get("in_indonesia_bounds", False)),
            "history_id": str(result.inserted_id),
            "ocr_method": "tesseract_enhanced",
            "action": "refresh_page"  # Signal untuk frontend refresh
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in save_data: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🟢 Simpan Data Cache ke History (Legacy)
@router.post("/inspeksi/save-cache")
async def save_cache_to_history(current_admin: dict = Depends(get_current_admin)):
    """
    Simpan data dari cache ke history (Legacy endpoint)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Ambil data cache untuk admin ini
        if current_admin.get("role") == "admin":
            filter_query = {}
        else:
            filter_query = {"admin_id": admin_id}
            
        data = list(temp_collection.find(filter_query, {"_id": 0}))
        if not data:
            raise HTTPException(status_code=400, detail="Tidak ada data cache untuk disimpan")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path = IMAGE_SAVED_DIR / timestamp
        folder_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving {len(data)} entries from cache to history using Tesseract: {timestamp}")

        # Pindahkan gambar ke folder history
        successful_moves = 0
        coordinates_count = 0
        indonesia_count = 0
        
        for d in data:
            try:
                if "foto_path" in d and d["foto_path"]:
                    original = Path(d["foto_path"])
                    if original.exists():
                        new_path = folder_path / original.name
                        shutil.move(str(original), new_path)
                        d["foto_path"] = str(new_path)
                        successful_moves += 1
                    else:
                        logger.warning(f"Image file not found: {original}")
                        d["foto_path"] = ""
                
                # Count coordinates
                if d.get("latitude") and d.get("longitude"):
                    coordinates_count += 1
                    if is_coordinate_in_indonesia(d["latitude"], d["longitude"]):
                        indonesia_count += 1
                
                # Update metadata
                d["ocr_method"] = d.get("ocr_method", "tesseract_enhanced")
                d["coordinates_found"] = bool(d.get("latitude") and d.get("longitude"))
                d["in_indonesia_bounds"] = is_coordinate_in_indonesia(d.get("latitude", ""), d.get("longitude", ""))
                
            except Exception as e:
                logger.error(f"Failed to move image {d.get('foto_path', 'unknown')}: {e}")
                d["foto_path"] = ""

        # Simpan ke history collection
        history_entry = {
            "timestamp": timestamp,
            "data": data,
            "admin_id": admin_id,
            "ocr_method": "tesseract_enhanced",
            "summary": {
                "total_entries": len(data),
                "images_moved": successful_moves,
                "coordinates_extracted": coordinates_count,
                "indonesia_coordinates": indonesia_count,
                "created_at": datetime.now().isoformat()
            }
        }

        result = history_collection.insert_one(history_entry)
        
        if result.inserted_id:
            # Hapus data cache setelah berhasil disimpan
            if current_admin.get("role") == "admin":
                temp_collection.delete_many({})
            else:
                temp_collection.delete_many({"admin_id": admin_id})
            logger.info(f"Cache cleared for admin {admin_id} after successful save")
            
            return {
                "message": "Data cache berhasil dipindahkan ke history",
                "timestamp": timestamp,
                "total_moved": len(data),
                "images_moved": successful_moves,
                "coordinates_extracted": coordinates_count,
                "indonesia_coordinates": indonesia_count,
                "ocr_method": "tesseract_enhanced",
                "action": "refresh_page"  # Signal untuk frontend refresh
            }
        else:
            raise HTTPException(status_code=500, detail="Gagal menyimpan ke database")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in save_cache_to_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 🆕 Endpoint untuk mendapatkan statistik Inspeksi
@router.get("/inspeksi/stats")
async def get_inspeksi_stats(current_admin: dict = Depends(get_current_admin)):
    """
    Dapatkan statistik inspeksi untuk admin dengan info Tesseract OCR
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            cache_filter = {}
            history_filter = {}
        else:
            cache_filter = {"admin_id": admin_id}
            history_filter = {"admin_id": admin_id}
        
        # Cache data stats
        cache_count = temp_collection.count_documents(cache_filter)
        
        # History stats untuk admin ini
        history_count = history_collection.count_documents(history_filter)
        
        # OCR accuracy dari data cache yang ada
        data = list(temp_collection.find(cache_filter, {"_id": 0}))
        
        total_entries = len(data)
        entries_with_coordinates = sum(1 for d in data if d.get("latitude") and d.get("longitude"))
        entries_with_valid_indonesia = sum(1 for d in data 
                                         if d.get("latitude") and d.get("longitude") 
                                         and is_coordinate_in_indonesia(d["latitude"], d["longitude"]))
        
        # Count by OCR method
        tesseract_entries = sum(1 for d in data if d.get("ocr_method") == "tesseract_enhanced")
        
        # Count by jadwal
        jadwal_based_entries = sum(1 for d in data if d.get("jadwal_id"))
        
        stats = {
            "cache": {
                "total_entries": cache_count,
                "has_data": cache_count > 0,
                "jadwal_based_entries": jadwal_based_entries
            },
            "history": {
                "total_saved": history_count
            },
            # ✅ BACKWARD COMPATIBILITY: Keep original structure for frontend
            "ocr_accuracy": {
                "total_entries": total_entries,
                "entries_with_coordinates": entries_with_coordinates,
                "entries_with_valid_indonesia_coordinates": entries_with_valid_indonesia,
                "coordinate_extraction_rate": (entries_with_coordinates / total_entries * 100) if total_entries > 0 else 0,
                "valid_indonesia_rate": (entries_with_valid_indonesia / total_entries * 100) if total_entries > 0 else 0
            },
            # ✅ NEW: Enhanced stats with Tesseract info
            "ocr_performance": {
                "total_entries": total_entries,
                "entries_with_coordinates": entries_with_coordinates,
                "entries_with_valid_indonesia_coordinates": entries_with_valid_indonesia,
                "tesseract_enhanced_entries": tesseract_entries,
                "coordinate_extraction_rate": (entries_with_coordinates / total_entries * 100) if total_entries > 0 else 0,
                "valid_indonesia_rate": (entries_with_valid_indonesia / total_entries * 100) if total_entries > 0 else 0,
                "tesseract_usage_rate": (tesseract_entries / total_entries * 100) if total_entries > 0 else 0,
                "jadwal_based_rate": (jadwal_based_entries / total_entries * 100) if total_entries > 0 else 0
            },
            "workflow": {
                "new_jadwal_based": jadwal_based_entries,
                "legacy_entries": total_entries - jadwal_based_entries
            },
            "ocr_method": "tesseract_enhanced",
            "migration_status": "completed",
            "features": [
                "Enhanced image preprocessing",
                "Multiple OCR configurations", 
                "Character whitelist optimization",
                "Indonesia coordinate validation",
                "Flexible coordinate pattern matching",
                "Jadwal-based workflow integration"
            ]
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting inspeksi stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get inspeksi statistics")

# 🆕 Clear Cache (untuk reset manual)
@router.delete("/inspeksi/clear-cache")
async def clear_cache(current_admin: dict = Depends(get_current_admin)):
    """
    Hapus semua data cache untuk admin (reset manual)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {}
        else:
            filter_query = {"admin_id": admin_id}
        
        # Hapus gambar-gambar di temp
        data = list(temp_collection.find(filter_query, {"foto_path": 1}))
        deleted_files = 0
        for item in data:
            if "foto_path" in item and item["foto_path"]:
                try:
                    foto_path = Path(item["foto_path"])
                    if foto_path.exists():
                        foto_path.unlink()
                        deleted_files += 1
                except Exception as e:
                    logger.warning(f"Failed to delete file {item['foto_path']}: {e}")
        
        # Hapus data dari database
        result = temp_collection.delete_many(filter_query)
        
        logger.info(f"Cache cleared for admin {admin_id}: {result.deleted_count} entries, {deleted_files} files")
        
        return {
            "message": "Cache berhasil dibersihkan",
            "deleted_entries": result.deleted_count,
            "deleted_files": deleted_files,
            "ocr_method": "tesseract_enhanced"
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

# ✅ Generate from cache dengan Tesseract (Legacy)
@router.post("/inspeksi/generate-from-cache")
async def generate_from_cache(current_admin: dict = Depends(get_current_admin)):
    """
    Generate Excel file dari data cache dengan koordinat yang sudah ada (Legacy endpoint)
    """
    try:
        admin_id = str(current_admin["_id"])
        logger.info(f"=== GENERATE FROM CACHE START (Legacy) ===")
        logger.info(f"Admin ID: {admin_id}")
        
        # Filter berdasarkan role
        if current_admin.get("role") == "admin":
            filter_query = {}
        else:
            filter_query = {"admin_id": admin_id}
        
        # Ambil data cache
        try:
            logger.info("Fetching cache data...")
            cache_data = list(temp_collection.find(filter_query, {"_id": 0}))
            logger.info(f"Cache data count: {len(cache_data)}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        
        if not cache_data:
            logger.warning("No cache data found")
            raise HTTPException(status_code=400, detail="Tidak ada data cache untuk di-generate")

        # Debug info
        logger.info("=== CACHE DATA DEBUGGING (Legacy) ===")
        tesseract_count = sum(1 for item in cache_data if item.get('ocr_method') == 'tesseract_enhanced')
        coords_count = sum(1 for item in cache_data if item.get('latitude') and item.get('longitude'))
        jadwal_count = sum(1 for item in cache_data if item.get('jadwal_id'))
        logger.info(f"Tesseract enhanced entries: {tesseract_count}/{len(cache_data)}")
        logger.info(f"Entries with coordinates: {coords_count}/{len(cache_data)}")
        logger.info(f"Jadwal-based entries: {jadwal_count}/{len(cache_data)}")

        # Process data
        try:
            logger.info("=== PROCESSING DATA FOR EXCEL (Legacy) ===")
            processed_data = []
            
            for i, item in enumerate(cache_data):
                try:
                    # Ambil koordinat dari cache dengan validasi
                    cached_latitude = item.get("latitude", "")
                    cached_longitude = item.get("longitude", "")
                    
                    # Pastikan tidak ada leading/trailing spaces
                    if cached_latitude:
                        cached_latitude = str(cached_latitude).strip()
                    if cached_longitude:
                        cached_longitude = str(cached_longitude).strip()
                    
                    processed_item = {
                        "no": item.get("no", i + 1),
                        "jalur": item.get("jalur", ""),
                        "kondisi": item.get("kondisi", ""),
                        "keterangan": item.get("keterangan", ""),
                        "latitude": cached_latitude,
                        "longitude": cached_longitude,
                        "foto_path": item.get("foto_path", ""),
                        "image": item.get("foto_path", ""),
                        "ocr_method": item.get("ocr_method", "tesseract_enhanced"),
                        "coordinates_found": bool(cached_latitude and cached_longitude),
                        "in_indonesia_bounds": is_coordinate_in_indonesia(cached_latitude, cached_longitude) if cached_latitude and cached_longitude else False
                    }
                    
                    processed_data.append(processed_item)
                    
                    if i < 3:  # Log first 3 items
                        logger.info(f"Processed item {i+1}: lat='{cached_latitude}', lon='{cached_longitude}', method='{processed_item['ocr_method']}'")
                    
                except Exception as item_error:
                    logger.error(f"Error processing item {i+1}: {item_error}")
                    # Add item with empty coordinates if error
                    processed_item = {
                        "no": i + 1,
                        "jalur": item.get("jalur", ""),
                        "kondisi": item.get("kondisi", ""),
                        "keterangan": item.get("keterangan", ""),
                        "latitude": "",
                        "longitude": "",
                        "foto_path": "",
                        "image": "",
                        "ocr_method": "tesseract_enhanced",
                        "coordinates_found": False,
                        "in_indonesia_bounds": False
                    }
                    processed_data.append(processed_item)
                    
        except Exception as process_error:
            logger.error(f"Data processing error: {process_error}")
            raise HTTPException(status_code=500, detail=f"Data processing error: {str(process_error)}")

        logger.info(f"Total processed items: {len(processed_data)}")
        successful_coords = sum(1 for item in processed_data if item['coordinates_found'])
        indonesia_coords = sum(1 for item in processed_data if item['in_indonesia_bounds'])
        logger.info(f"Items with coordinates: {successful_coords}")
        logger.info(f"Items with Indonesia coordinates: {indonesia_coords}")

        # Check and create save directory
        try:
            save_dir = UPLOAD_DIR
            save_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Save directory ready: {save_dir}")
        except Exception as dir_error:
            logger.error(f"Directory creation error: {dir_error}")
            raise HTTPException(status_code=500, detail=f"Directory error: {str(dir_error)}")

        # Generate Excel
        try:
            logger.info("=== CALLING GENERATE_EXCEL (Legacy) ===")
            output_path = generate_excel(processed_data, save_dir)
            logger.info(f"Excel generation completed: {output_path}")
        except FileNotFoundError as fnf_error:
            logger.error(f"Template file not found: {fnf_error}")
            raise HTTPException(status_code=500, detail=f"Template Excel tidak ditemukan: {str(fnf_error)}")
        except Exception as excel_error:
            logger.error(f"Excel generation error: {excel_error}")
            import traceback
            logger.error(f"Excel error traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Excel generation error: {str(excel_error)}")

        # Verify file exists
        try:
            if not output_path.exists():
                logger.error(f"Generated file does not exist: {output_path}")
                raise HTTPException(status_code=500, detail="Generated file not found")
            
            file_size = output_path.stat().st_size
            logger.info(f"File verified, size: {file_size} bytes")
            
            if file_size == 0:
                logger.error("Generated file is empty")
                raise HTTPException(status_code=500, detail="Generated file is empty")
                
        except Exception as verify_error:
            logger.error(f"File verification error: {verify_error}")
            raise HTTPException(status_code=500, detail=f"File verification error: {str(verify_error)}")

        # Return file
        try:
            logger.info("Returning FileResponse...")
            return FileResponse(
                path=str(output_path),
                filename=f"inspeksi-legacy-cache-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as response_error:
            logger.error(f"FileResponse error: {response_error}")
            raise HTTPException(status_code=500, detail=f"File response error: {str(response_error)}")
        
    except HTTPException as he:
        logger.error(f"HTTP Exception: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"=== UNEXPECTED ERROR ===")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🆕 Debug endpoint untuk testing Tesseract OCR
@router.post("/inspeksi/debug-ocr")
async def debug_ocr(
    foto: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Debug endpoint untuk testing Tesseract OCR performance
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Validasi format file
        ext = Path(foto.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            raise HTTPException(status_code=400, detail="Format gambar tidak didukung")

        # Simpan file gambar sementara
        filename = f"debug_{uuid.uuid4().hex}{ext}"
        debug_path = IMAGE_TEMP_DIR / filename
        
        IMAGE_TEMP_DIR.mkdir(parents=True, exist_ok=True)

        with debug_path.open("wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

        logger.info(f"Debug OCR for file: {foto.filename}")

        # Get extractor untuk debug
        extractor = get_extractor()
        
        # Test preprocessing
        enhanced_images = extractor.preprocess_image_for_coordinates(str(debug_path))
        
        # Test OCR dengan multiple methods
        all_texts = extractor.extract_text_with_multiple_methods(enhanced_images) if enhanced_images else []
        
        # Test coordinate extraction
        best_coordinates = None
        extraction_attempts = []
        
        for method, config, text in all_texts:
            coords = extractor.extract_coordinates_flexible(text)
            attempt_info = {
                "method": method,
                "config": config[:50] + "..." if len(config) > 50 else config,
                "text": text[:100] + "..." if len(text) > 100 else text,
                "coordinates_found": bool(coords),
                "coordinates": coords if coords else None
            }
            extraction_attempts.append(attempt_info)
            
            if coords and not best_coordinates:
                best_coordinates = coords

        # Final coordinate extraction result
        final_lat, final_lon = extract_coordinates_with_validation(str(debug_path))
        
        # Cleanup debug file
        try:
            debug_path.unlink()
        except:
            pass

        debug_result = {
            "filename": foto.filename,
            "ocr_method": "tesseract_enhanced",
            "preprocessing": {
                "enhanced_images_generated": len(enhanced_images) if enhanced_images else 0,
                "methods": [method for method, _ in enhanced_images] if enhanced_images else []
            },
            "ocr_results": {
                "total_attempts": len(all_texts),
                "successful_extractions": len([t for t in all_texts if t[2].strip()]),
                "extraction_attempts": extraction_attempts
            },
            "coordinate_extraction": {
                "best_coordinates": best_coordinates,
                "final_result": {
                    "latitude": final_lat,
                    "longitude": final_lon,
                    "coordinates_found": bool(final_lat and final_lon),
                    "in_indonesia_bounds": is_coordinate_in_indonesia(final_lat, final_lon) if final_lat and final_lon else False
                }
            },
            "performance_summary": {
                "coordinate_extraction_successful": bool(final_lat and final_lon),
                "indonesia_validation_passed": is_coordinate_in_indonesia(final_lat, final_lon) if final_lat and final_lon else False,
                "total_processing_steps": len(enhanced_images) + len(all_texts) if enhanced_images else 0
            }
        }

        return debug_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in debug_ocr: {e}")
        raise HTTPException(status_code=500, detail=f"Debug OCR error: {str(e)}")