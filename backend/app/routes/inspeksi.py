# app/routes/inspeksi.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
from pathlib import Path
import shutil, uuid
import json
import logging
from datetime import datetime

# Import services yang sudah diperbaiki
from app.services.ocr_service import extract_coordinates_from_image
from app.services.excel_service import generate_excel
from app.ocr_config import CoordinateOCRConfig, enhance_image_for_coordinates, is_coordinate_in_indonesia
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

# Inisialisasi OCR config
ocr_config = CoordinateOCRConfig()

def extract_coordinates_with_validation(image_path: str) -> tuple[str, str]:
    """
    Ekstrak koordinat dengan multiple validation dan enhancement
    """
    try:
        logger.info(f"Extracting coordinates from: {image_path}")
        
        # Step 1: Enhance gambar untuk OCR yang lebih baik
        enhanced_path = enhance_image_for_coordinates(image_path)
        
        # Step 2: Multiple OCR attempts dengan berbagai metode
        coordinates_attempts = []
        
        # Attempt 1: OCR dengan image asli
        try:
            lat1, lon1 = extract_coordinates_from_image(image_path)
            if lat1 and lon1:
                coordinates_attempts.append((lat1, lon1, "original"))
                logger.debug(f"Original OCR result: {lat1}, {lon1}")
        except Exception as e:
            logger.debug(f"Original OCR failed: {e}")
        
        # Attempt 2: OCR dengan enhanced image
        if enhanced_path != image_path:
            try:
                lat2, lon2 = extract_coordinates_from_image(enhanced_path)
                if lat2 and lon2:
                    coordinates_attempts.append((lat2, lon2, "enhanced"))
                    logger.debug(f"Enhanced OCR result: {lat2}, {lon2}")
            except Exception as e:
                logger.debug(f"Enhanced OCR failed: {e}")
        
        # Attempt 3: OCR dengan konfigurasi yang dioptimalkan
        try:
            optimized_result = ocr_config.read_coordinates_optimized(image_path)
            if optimized_result:
                text_optimized = " ".join(optimized_result)
                lat3, lon3 = parse_coordinates_from_text(text_optimized)
                if lat3 and lon3:
                    coordinates_attempts.append((lat3, lon3, "optimized"))
                    logger.debug(f"Optimized OCR result: {lat3}, {lon3}")
        except Exception as e:
            logger.debug(f"Optimized OCR failed: {e}")
        
        # Step 3: Pilih hasil terbaik berdasarkan prioritas dan validasi
        if coordinates_attempts:
            # Prioritas: enhanced > optimized > original
            priority_order = ["enhanced", "optimized", "original"]
            
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

def parse_coordinates_from_text(text: str) -> tuple[str, str]:
    """
    Parse koordinat dari teks dengan regex yang lebih robust
    """
    import re
    
    # Pattern untuk berbagai format koordinat
    patterns = [
        # Format standar: 6°52'35.622"S 107°34'37.722"E
        r'(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:\.\d+)?)[\"″]\s*([NS])\s+(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:\.\d+)?)[\"″]\s*([EW])',
        
        # Format dengan koma: 6°52'35,622"S 107°34'37,722"E
        r'(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:,\d+)?)[\"″]\s*([NS])\s+(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:,\d+)?)[\"″]\s*([EW])',
        
        # Format tanpa spasi: 6°52'35.622"S107°34'37.722"E
        r'(\d{1,3})[°*](\d{1,2})[\'′](\d{1,2}(?:\.\d+)?)[\"″]([NS])(\d{1,3})[°*](\d{1,2})[\'′](\d{1,2}(?:\.\d+)?)[\"″]([EW])',
        
        # Format dengan karakter berbeda: 6*52'35.622"S 107*34'37.722"E
        r'(\d{1,3})[°*o]\s*(\d{1,2})[\'′/]\s*(\d{1,2}(?:[.,]\d+)?)[\"″]\s*([NS])\s+(\d{1,3})[°*o]\s*(\d{1,2})[\'′/]\s*(\d{1,2}(?:[.,]\d+)?)[\"″]\s*([EW])',
    ]
    
    # Normalisasi teks
    cleaned_text = (text
                   .replace(',', '.')
                   .replace('*', '°')
                   .replace('o', '°')
                   .replace('O', '°')
                   .replace('′', "'")
                   .replace('″', '"')
                   .replace('/', "'")
                   .replace('\\', "'"))
    
    logger.debug(f"Parsing coordinates from cleaned text: {cleaned_text}")
    
    for i, pattern in enumerate(patterns):
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        if matches:
            match = matches[0]
            if len(match) == 8:
                lat_deg, lat_min, lat_sec, lat_dir = match[0], match[1], match[2], match[3]
                lon_deg, lon_min, lon_sec, lon_dir = match[4], match[5], match[6], match[7]
                
                latitude = f"{lat_deg}° {lat_min}' {lat_sec}\" {lat_dir.upper()}"
                longitude = f"{lon_deg}° {lon_min}' {lon_sec}\" {lon_dir.upper()}"
                
                logger.debug(f"Pattern {i+1} matched: {latitude}, {longitude}")
                return latitude, longitude
    
    logger.debug("No coordinate patterns matched")
    return "", ""

