# app/services/excel_service.py - Perbaiki path temporary image
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as ExcelImage
from pathlib import Path
from typing import List
from datetime import datetime
from PIL import Image
import os
import logging
import tempfile
import uuid

logger = logging.getLogger(__name__)

def generate_excel(data: List[dict], save_dir: Path) -> Path:
    """
    Generate Excel file dengan koordinat dari cache data
    """
    template_path = Path("uploads/template.xlsx")
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template Excel tidak ditemukan: {template_path}")
    
    wb = load_workbook(template_path)
    ws = wb.active
    start_row = 9

    logger.info(f"=== EXCEL SERVICE START ===")
    logger.info(f"Generating Excel with {len(data)} entries")

    # ✅ BUAT TEMP DIRECTORY UNTUK GAMBAR
    temp_dir = Path(tempfile.gettempdir()) / "excel_images"
    temp_dir.mkdir(exist_ok=True)
    
    temp_files_to_cleanup = []  # Track files to cleanup

    try:
        for i, entry in enumerate(data):
            row = start_row + i
            
            logger.info(f"=== PROCESSING ROW {row} (Entry {i+1}) ===")
            
            # Basic data
            no_value = entry.get("no", i + 1)
            jalur_value = entry.get("jalur", "")
            
            ws[f'B{row}'] = no_value
            ws[f'C{row}'] = jalur_value

            # ✅ KOORDINAT - Langsung dari cache
            latitude = entry.get("latitude")
            longitude = entry.get("longitude")
            
            logger.info(f"  Coordinates from cache: lat='{latitude}', lon='{longitude}'")
            
            # Set latitude
            if latitude and str(latitude).strip():
                lat_clean = str(latitude).strip()
                ws[f'D{row}'] = lat_clean
                logger.info(f"  ✅ SET D{row} = '{lat_clean}'")
            else:
                ws[f'D{row}'] = ""
                logger.warning(f"  ❌ D{row} empty")
                
            # Set longitude
            if longitude and str(longitude).strip():
                lon_clean = str(longitude).strip()
                ws[f'E{row}'] = lon_clean
                logger.info(f"  ✅ SET E{row} = '{lon_clean}'")
            else:
                ws[f'E{row}'] = ""
                logger.warning(f"  ❌ E{row} empty")

            # Kondisi checkboxes
            kondisi = entry.get("kondisi", "").lower()
            ws[f'F{row}'] = "√" if kondisi == "baik" else ""
            ws[f'G{row}'] = "√" if kondisi == "sedang" else ""
            ws[f'H{row}'] = "√" if kondisi == "buruk" else ""

            # Keterangan
            keterangan_value = entry.get("keterangan", "")
            ws[f'I{row}'] = keterangan_value

            # ✅ FOTO - Perbaiki path temporary
            foto_path = entry.get("foto_path")
            if foto_path and os.path.exists(str(foto_path)):
                try:
                    logger.info(f"  Processing image: {foto_path}")
                    
                    # Buka dan resize gambar
                    img = Image.open(str(foto_path))
                    img.thumbnail((400, 300), Image.Resampling.LANCZOS)
                    
                    # ✅ BUAT PATH TEMPORARY YANG BENAR
                    temp_filename = f"temp_img_{uuid.uuid4().hex}.png"
                    img_temp_path = temp_dir / temp_filename
                    
                    logger.info(f"  Saving temp image to: {img_temp_path}")
                    
                    # Save temporary image
                    img.save(str(img_temp_path), "PNG")
                    temp_files_to_cleanup.append(img_temp_path)
                    
                    # Add to Excel
                    excel_img = ExcelImage(str(img_temp_path))
                    excel_img.width = 120
                    excel_img.height = 90
                    ws.add_image(excel_img, f'J{row}')
                    
                    logger.info(f"  ✅ Image added to J{row}")
                    
                except Exception as e:
                    logger.error(f"  ❌ Image error for row {row}: {e}")
            else:
                logger.warning(f"  No valid image for row {row}: foto_path='{foto_path}'")

        # Save file
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"output-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
        save_path = save_dir / filename
        
        logger.info(f"Saving Excel to: {save_path}")
        wb.save(save_path)
        
        logger.info(f"✅ Excel generation completed: {save_path}")
        return save_path
        
    finally:
        # ✅ CLEANUP TEMPORARY FILES
        for temp_file in temp_files_to_cleanup:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.info(f"Cleaned up temp file: {temp_file}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup {temp_file}: {cleanup_error}")