from openpyxl import load_workbook
from openpyxl.drawing.image import Image as ExcelImage
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import base64
from PIL import Image
import io
import os
import logging

from app.config import settings
from app.models.inspeksi import InspeksiData

logger = logging.getLogger(__name__)

class ExcelService:
    """Service untuk generate Excel file menggunakan template"""
    
    def __init__(self):
        self.template_path = Path(settings.upload_dir) / "template.xlsx"
        self.generated_dir = Path(settings.upload_dir) / "generated"
        self.images_dir = Path(settings.upload_dir) / "images"
        
        # Ensure directories exist
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_excel(self, data: List[InspeksiData], title: str = "Inspeksi Lapangan") -> Dict[str, Any]:
        """
        Generate Excel file dari data inspeksi
        
        Args:
            data: List data inspeksi
            title: Judul inspeksi
            
        Returns:
            Dict dengan informasi file yang digenerate
        """
        try:
            if not self.template_path.exists():
                raise FileNotFoundError(f"Template file not found: {self.template_path}")
            
            # Load template
            wb = load_workbook(self.template_path)
            ws = wb.active
            
            # Set timestamp di cell J4
            current_time = datetime.now()
            time_string = current_time.strftime("%d:%m:%Y")
            ws['J4'] = time_string
            
            logger.info(f"Setting timestamp J4: {time_string}")
            
            # Set title jika ada cell untuk title
            if hasattr(ws, 'J2'):
                ws['J2'] = title
            
            # Fill data starting from row 9
            start_row = 9
            temp_images = []  # Track temporary images for cleanup
            
            for i, entry in enumerate(data):
                row = start_row + i
                
                # Fill basic data
                ws[f'B{row}'] = entry.no
                ws[f'C{row}'] = entry.jalur
                ws[f'D{row}'] = entry.latitude
                ws[f'E{row}'] = entry.longitude
                
                # Set kondisi checkmarks
                kondisi = entry.kondisi.lower()
                if kondisi == "baik":
                    ws[f'F{row}'] = "√"
                    ws[f'G{row}'] = ""
                    ws[f'H{row}'] = ""
                elif kondisi == "sedang":
                    ws[f'F{row}'] = ""
                    ws[f'G{row}'] = "√"
                    ws[f'H{row}'] = ""
                elif kondisi == "buruk":
                    ws[f'F{row}'] = ""
                    ws[f'G{row}'] = ""
                    ws[f'H{row}'] = "√"
                
                # Fill keterangan
                ws[f'I{row}'] = entry.keterangan
                
                # Handle image
                if entry.image_data or entry.image_path:
                    try:
                        img_path = self._process_image_for_excel(entry, row)
                        if img_path:
                            temp_images.append(img_path)
                            
                            # Add image to Excel
                            excel_img = ExcelImage(str(img_path))
                            excel_img.width = 120
                            excel_img.height = 90
                            ws.add_image(excel_img, f'J{row}')
                            
                            logger.info(f"Image added to cell J{row}")
                            
                    except Exception as e:
                        logger.error(f"Failed to process image for row {row}: {e}")
                        # Continue without image
                        continue
            
            # Generate filename
            filename = f"output-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
            save_path = self.generated_dir / filename
            
            # Save workbook
            wb.save(save_path)
            logger.info(f"Excel file saved: {save_path}")
            
            # Cleanup temporary images
            self._cleanup_temp_images(temp_images)
            
            # Get file info
            file_size = save_path.stat().st_size
            
            return {
                "success": True,
                "filename": filename,
                "file_path": str(save_path),
                "relative_path": f"/uploads/generated/{filename}",
                "file_size": file_size,
                "total_items": len(data),
                "generated_at": datetime.utcnow().isoformat(),
                "message": f"Excel file generated successfully with {len(data)} items"
            }
            
        except Exception as e:
            logger.error(f"Excel generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to generate Excel file"
            }
    
    def _process_image_for_excel(self, entry: InspeksiData, row: int) -> Path:
        """
        Process image untuk dimasukkan ke Excel
        
        Args:
            entry: Data inspeksi yang berisi image
            row: Row number untuk nama file
            
        Returns:
            Path ke temporary image file
        """
        try:
            if entry.image_data:
                # Process base64 image data
                if entry.image_data.startswith("data:image"):
                    header, encoded = entry.image_data.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                else:
                    image_bytes = base64.b64decode(entry.image_data)
                
                img = Image.open(io.BytesIO(image_bytes))
                
            elif entry.image_path:
                # Process file path
                if not os.path.exists(entry.image_path):
                    raise FileNotFoundError(f"Image file not found: {entry.image_path}")
                img = Image.open(entry.image_path)
            else:
                return None
            
            # Resize image if too large
            max_size = (300, 225)  # 4:3 ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img
            
            # Save temporary image
            temp_path = self.images_dir / f"temp_excel_img_{row}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            img.save(temp_path, format='PNG', optimize=True)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            return None
    
    def _cleanup_temp_images(self, temp_images: List[Path]):
        """Clean up temporary image files"""
        for img_path in temp_images:
            try:
                if img_path.exists():
                    img_path.unlink()
                    logger.debug(f"Cleaned up temp image: {img_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp image {img_path}: {e}")
    
    def validate_template(self) -> Dict[str, Any]:
        """
        Validate template Excel file
        
        Returns:
            Dict dengan status validasi template
        """
        try:
            if not self.template_path.exists():
                return {
                    "valid": False,
                    "error": f"Template file not found: {self.template_path}",
                    "suggestions": [
                        "Upload template.xlsx file to uploads directory",
                        "Ensure template has proper structure with required columns"
                    ]
                }
            
            # Try to load template
            wb = load_workbook(self.template_path)
            ws = wb.active
            
            # Check basic structure
            required_cells = ['B9', 'C9', 'D9', 'E9', 'F9', 'G9', 'H9', 'I9', 'J9']
            missing_cells = []
            
            for cell in required_cells:
                if ws[cell] is None:
                    missing_cells.append(cell)
            
            return {
                "valid": True,
                "template_path": str(self.template_path),
                "worksheet_name": ws.title,
                "missing_cells": missing_cells,
                "message": "Template validation successful"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "message": "Template validation failed"
            }
    
    def get_template_info(self) -> Dict[str, Any]:
        """Get information about template file"""
        try:
            if not self.template_path.exists():
                return {
                    "exists": False,
                    "error": "Template file not found"
                }
            
            stat = self.template_path.stat()
            
            return {
                "exists": True,
                "path": str(self.template_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            }
            
        except Exception as e:
            return {
                "exists": False,
                "error": str(e)
            }

# Global Excel service instance
excel_service = ExcelService()