# 🟢 Upload dan Tambah Data Baru
@router.post("/inspeksi/add")
async def add_entry(
    jalur: str = Form(...),
    kondisi: str = Form(...),
    keterangan: str = Form(...),
    foto: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Tambah entry baru dengan OCR koordinat yang diperbaiki (Cache data)
    """
    try:
        admin_id = str(current_admin["_id"])
        
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

        # Ekstrak koordinat dengan validasi
        logger.info(f"Processing image: {foto.filename}")
        lintang, bujur = extract_coordinates_with_validation(str(saved_path))
        
        # Log hasil ekstraksi
        if lintang and bujur:
            logger.info(f"Successfully extracted coordinates: {lintang}, {bujur}")
        else:
            logger.warning(f"Failed to extract coordinates from {foto.filename}")

        # Buat entry baru untuk cache
        entry = {
            "no": temp_collection.count_documents({"admin_id": admin_id}) + 1,
            "jalur": jalur,
            "kondisi": kondisi,
            "keterangan": keterangan,
            "latitude": lintang,
            "longitude": bujur,
            "foto_path": str(saved_path),
            "foto_filename": filename,
            "admin_id": admin_id,
            "created_at": datetime.now().isoformat()
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
                "jalur": jalur,
                "kondisi": kondisi,
                "keterangan": keterangan,
                "foto_filename": filename
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_entry: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🔵 Ambil Semua Data Cache (Inspeksi)
@router.get("/inspeksi/all")
async def get_all_temp(current_admin: dict = Depends(get_current_admin)):
    """
    Ambil semua data cache untuk inspeksi
    """
    try:
        admin_id = str(current_admin["_id"])
        data = list(temp_collection.find({"admin_id": admin_id}, {"_id": 0}))
        logger.info(f"Retrieved {len(data)} temporary entries for admin {admin_id}")
        return data
    except Exception as e:
        logger.error(f"Error retrieving temporary data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve data")

# 🔴 Hapus Data Cache Berdasarkan No
@router.delete("/inspeksi/delete/{no}")
async def delete_entry(no: int, current_admin: dict = Depends(get_current_admin)):
    """
    Hapus entry cache berdasarkan nomor
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Ambil data untuk mendapatkan path gambar
        entry = temp_collection.find_one({"no": no, "admin_id": admin_id})
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
        result = temp_collection.delete_one({"no": no, "admin_id": admin_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        logger.info(f"Deleted entry no: {no} for admin {admin_id}")
        return {"message": "Data berhasil dihapus"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entry {no}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete entry")

# 🟡 Generate File Excel (Bisa berulang kali)
@router.post("/inspeksi/generate")
async def generate_file(
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Generate Excel file dengan OCR koordinat yang diperbaiki (Bisa berulang kali)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Parse JSON entries dari FormData
        parsed = [json.loads(e) for e in entries]
        if not parsed or len(parsed) != len(images):
            raise HTTPException(400, "Jumlah entries dan images tidak cocok")

        logger.info(f"Generating Excel for {len(images)} images for admin {admin_id}")

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

                # OCR: ambil lintang & bujur dengan validasi
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
                }
                full_entries.append(entry_complete)

        if not full_entries:
            raise HTTPException(400, "Tidak ada data yang berhasil diproses")

        # Generate Excel dan kirim file sebagai response download
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = generate_excel(full_entries, save_dir)

        logger.info(f"Excel file generated successfully: {output_path}")
        
        return FileResponse(
            path=str(output_path),
            filename=f"inspeksi-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")

# 🟣 Simpan Data dan Pindahkan ke History (Sekali saja, lalu refresh)
@router.post("/inspeksi/save")
async def save_data(
    entries: List[str] = Form(...),
    images: List[UploadFile] = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Simpan data dari inspeksi ke history dan hapus cache (Sekali saja, lalu refresh)
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

        logger.info(f"Saving {len(parsed_entries)} entries to history: {timestamp}")

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

                # Extract coordinates menggunakan OCR
                latitude = ""
                longitude = ""
                try:
                    latitude, longitude = extract_coordinates_with_validation(str(image_path))
                    if latitude and longitude:
                        logger.info(f"Extracted coordinates for image {i+1}: {latitude}, {longitude}")
                    else:
                        logger.warning(f"Failed to extract coordinates for image {i+1}")
                except Exception as ocr_error:
                    logger.error(f"OCR error for image {i+1}: {ocr_error}")

                # Update entry dengan path gambar dan koordinat
                entry_with_image = {
                    **entry,
                    "foto_path": str(image_path),
                    "foto_filename": new_filename,
                    "original_filename": image.filename,
                    "latitude": latitude,  # Tambahkan koordinat
                    "longitude": longitude,  # Tambahkan koordinat
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
            "admin_id": admin_id,  # Tambahkan admin_id
            "summary": {
                "total_entries": len(saved_data),
                "successful_saves": successful_saves,
                "images_saved": successful_saves,
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
            "history_id": str(result.inserted_id),
            "action": "refresh_page"  # Signal untuk frontend refresh
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in save_data: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🟢 Simpan Data Cache ke History (Alternatif untuk data yang sudah ada di cache)
@router.post("/inspeksi/save-cache")
async def save_cache_to_history(current_admin: dict = Depends(get_current_admin)):
    """
    Simpan data dari cache ke history (Logika lama yang diperbaiki)
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Ambil data cache untuk admin ini
        data = list(temp_collection.find({"admin_id": admin_id}, {"_id": 0}))
        if not data:
            raise HTTPException(status_code=400, detail="Tidak ada data cache untuk disimpan")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path = IMAGE_SAVED_DIR / timestamp
        folder_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving {len(data)} entries from cache to history: {timestamp}")

        # Pindahkan gambar ke folder history
        successful_moves = 0
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
            except Exception as e:
                logger.error(f"Failed to move image {d.get('foto_path', 'unknown')}: {e}")
                d["foto_path"] = ""

        # Simpan ke history collection
        history_entry = {
            "timestamp": timestamp,
            "data": data,
            "admin_id": admin_id,
            "summary": {
                "total_entries": len(data),
                "images_moved": successful_moves,
                "created_at": datetime.now().isoformat()
            }
        }

        result = history_collection.insert_one(history_entry)
        
        if result.inserted_id:
            # Hapus data cache setelah berhasil disimpan
            temp_collection.delete_many({"admin_id": admin_id})
            logger.info(f"Cache cleared for admin {admin_id} after successful save")
            
            return {
                "message": "Data cache berhasil dipindahkan ke history",
                "timestamp": timestamp,
                "total_moved": len(data),
                "images_moved": successful_moves,
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
    Dapatkan statistik inspeksi untuk admin
    """
    try:
        admin_id = str(current_admin["_id"])
        
        # Cache data stats
        cache_count = temp_collection.count_documents({"admin_id": admin_id})
        
        # History stats untuk admin ini
        history_count = history_collection.count_documents({"admin_id": admin_id})
        
        # OCR accuracy dari data cache yang ada
        data = list(temp_collection.find({"admin_id": admin_id}, {"_id": 0}))
        
        total_entries = len(data)
        entries_with_coordinates = sum(1 for d in data if d.get("latitude") and d.get("longitude"))
        entries_with_valid_indonesia = sum(1 for d in data 
                                         if d.get("latitude") and d.get("longitude") 
                                         and is_coordinate_in_indonesia(d["latitude"], d["longitude"]))
        
        stats = {
            "cache": {
                "total_entries": cache_count,
                "has_data": cache_count > 0
            },
            "history": {
                "total_saved": history_count
            },
            "ocr_accuracy": {
                "total_entries": total_entries,
                "entries_with_coordinates": entries_with_coordinates,
                "entries_with_valid_indonesia_coordinates": entries_with_valid_indonesia,
                "coordinate_extraction_rate": (entries_with_coordinates / total_entries * 100) if total_entries > 0 else 0,
                "valid_indonesia_rate": (entries_with_valid_indonesia / total_entries * 100) if total_entries > 0 else 0
            }
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
        
        # Hapus gambar-gambar di temp
        data = list(temp_collection.find({"admin_id": admin_id}, {"foto_path": 1}))
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
        result = temp_collection.delete_many({"admin_id": admin_id})
        
        logger.info(f"Cache cleared for admin {admin_id}: {result.deleted_count} entries, {deleted_files} files")
        
        return {
            "message": "Cache berhasil dibersihkan",
            "deleted_entries": result.deleted_count,
            "deleted_files": deleted_files
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

# ✅ PERBAIKAN: Endpoint generate-from-cache dengan indentasi yang benar
@router.post("/inspeksi/generate-from-cache")
async def generate_from_cache(current_admin: dict = Depends(get_current_admin)):
    """
    Generate Excel file dari data cache dengan koordinat yang sudah ada
    """
    try:
        admin_id = str(current_admin["_id"])
        logger.info(f"=== GENERATE FROM CACHE START ===")
        logger.info(f"Admin ID: {admin_id}")
        
        # Ambil data cache
        logger.info("Fetching cache data...")
        cache_data = list(temp_collection.find({"admin_id": admin_id}, {"_id": 0}))
        logger.info(f"Cache data count: {len(cache_data)}")
        
        if not cache_data:
            logger.warning("No cache data found")
            raise HTTPException(status_code=400, detail="Tidak ada data cache untuk di-generate")

        # ✅ DEBUGGING DETAIL - Log setiap item cache
        logger.info("=== CACHE DATA DEBUGGING ===")
        for i, item in enumerate(cache_data):
            logger.info(f"Cache Item {i+1}:")
            logger.info(f"  Keys: {list(item.keys())}")
            logger.info(f"  No: {item.get('no')}")
            logger.info(f"  Jalur: '{item.get('jalur')}'")
            logger.info(f"  Latitude: '{item.get('latitude')}' (type: {type(item.get('latitude'))})")
            logger.info(f"  Longitude: '{item.get('longitude')}' (type: {type(item.get('longitude'))})")
            logger.info(f"  Kondisi: '{item.get('kondisi')}'")
            logger.info(f"  Keterangan: '{item.get('keterangan')}'")
            logger.info(f"  Foto path: '{item.get('foto_path')}'")

        # ✅ Process data - pastikan koordinat diteruskan dengan benar
        logger.info("=== PROCESSING DATA FOR EXCEL ===")
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
                
                logger.info(f"Processing item {i+1}:")
                logger.info(f"  Original lat: '{item.get('latitude')}'")
                logger.info(f"  Original lon: '{item.get('longitude')}'")
                logger.info(f"  Processed lat: '{cached_latitude}'")
                logger.info(f"  Processed lon: '{cached_longitude}'")
                
                processed_item = {
                    "no": item.get("no", i + 1),
                    "jalur": item.get("jalur", ""),
                    "kondisi": item.get("kondisi", ""),
                    "keterangan": item.get("keterangan", ""),
                    "latitude": cached_latitude,  # ✅ Koordinat dari cache
                    "longitude": cached_longitude,  # ✅ Koordinat dari cache
                    "foto_path": item.get("foto_path", ""),
                    "image": item.get("foto_path", ""),
                }
                
                processed_data.append(processed_item)
                logger.info(f"  ✅ Added to processed_data with lat='{cached_latitude}', lon='{cached_longitude}'")
                
            except Exception as process_error:
                logger.error(f"Error processing item {i+1}: {process_error}")
                # Tetap tambahkan item dengan koordinat kosong jika error
                processed_item = {
                    "no": i + 1,
                    "jalur": item.get("jalur", ""),
                    "kondisi": item.get("kondisi", ""),
                    "keterangan": item.get("keterangan", ""),
                    "latitude": "",
                    "longitude": "",
                    "foto_path": "",
                    "image": "",
                }
                processed_data.append(processed_item)

        logger.info(f"=== FINAL PROCESSED DATA ===")
        logger.info(f"Total processed items: {len(processed_data)}")
        for i, item in enumerate(processed_data):
            logger.info(f"Final item {i+1}: lat='{item['latitude']}', lon='{item['longitude']}'")

        # Generate Excel
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("=== CALLING GENERATE_EXCEL ===")
        output_path = generate_excel(processed_data, save_dir)
        logger.info(f"Excel generation completed: {output_path}")

        # Verify file exists
        if not output_path.exists():
            logger.error(f"Generated file does not exist: {output_path}")
            raise HTTPException(status_code=500, detail="Generated file not found")

        return FileResponse(
            path=str(output_path),
            filename=f"inspeksi-cache-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"=== UNEXPECTED ERROR ===")
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    

# app/routes/inspeksi.py - Update generate-from-cache endpoint
@router.post("/inspeksi/generate-from-cache")
async def generate_from_cache(current_admin: dict = Depends(get_current_admin)):
    """
    Generate Excel file dari data cache dengan koordinat yang sudah ada
    """
    try:
        admin_id = str(current_admin["_id"])
        logger.info(f"=== GENERATE FROM CACHE START ===")
        logger.info(f"Admin ID: {admin_id}")
        
        # Ambil data cache
        try:
            logger.info("Fetching cache data...")
            cache_data = list(temp_collection.find({"admin_id": admin_id}, {"_id": 0}))
            logger.info(f"Cache data count: {len(cache_data)}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        
        if not cache_data:
            logger.warning("No cache data found")
            raise HTTPException(status_code=400, detail="Tidak ada data cache untuk di-generate")

        # ✅ DEBUGGING DETAIL - Log setiap item cache
        logger.info("=== CACHE DATA DEBUGGING ===")
        for i, item in enumerate(cache_data[:3]):  # Log first 3 items only
            logger.info(f"Cache Item {i+1}:")
            logger.info(f"  Keys: {list(item.keys())}")
            logger.info(f"  No: {item.get('no')}")
            logger.info(f"  Jalur: '{item.get('jalur')}'")
            logger.info(f"  Latitude: '{item.get('latitude')}' (type: {type(item.get('latitude'))})")
            logger.info(f"  Longitude: '{item.get('longitude')}' (type: {type(item.get('longitude'))})")

        # ✅ Process data
        try:
            logger.info("=== PROCESSING DATA FOR EXCEL ===")
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
            logger.info("=== CALLING GENERATE_EXCEL ===")
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
                filename=f"inspeksi-cache-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
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