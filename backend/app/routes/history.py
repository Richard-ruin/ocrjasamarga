# app/routes/history.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from typing import List
from pathlib import Path
from datetime import datetime
from bson import ObjectId
import shutil
import uuid
import json
import logging
import os

from app.services.ocr_service import extract_coordinates_from_image
from app.services.excel_service import generate_excel
from app.ocr_config import CoordinateOCRConfig, enhance_image_for_coordinates, is_coordinate_in_indonesia
from app.config import db
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR
from app.routes.auth import get_current_admin

router = APIRouter()
logger = logging.getLogger(__name__)

# Collections
history_collection = db["saved_tables"]
temp_collection = db["temp_entries"]

def extract_coordinates_with_validation(image_path: str) -> tuple[str, str]:
    """Extract coordinates with validation (same as inspeksi.py)"""
    try:
        logger.info(f"Extracting coordinates from: {image_path}")
        
        # Step 1: Enhance gambar untuk OCR yang lebih baik
        enhanced_path = enhance_image_for_coordinates(image_path)
        
        # Step 2: Multiple OCR attempts
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
        
        # Step 3: Pilih hasil terbaik
        if coordinates_attempts:
            for lat, lon, source in coordinates_attempts:
                if is_coordinate_in_indonesia(lat, lon):
                    logger.info(f"Selected valid coordinates from {source}: {lat}, {lon}")
                    return lat, lon
            
            # Jika tidak ada yang valid untuk Indonesia, ambil yang pertama
            lat, lon, source = coordinates_attempts[0]
            logger.info(f"Selected coordinates (fallback) from {source}: {lat}, {lon}")
            return lat, lon
        
        logger.warning(f"No coordinates found in image: {image_path}")
        return "", ""
        
    except Exception as e:
        logger.error(f"Error in extract_coordinates_with_validation: {e}")
        return "", ""

@router.get("/history")
async def get_all_history(current_admin: dict = Depends(get_current_admin)):
    """Ambil semua history untuk admin yang sedang login"""
    try:
        admin_id = str(current_admin["_id"])
        
        # Filter history berdasarkan admin_id
        all_data = list(history_collection.find({"admin_id": admin_id}))
        
        # Convert ObjectId to string dan pastikan format tanggal konsisten
        for item in all_data:
            item["_id"] = str(item["_id"])
            
            # Pastikan ada field saved_at yang valid
            if "summary" in item and "created_at" in item["summary"]:
                item["saved_at"] = item["summary"]["created_at"]
            elif "timestamp" in item:
                # Convert timestamp format YYYYMMDD_HHMMSS ke ISO format
                try:
                    timestamp_str = item["timestamp"]
                    dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    item["saved_at"] = dt.isoformat()
                except ValueError:
                    # Fallback ke timestamp string jika parsing gagal
                    item["saved_at"] = datetime.now().isoformat()
            else:
                # Fallback jika tidak ada timestamp
                item["saved_at"] = datetime.now().isoformat()
                
        return all_data
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history data")

