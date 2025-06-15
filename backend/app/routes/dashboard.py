from fastapi import APIRouter, UploadFile, File, Form, HTTPException
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
from app.config import temp_collection, history_collection
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR
from fastapi.responses import FileResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

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

@router.post("/generate")
async def generate_file(
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...)
):
    """
    Generate Excel file dengan OCR koordinat yang diperbaiki
    """
    try:
        # Parse JSON entries dari FormData
        parsed = [json.loads(e) for e in entries]
        if not parsed or len(parsed) != len(images):
            raise HTTPException(400, "Jumlah entries dan images tidak cocok")

        logger.info(f"Generating Excel for {len(images)} images")

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
            filename=output_path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")


# 🟢 Upload dan Tambah Data Baru
@router.post("/add")
async def add_entry(
    jalur: str = Form(...),
    kondisi: str = Form(...),
    keterangan: str = Form(...),
    foto: UploadFile = File(...)
):
    """
    Tambah entry baru dengan OCR koordinat yang diperbaiki
    """
    try:
        # Validasi format file
        ext = Path(foto.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            raise HTTPException(status_code=400, detail="Format gambar tidak didukung")

        # Simpan file gambar
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

        # Buat entry baru
        entry = {
            "no": temp_collection.count_documents({}) + 1,
            "jalur": jalur,
            "kondisi": kondisi,
            "keterangan": keterangan,
            "latitude": lintang,
            "longitude": bujur,
            "foto_path": str(saved_path),
            "created_at": datetime.now().isoformat()
        }

        temp_collection.insert_one(entry)
        
        return {
            "message": "Data berhasil ditambahkan",
            "coordinates": {
                "latitude": lintang,
                "longitude": bujur
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_entry: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 🔵 Ambil Semua Data Sementara (Dashboard)
@router.get("/all")
def get_all_temp():
    """
    Ambil semua data sementara untuk dashboard
    """
    try:
        data = list(temp_collection.find({}, {"_id": 0}))
        logger.info(f"Retrieved {len(data)} temporary entries")
        return data
    except Exception as e:
        logger.error(f"Error retrieving temporary data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve data")

# 🔴 Hapus Data Sementara Berdasarkan No
@router.delete("/delete/{no}")
def delete_entry(no: int):
    """
    Hapus entry berdasarkan nomor
    """
    try:
        # Ambil data untuk mendapatkan path gambar
        entry = temp_collection.find_one({"no": no})
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
        result = temp_collection.delete_one({"no": no})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        logger.info(f"Deleted entry no: {no}")
        return {"message": "Data berhasil dihapus"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entry {no}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete entry")

# 🟡 Generate File Excel dari Data Sementara@router.post("/generate")
async def generate_file(
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...)
):
    """
    Generate Excel file dengan sistem OCR koordinat yang diperbaiki
    """
    temp_files = []
    gps_results = []
    
    try:
        # Validasi input
        if not images or not entries:
            raise HTTPException(400, "Images dan entries tidak boleh kosong")
        
        # Parse JSON entries dari FormData
        try:
            parsed_entries = [json.loads(entry) for entry in entries]
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Invalid JSON format in entries: {str(e)}")
        
        if len(parsed_entries) != len(images):
            raise HTTPException(400, f"Jumlah entries ({len(parsed_entries)}) dan images ({len(images)}) tidak cocok")

        logger.info(f"Starting Excel generation for {len(images)} images")

        # Process setiap gambar
        full_entries = []
        
        for i, (entry, img) in enumerate(zip(parsed_entries, images), start=1):
            try:
                logger.info(f"Processing image {i}/{len(images)}: {img.filename}")
                
                # Validasi format file
                if not validate_image_file(img.filename):
                    logger.warning(f"Unsupported file format: {img.filename}")
                    # Tetap lanjutkan dengan entry kosong
                    entry_complete = create_empty_entry(i, entry)
                    full_entries.append(entry_complete)
                    continue
                
                # Simpan gambar sementara
                save_path = save_uploaded_image(img, IMAGE_TEMP_DIR)
                temp_files.append(save_path)
                
                # Reset file pointer untuk kemungkinan penggunaan selanjutnya
                img.file.seek(0)
                
                # Ekstrak koordinat GPS dengan sistem baru
                gps_result = extract_gps_coordinates_advanced(save_path)
                gps_results.append(gps_result)
                
                # Log hasil untuk monitoring
                if gps_result.is_valid:
                    logger.info(f"Image {i} GPS extraction successful: "
                              f"{gps_result.latitude}, {gps_result.longitude} "
                              f"(confidence: {gps_result.confidence:.2f})")
                    
                    # Validasi tambahan untuk wilayah Indonesia
                    if not is_coordinate_in_indonesia(gps_result.latitude, gps_result.longitude):
                        logger.warning(f"Image {i} coordinates outside Indonesia bounds")
                        gps_result.is_valid = False
                else:
                    logger.warning(f"Image {i} GPS extraction failed or low confidence")

                # Buat entry lengkap
                entry_complete = {
                    "no": i,
                    "jalur": entry.get("jalur", ""),
                    "latitude": gps_result.latitude if gps_result.is_valid else "",
                    "longitude": gps_result.longitude if gps_result.is_valid else "",
                    "kondisi": entry.get("kondisi", ""),
                    "keterangan": entry.get("keterangan", ""),
                    "foto_path": save_path,
                    "image": save_path,
                    # Data tambahan untuk analisis
                    "gps_confidence": f"{gps_result.confidence:.2f}" if gps_result.confidence > 0 else "",
                    "extraction_method": gps_result.method,
                    "processing_time": f"{gps_result.processing_time:.2f}s",
                    "gps_context": json.dumps(gps_result.context) if gps_result.context else ""
                }
                
                full_entries.append(entry_complete)
                
            except Exception as e:
                logger.error(f"Error processing image {i} ({img.filename}): {str(e)}")
                # Tetap lanjutkan dengan entry kosong
                entry_complete = create_empty_entry(i, entry, error=str(e))
                full_entries.append(entry_complete)
                
                # Tambah result kosong untuk laporan
                empty_result = GPSExtractionResult()
                gps_results.append(empty_result)

        # Validasi apakah ada data yang berhasil diproses
        if not full_entries:
            raise HTTPException(400, "Tidak ada data yang berhasil diproses")

        # Generate laporan processing
        processing_report = generate_processing_report(gps_results)
        logger.info(f"Processing report: {processing_report}")

        # Import generate_excel function (diasumsikan sudah ada)
        from excel_service import generate_excel  # Sesuaikan dengan import yang benar
        
        # Generate Excel file
        output_path = generate_excel(full_entries, UPLOAD_DIR, processing_report)
        
        logger.info(f"Excel file generated successfully: {output_path}")
        logger.info(f"Processing summary: {processing_report}")
        
        # Cleanup temp files setelah Excel berhasil dibuat
        cleanup_temp_files(temp_files)
        
        # Return file sebagai response
        return FileResponse(
            path=str(output_path),
            filename=f"gps_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=gps_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "X-Processing-Report": json.dumps(processing_report)
            }
        )
        
    except HTTPException:
        # Cleanup temp files jika terjadi error
        cleanup_temp_files(temp_files)
        raise
    except Exception as e:
        # Cleanup temp files jika terjadi error
        cleanup_temp_files(temp_files)
        logger.error(f"Unexpected error in generate_file: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate Excel file: {str(e)}"
        )

def create_empty_entry(index: int, original_entry: dict, error: str = "") -> dict:
    """
    Buat entry kosong untuk kasus error
    """
    return {
        "no": index,
        "jalur": original_entry.get("jalur", ""),
        "latitude": "",
        "longitude": "",
        "kondisi": original_entry.get("kondisi", ""),
        "keterangan": original_entry.get("keterangan", ""),
        "foto_path": "",
        "image": "",
        "gps_confidence": "",
        "extraction_method": "",
        "processing_time": "",
        "gps_context": "",
        "error": error
    }
# 🟣 Simpan dan Pindahkan ke History
# Perbaikan untuk backend save endpoint
@router.post("/save")
async def save_data(
    entries: List[str] = Form(...),
    images: List[UploadFile] = File(...)
):
    """
    Simpan data yang dikirim dari frontend ke history
    """
    try:
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

                # ✅ FIXED: Extract coordinates menggunakan OCR
                latitude = ""
                longitude = ""
                try:
                    from app.services.ocr_service import extract_coordinates_with_validation
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
                    "latitude": latitude,  # ✅ Tambahkan koordinat
                    "longitude": longitude,  # ✅ Tambahkan koordinat
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

        logger.info(f"Successfully saved history entry with ID: {result.inserted_id}")
        
        return {
            "message": f"Data berhasil disimpan ke history",
            "timestamp": timestamp,
            "total_saved": len(saved_data),
            "successful_images": successful_saves,
            "history_id": str(result.inserted_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in save_data: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Alternatif: Jika Anda ingin tetap menggunakan logika lama, buat endpoint terpisah
@router.post("/save-temp")
def save_temp_to_history():
    """
    Simpan data dari temporary collection ke history (logika lama)
    """
    try:
        data = list(temp_collection.find({}, {"_id": 0}))
        if not data:
            raise HTTPException(status_code=400, detail="Tidak ada data temporary untuk disimpan")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path = IMAGE_SAVED_DIR / timestamp
        folder_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving {len(data)} entries from temp to history: {timestamp}")

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
            "summary": {
                "total_entries": len(data),
                "images_moved": successful_moves,
                "created_at": datetime.now().isoformat()
            }
        }

        result = history_collection.insert_one(history_entry)
        
        if result.inserted_id:
            # Hapus data temporary setelah berhasil disimpan
            temp_collection.delete_many({})
            logger.info(f"Temporary data cleared after successful save")
            
            return {
                "message": "Data berhasil dipindahkan ke history",
                "timestamp": timestamp,
                "total_moved": len(data),
                "images_moved": successful_moves
            }
        else:
            raise HTTPException(status_code=500, detail="Gagal menyimpan ke database")

    except Exception as e:
        logger.error(f"Error in save_temp_to_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 🆕 Endpoint tambahan untuk testing dan debugging


# 🆕 Endpoint untuk mendapatkan statistik OCR
@router.get("/ocr-stats")
def get_ocr_stats():
    """
    Dapatkan statistik akurasi OCR dari data yang ada
    """
    try:
        data = list(temp_collection.find({}, {"_id": 0}))
        
        total_entries = len(data)
        entries_with_coordinates = sum(1 for d in data if d.get("latitude") and d.get("longitude"))
        entries_with_valid_indonesia = sum(1 for d in data 
                                         if d.get("latitude") and d.get("longitude") 
                                         and is_coordinate_in_indonesia(d["latitude"], d["longitude"]))
        
        stats = {
            "total_entries": total_entries,
            "entries_with_coordinates": entries_with_coordinates,
            "entries_with_valid_indonesia_coordinates": entries_with_valid_indonesia,
            "coordinate_extraction_rate": (entries_with_coordinates / total_entries * 100) if total_entries > 0 else 0,
            "valid_indonesia_rate": (entries_with_valid_indonesia / total_entries * 100) if total_entries > 0 else 0
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting OCR stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get OCR statistics")