import paddleocr
import cv2
import numpy as np
from PIL import Image
import io
import base64
import logging
from typing import Tuple, Optional, Dict, Any
import re
from datetime import datetime

from app.config import settings
from app.utils.helpers import extract_gps_from_text, parse_address_from_text

logger = logging.getLogger(__name__)

class OCRService:
    """Service untuk OCR menggunakan PaddleOCR"""
    
    def __init__(self):
        self.ocr = None
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Initialize PaddleOCR engine"""
        try:
            self.ocr = paddleocr.PaddleOCR(
                use_angle_cls=True,
                lang=settings.ocr_language,
                use_gpu=settings.ocr_gpu,
                show_log=False
            )
            logger.info("PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise e
    
    def process_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Process image dengan OCR dan extract informasi
        
        Args:
            image_data: Binary data gambar
            
        Returns:
            Dict dengan hasil OCR dan koordinat yang diekstrak
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                raise ValueError("Invalid image data")
            
            # Preprocess image untuk OCR yang lebih baik
            processed_image = self._preprocess_image(image)
            
            # Jalankan OCR
            ocr_result = self.ocr.ocr(processed_image, cls=True)
            
            # Extract text dari hasil OCR
            raw_text = self._extract_text_from_result(ocr_result)
            
            # Extract koordinat GPS
            latitude, longitude = extract_gps_from_text(raw_text)
            
            # Extract informasi alamat
            address_info = parse_address_from_text(raw_text)
            
            # Extract timestamp jika ada
            timestamp = self._extract_timestamp_from_text(raw_text)
            
            # Extract arah kompas jika ada
            compass_direction = self._extract_compass_direction(raw_text)
            
            result = {
                "success": True,
                "raw_text": raw_text,
                "coordinates": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "valid": latitude is not None and longitude is not None
                },
                "address": address_info,
                "timestamp": timestamp,
                "compass_direction": compass_direction,
                "ocr_confidence": self._calculate_confidence(ocr_result),
                "processed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"OCR processing successful. Coordinates found: {latitude}, {longitude}")
            return result
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_text": "",
                "coordinates": {"latitude": None, "longitude": None, "valid": False},
                "processed_at": datetime.utcnow().isoformat()
            }
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image untuk meningkatkan akurasi OCR
        Optimized untuk text dengan background hitam dan font putih
        """
        # Convert ke grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Untuk text putih di background hitam, invert image
        # Karena PaddleOCR bekerja lebih baik dengan text hitam di background putih
        inverted = cv2.bitwise_not(gray)
        
        # Noise reduction
        denoised = cv2.fastNlMeansDenoising(inverted)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Gaussian blur untuk smooth text
        blurred = cv2.GaussianBlur(enhanced, (1, 1), 0)
        
        # Threshold untuk binary image
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _extract_text_from_result(self, ocr_result: list) -> str:
        """Extract text dari hasil OCR PaddleOCR"""
        if not ocr_result or not ocr_result[0]:
            return ""
        
        texts = []
        for line in ocr_result[0]:
            if len(line) >= 2:
                text = line[1][0] if isinstance(line[1], tuple) else line[1]
                texts.append(text)
        
        return "\n".join(texts)
    
    def _calculate_confidence(self, ocr_result: list) -> float:
        """Calculate average confidence dari OCR result"""
        if not ocr_result or not ocr_result[0]:
            return 0.0
        
        confidences = []
        for line in ocr_result[0]:
            if len(line) >= 2 and isinstance(line[1], tuple) and len(line[1]) >= 2:
                confidences.append(line[1][1])
        
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _extract_timestamp_from_text(self, text: str) -> Optional[str]:
        """Extract timestamp dari OCR text"""
        # Pattern untuk berbagai format tanggal
        date_patterns = [
            r"\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}\.\d{2}\.\d{2}",  # 13 Jun 2025 12.59.06
            r"\d{1,2}/\d{1,2}/\d{4}\s+\d{2}:\d{2}:\d{2}",      # 13/06/2025 12:59:06
            r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}",          # 2025-06-13 12:59:06
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_compass_direction(self, text: str) -> Optional[str]:
        """Extract arah kompas dari OCR text"""
        # Pattern untuk arah kompas
        compass_pattern = r"\d+°\s*[NSEW]{1,2}"
        
        match = re.search(compass_pattern, text)
        if match:
            return match.group(0)
        
        return None
    
    def process_base64_image(self, base64_data: str) -> Dict[str, Any]:
        """
        Process image dari base64 data
        
        Args:
            base64_data: Base64 encoded image data
            
        Returns:
            Dict dengan hasil OCR
        """
        try:
            # Remove data URL prefix if present
            if base64_data.startswith("data:image"):
                base64_data = base64_data.split(",", 1)[1]
            
            # Decode base64
            image_data = base64.b64decode(base64_data)
            
            return self.process_image(image_data)
            
        except Exception as e:
            logger.error(f"Failed to process base64 image: {e}")
            return {
                "success": False,
                "error": f"Failed to decode base64 image: {str(e)}",
                "coordinates": {"latitude": None, "longitude": None, "valid": False}
            }
    
    def extract_location_info(self, text: str) -> Dict[str, Any]:
        """
        Extract informasi lokasi lengkap dari text OCR
        Khusus untuk format aplikasi GPS Indonesia
        """
        info = {
            "street": None,
            "district": None,
            "subdistrict": None,
            "city": None,
            "province": None,
            "postal_code": None
        }
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Identifikasi komponen alamat berdasarkan kata kunci Indonesia
            if any(keyword in line.lower() for keyword in ['jalan', 'jl.', 'street']):
                info['street'] = line
            elif 'kecamatan' in line.lower():
                info['district'] = line.replace('Kecamatan', '').strip()
            elif any(keyword in line.lower() for keyword in ['kelurahan', 'desa']):
                info['subdistrict'] = line
            elif any(keyword in line.lower() for keyword in ['kota', 'kabupaten']):
                info['city'] = line
            elif any(keyword in line.lower() for keyword in ['provinsi', 'province']):
                info['province'] = line
            elif re.match(r'\d{5}', line):  # 5 digit postal code
                info['postal_code'] = line
        
        return info

# Global OCR service instance
ocr_service = OCRService()