@router.post("/generate-ocr-from-history/{item_id}")
async def generate_ocr_excel_from_history(
    item_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Generate Excel file from history images by reprocessing OCR"""
    try:
        admin_id = str(current_admin["_id"])
        object_id = ObjectId(item_id)
        
        # Pastikan history milik admin yang sedang login
        doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        if not doc:
            raise HTTPException(status_code=404, detail="History not found")

        if "data" not in doc or not isinstance(doc["data"], list):
            raise HTTPException(status_code=400, detail="No data found in history")

        history_data = doc["data"]
        if not history_data:
            raise HTTPException(status_code=400, detail="History data is empty")

        logger.info(f"Generating Excel with OCR from history {item_id}, total {len(history_data)} items")

        full_entries = []
        for i, item in enumerate(history_data, start=1):
            try:
                foto_path = item.get("foto_path", "")
                if not foto_path or not Path(foto_path).exists():
                    logger.warning(f"Image file missing for entry {i}: {foto_path}")
                    lintang, bujur = "", ""
                    foto_path = ""
                else:
                    # Re-run OCR
                    lintang, bujur = extract_coordinates_with_validation(str(foto_path))
                    if not lintang or not bujur:
                        logger.warning(f"Failed OCR for entry {i}: {foto_path}")
                        lintang, bujur = "", ""

                entry_complete = {
                    "no": i,
                    "jalur": item.get("jalur", ""),
                    "latitude": lintang,
                    "longitude": bujur,
                    "kondisi": item.get("kondisi", ""),
                    "keterangan": item.get("keterangan", ""),
                    "foto_path": foto_path,
                    "image": foto_path,
                }

                full_entries.append(entry_complete)

            except Exception as e:
                logger.error(f"Error processing OCR from history item {i}: {e}")
                entry_complete = {
                    "no": i,
                    "jalur": item.get("jalur", ""),
                    "latitude": "",
                    "longitude": "",
                    "kondisi": item.get("kondisi", ""),
                    "keterangan": item.get("keterangan", ""),
                    "foto_path": "",
                    "image": "",
                }
                full_entries.append(entry_complete)

        if not full_entries:
            raise HTTPException(status_code=400, detail="No valid data to generate Excel")

        # Generate Excel
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = generate_excel(full_entries, save_dir)

        logger.info(f"Excel with OCR from history generated: {output_path}")

        return FileResponse(
            path=str(output_path),
            filename=f"ocr-history-{item_id[:8]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid history ID format")
    except Exception as e:
        logger.error(f"Error generating OCR Excel from history {item_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate OCR Excel from history: {str(e)}")

@router.post("/generate-from-history/{item_id}")
async def generate_excel_from_history(
    item_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Generate Excel file from history data using existing coordinates"""
    try:
        admin_id = str(current_admin["_id"])
        object_id = ObjectId(item_id)
        
        # Pastikan history milik admin yang sedang login
        doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        if not doc:
            raise HTTPException(status_code=404, detail="History not found")

        if "data" not in doc or not isinstance(doc["data"], list):
            raise HTTPException(status_code=400, detail="No data found in history")

        history_data = doc["data"]
        if not history_data:
            raise HTTPException(status_code=400, detail="History data is empty")

        logger.info(f"Generating Excel from history {item_id}, total {len(history_data)} items")

        full_entries = []
        for i, item in enumerate(history_data, start=1):
            try:
                # Gunakan koordinat yang sudah tersimpan di history
                latitude = item.get("latitude", "") or item.get("lintang", "")
                longitude = item.get("longitude", "") or item.get("bujur", "")
                
                foto_path = item.get("foto_path", "")
                if foto_path and not Path(foto_path).exists():
                    logger.warning(f"Image file missing for entry {i}: {foto_path}")
                    foto_path = ""

                entry_complete = {
                    "no": i,
                    "jalur": item.get("jalur", ""),
                    "latitude": latitude,
                    "longitude": longitude,
                    "kondisi": item.get("kondisi", ""),
                    "keterangan": item.get("keterangan", ""),
                    "foto_path": foto_path,
                    "image": foto_path,
                }

                full_entries.append(entry_complete)

            except Exception as e:
                logger.error(f"Error processing history item {i}: {e}")
                entry_complete = {
                    "no": i,
                    "jalur": item.get("jalur", ""),
                    "latitude": "",
                    "longitude": "",
                    "kondisi": item.get("kondisi", ""),
                    "keterangan": item.get("keterangan", ""),
                    "foto_path": "",
                    "image": "",
                }
                full_entries.append(entry_complete)

        if not full_entries:
            raise HTTPException(status_code=400, detail="No valid data to generate Excel")

        # Generate Excel
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = generate_excel(full_entries, save_dir)

        logger.info(f"Excel from history generated: {output_path}")

        return FileResponse(
            path=str(output_path),
            filename=f"history-{item_id[:8]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid history ID format")
    except Exception as e:
        logger.error(f"Error generating Excel from history {item_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel from history: {str(e)}")

@router.post("/generate-modified-history")
async def generate_modified_history(
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...),
    history_id: str = Form(...),
    current_admin: dict = Depends(get_current_admin)
):
    """Generate Excel from modified history data in EditDashboard"""
    try:
        admin_id = str(current_admin["_id"])
        
        # Parse JSON entries dari FormData
        parsed = [json.loads(e) for e in entries]
        if not parsed:
            raise HTTPException(400, "No entries provided")
        
        logger.info(f"Generating Excel for modified history {history_id} with {len(parsed)} entries and {len(images)} images")
        
        # Ambil data history asli untuk referensi (pastikan milik admin)
        try:
            object_id = ObjectId(history_id)
            original_doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        except:
            original_doc = None
        
        if not original_doc:
            raise HTTPException(status_code=404, detail="History not found or access denied")
        
        # Siapkan data lengkap untuk excel
        full_entries = []
        image_index = 0
        
        for i, entry in enumerate(parsed, start=1):
            try:
                logger.info(f"Processing entry {i}/{len(parsed)} - is_from_history: {entry.get('is_from_history')}")
                
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
                
                # Tentukan sumber gambar
                if entry.get("is_from_history") and entry.get("foto_path"):
                    # Gambar dari history yang tidak diubah
                    foto_path = Path(entry["foto_path"])
                    if foto_path.exists():
                        entry_complete["foto_path"] = str(foto_path)
                        entry_complete["image"] = str(foto_path)
                        # Gunakan koordinat yang sudah ada
                        entry_complete["latitude"] = entry.get("latitude", "")
                        entry_complete["longitude"] = entry.get("longitude", "")
                        logger.info(f"Using existing image for entry {i}: {foto_path}")
                    else:
                        logger.warning(f"History image not found for entry {i}: {foto_path}")
                    
                elif image_index < len(images):
                    # Gambar baru yang di-upload
                    img = images[image_index]
                    image_index += 1
                    
                    logger.info(f"Processing new image {image_index} for entry {i}: {img.filename}")
                    
                    # Validasi format file
                    if img.content_type and not img.content_type.startswith('image/'):
                        logger.warning(f"Invalid content type for entry {i}: {img.content_type}")
                    else:
                        # Simpan gambar sementara
                        ext = Path(img.filename).suffix.lower() if img.filename else '.jpg'
                        if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                            ext = '.jpg'
                        
                        fname = f"{uuid.uuid4().hex}{ext}"
                        save_path = IMAGE_TEMP_DIR / fname
                        IMAGE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
                        
                        # Save uploaded file
                        content = await img.read()
                        with save_path.open("wb") as f:
                            f.write(content)
                        
                        logger.info(f"Saved new image to: {save_path}")
                        
                        # OCR untuk gambar baru
                        try:
                            lintang, bujur = extract_coordinates_with_validation(str(save_path))
                            
                            if lintang and bujur:
                                logger.info(f"New image {i} coordinates: {lintang}, {bujur}")
                                entry_complete["latitude"] = lintang
                                entry_complete["longitude"] = bujur
                            else:
                                logger.warning(f"Failed to extract coordinates from new image {i}")
                        except Exception as ocr_error:
                            logger.error(f"OCR error for entry {i}: {ocr_error}")
                        
                        entry_complete["foto_path"] = str(save_path)
                        entry_complete["image"] = str(save_path)
                else:
                    logger.warning(f"No image available for entry {i} (image_index: {image_index}, total images: {len(images)})")
                
                full_entries.append(entry_complete)
                
            except Exception as e:
                logger.error(f"Error processing modified entry {i}: {e}")
                # Tetap lanjutkan dengan entry minimal
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
            raise HTTPException(400, "No valid data to generate Excel")
        
        # Generate Excel
        save_dir = UPLOAD_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = generate_excel(full_entries, save_dir)
        
        logger.info(f"Modified history Excel generated successfully: {output_path}")
        
        return FileResponse(
            path=str(output_path),
            filename=f"modified-history-{history_id[:8]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating modified history Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate modified Excel: {str(e)}")

