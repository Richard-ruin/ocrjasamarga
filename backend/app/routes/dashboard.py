from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
from pathlib import Path
import shutil, uuid
import json
import logging
from datetime import datetime
import cv2
import numpy as np

from app.config import temp_collection, history_collection
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR
from app.services.excel_service import generate_excel
from app.services.ocr_service import extract_coordinates_with_validation
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def save_debug_image(image_path: str, processed_image: np.ndarray, suffix: str = "processed"):
    """
    Simpan gambar hasil preprocessing untuk debugging
    """
    try:
        debug_path = image_path.replace('.jpg', f'_{suffix}.jpg').replace('.jpeg', f'_{suffix}.jpg').replace('.png', f'_{suffix}.png')
        cv2.imwrite(debug_path, processed_image)
        logger.info(f"Debug image saved: {debug_path}")
        return debug_path
    except Exception as e:
        logger.error(f"Failed to save debug image: {e}")
        return None

def validate_image_format(image: UploadFile) -> bool:
    """
    Validasi format gambar yang didukung
    """
    supported_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff']
    return image.content_type in supported_formats

def get_image_info(image_path: str) -> dict:
    """
    Dapatkan informasi gambar untuk debugging
    """
    try:
        img = cv2.imread(image_path)
        if img is not None:
            height, width, channels = img.shape
            return {
                "width": width,
                "height": height,
                "channels": channels,
                "size_mb": round(Path(image_path).stat().st_size / (1024 * 1024), 2)
            }
        return {"error": "Cannot read image"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/generate")
async def generate_excel_report(
    entries: List[str] = Form(...),
    images: List[UploadFile] = File(...)
):
    """
    Generate Excel report dengan koordinat yang diekstrak dari gambar menggunakan OCR
    Enhanced version dengan improved debugging dan error handling
    """
    try:
        parsed_entries = []
        for entry_str in entries:
            try:
                entry_data = json.loads(entry_str)
                parsed_entries.append(entry_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse entry: {entry_str}, error: {e}")
                continue

        if not parsed_entries:
            raise HTTPException(status_code=400, detail="Tidak ada data valid untuk di-generate")

        if len(images) != len(parsed_entries):
            raise HTTPException(
                status_code=400, 
                detail=f"Jumlah gambar ({len(images)}) tidak sesuai dengan jumlah entries ({len(parsed_entries)})"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_folder = IMAGE_TEMP_DIR / f"generate_{timestamp}"
        temp_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"🔄 Generating Excel report for {len(parsed_entries)} entries")
        logger.info(f"📁 Temporary folder: {temp_folder}")

        processed_data = []
        ocr_summary = {"total": len(images), "success": 0, "failed": 0}
        
        for i, (entry, image) in enumerate(zip(parsed_entries, images)):
            entry_num = i + 1
            logger.info(f"\n📋 Processing entry {entry_num}/{len(parsed_entries)}")
            
            try:
                if not validate_image_format(image):
                    logger.warning(f"❌ File {image.filename} format tidak didukung: {image.content_type}")
                    processed_data.append({
                        **entry,
                        "latitude": "",
                        "longitude": "",
                        "image": "",
                        "error": f"Format tidak didukung: {image.content_type}",
                        "original_filename": image.filename or "unknown"
                    })
                    ocr_summary["failed"] += 1
                    continue

                file_extension = Path(image.filename).suffix if image.filename else '.jpg'
                temp_filename = f"temp_img_{entry_num:03d}_{timestamp}{file_extension}"
                temp_image_path = temp_folder / temp_filename

                content = await image.read()
                with open(temp_image_path, "wb") as f:
                    f.write(content)

                img_info = get_image_info(str(temp_image_path))
                logger.info(f"📸 Saved image {entry_num}: {temp_image_path}")
                logger.info(f"📊 Image info: {img_info}")

                logger.info(f"🔍 Starting OCR extraction for image {entry_num}")
                
                try:
                    latitude, longitude = extract_coordinates_with_validation(str(temp_image_path))
                    
                    if latitude and longitude:
                        logger.info(f"✅ Successfully extracted coordinates for image {entry_num}: {latitude}, {longitude}")
                        ocr_summary["success"] += 1
                    else:
                        logger.warning(f"❌ Failed to extract coordinates for image {entry_num}")
                        ocr_summary["failed"] += 1
                    
                except Exception as ocr_error:
                    logger.error(f"❌ OCR error for image {entry_num}: {ocr_error}")
                    latitude, longitude = "", ""
                    ocr_summary["failed"] += 1

                ocr_debug_info = {
                    "image_path": str(temp_image_path),
                    "image_info": img_info,
                    "extracted_lat": latitude,
                    "extracted_lon": longitude,
                    "success": bool(latitude and longitude)
                }
                
                logger.info(f"🔍 OCR Debug info for image {entry_num}: {ocr_debug_info}")

                processed_entry = {
                    **entry,
                    "latitude": latitude,
                    "longitude": longitude,
                    "image": str(temp_image_path),
                    "original_filename": image.filename or f"image_{entry_num}",
                    "ocr_debug": ocr_debug_info
                }
                
                processed_data.append(processed_entry)
                logger.info(f"✅ Processed entry {entry_num}: lat={latitude}, lon={longitude}, file={image.filename}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process entry {entry_num}: {e}")
                error_entry = {
                    **entry,
                    "latitude": "",
                    "longitude": "",
                    "image": "",
                    "error": str(e),
                    "original_filename": image.filename if image else f"image_{entry_num}"
                }
                processed_data.append(error_entry)
                ocr_summary["failed"] += 1

        logger.info(f"\n📊 OCR Summary: {ocr_summary['success']}/{ocr_summary['total']} images successfully processed")
        
        if not processed_data:
            raise HTTPException(status_code=400, detail="Tidak ada data yang berhasil diproses")
        try:
            output_dir = UPLOAD_DIR / "generated_reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            excel_path = generate_excel(processed_data, output_dir)
            
            logger.info(f"📄 Excel report generated successfully: {excel_path}")

            cleanup_temp = ocr_summary["success"] > 0  
            
            if cleanup_temp:
                try:
                    shutil.rmtree(temp_folder)
                    logger.info(f"🧹 Cleaned up temporary folder: {temp_folder}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to cleanup temporary folder: {cleanup_error}")
            else:
                logger.info(f"🔧 Temporary files kept for debugging: {temp_folder}")

            response_headers = {
                "X-OCR-Success": str(ocr_summary["success"]),
                "X-OCR-Failed": str(ocr_summary["failed"]),
                "X-OCR-Total": str(ocr_summary["total"])
            }
            
            return FileResponse(
                path=str(excel_path),
                filename=excel_path.name,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers=response_headers
            )
            
        except Exception as excel_error:
            logger.error(f"❌ Failed to generate Excel: {excel_error}")
            raise HTTPException(status_code=500, detail=f"Gagal generate Excel: {str(excel_error)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in generate_excel_report: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# 🟢 Upload dan Tambah Data Baru
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