@router.get("/history/{item_id}")
async def get_history_by_id(
    item_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Ambil data history berdasarkan ID (untuk EditDashboard)"""
    try:
        admin_id = str(current_admin["_id"])
        object_id = ObjectId(item_id)
        
        # Pastikan history milik admin yang sedang login
        doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        if not doc:
            raise HTTPException(status_code=404, detail="History not found")
        
        # Convert ObjectId to string
        doc["_id"] = str(doc["_id"])
        
        # Pastikan data array ada dan mark sebagai from_history
        if "data" in doc and isinstance(doc["data"], list):
            for item in doc["data"]:
                item["is_from_history"] = True
                # Pastikan foto_filename ada
                if "foto_path" in item and not item.get("foto_filename"):
                    # Extract filename from path
                    item["foto_filename"] = os.path.basename(item["foto_path"])
        
        return doc
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except Exception as e:
        logger.error(f"Error fetching history by ID {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history data")

@router.get("/history/image/{history_id}/{filename}")
async def get_history_image(
    history_id: str, 
    filename: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Endpoint untuk mengambil gambar dari history"""
    try:
        admin_id = str(current_admin["_id"])
        
        # Ambil data history untuk mendapatkan folder path (pastikan milik admin)
        object_id = ObjectId(history_id)
        doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        if not doc:
            raise HTTPException(status_code=404, detail="History not found")
        
        image_path = None
        
        # Method 1: Cari di folder history berdasarkan summary
        if "summary" in doc and "folder_path" in doc["summary"]:
            folder_path = Path(doc["summary"]["folder_path"])
            potential_path = folder_path / filename
            if potential_path.exists() and potential_path.is_file():
                image_path = potential_path
                logger.info(f"Found image via folder_path: {image_path}")
        
        # Method 2: Cari berdasarkan foto_path di data
        if not image_path and "data" in doc:
            for item in doc["data"]:
                if item.get("foto_filename") == filename and item.get("foto_path"):
                    potential_path = Path(item["foto_path"])
                    if potential_path.exists() and potential_path.is_file():
                        image_path = potential_path
                        logger.info(f"Found image via foto_path: {image_path}")
                        break
        
        # Method 3: Cari di semua subfolder IMAGE_SAVED_DIR (dengan admin_id check)
        if not image_path:
            for subfolder in IMAGE_SAVED_DIR.iterdir():
                if subfolder.is_dir():
                    potential_path = subfolder / filename
                    if potential_path.exists() and potential_path.is_file():
                        # Additional check: pastikan gambar ini milik admin
                        # (bisa ditambahkan logic tambahan jika diperlukan)
                        image_path = potential_path
                        logger.info(f"Found image via search: {image_path}")
                        break
        
        if not image_path:
            logger.error(f"Image not found: {filename} for history {history_id}")
            raise HTTPException(status_code=404, detail=f"Image not found: {filename}")
        
        # Tentukan media type berdasarkan extension
        ext = image_path.suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        return FileResponse(
            path=str(image_path),
            media_type=media_type,
            headers={"Cache-Control": "max-age=3600"}
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except Exception as e:
        logger.error(f"Error serving image {filename} for history {history_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve image")

@router.delete("/history/{item_id}")
async def delete_history(
    item_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Hapus riwayat berdasarkan _id"""
    try:
        admin_id = str(current_admin["_id"])
        object_id = ObjectId(item_id)
        
        # Ambil data dulu untuk cleanup file (pastikan milik admin)
        doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        # Hapus folder gambar jika ada
        try:
            if "summary" in doc and "folder_path" in doc["summary"]:
                folder_path = Path(doc["summary"]["folder_path"])
                if folder_path.exists():
                    shutil.rmtree(folder_path)
                    logger.info(f"Deleted folder: {folder_path}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup folder: {cleanup_error}")
        
        # Hapus dari database
        result = history_collection.delete_one({"_id": object_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
            
        return {"message": "Riwayat berhasil dihapus"}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="ID tidak valid")
    except Exception as e:
        logger.error(f"Error deleting history {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete history")

@router.post("/history/edit/{item_id}")
async def load_history_to_dashboard(
    item_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Load History ke Dashboard untuk Edit"""
    try:
        admin_id = str(current_admin["_id"])
        object_id = ObjectId(item_id)
        
        # Pastikan history milik admin yang sedang login
        doc = history_collection.find_one({"_id": object_id, "admin_id": admin_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan")

        # Bersihkan dashboard temporary untuk admin ini
        temp_collection.delete_many({"admin_id": admin_id})
        
        # Load data ke temporary collection
        if "data" in doc and isinstance(doc["data"], list):
            for idx, item in enumerate(doc["data"], start=1):
                item_copy = item.copy()
                item_copy["no"] = idx
                item_copy["admin_id"] = admin_id  # Pastikan admin_id ada
                temp_collection.insert_one(item_copy)
            
            return {
                "message": "Data berhasil dimuat ke dashboard", 
                "count": len(doc["data"])
            }
        else:
            return {"message": "Tidak ada data untuk dimuat", "count": 0}
            
    except ValueError:
        raise HTTPException(status_code=400, detail="ID tidak valid")
    except Exception as e:
        logger.error(f"Error loading history to dashboard {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load history to dashboard")

# Backward compatibility endpoint
@router.delete("/history/delete/{timestamp}")
async def delete_history_by_timestamp(
    timestamp: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Hapus berdasarkan timestamp (backward compatibility)"""
    try:
        admin_id = str(current_admin["_id"])
        
        # Hapus hanya jika milik admin yang sedang login
        result = history_collection.delete_one({
            "timestamp": timestamp,
            "admin_id": admin_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        return {"message": "Riwayat berhasil dihapus"}
    except Exception as e:
        logger.error(f"Error deleting history by timestamp {timestamp}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete history")