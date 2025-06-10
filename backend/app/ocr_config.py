# ocr_config.py - Konfigurasi tambahan untuk OCR yang lebih optimal

import easyocr
import cv2
import numpy as np
from typing import List, Dict, Any

class CoordinateOCRConfig:
    """
    Kelas untuk konfigurasi OCR yang dioptimalkan untuk koordinat
    """
    
    def __init__(self):
        # Inisialisasi reader dengan konfigurasi optimal
        self.reader = easyocr.Reader(
            ['en'], 
            gpu=False,
            verbose=False,
            download_enabled=True
        )
        
        # Parameter OCR yang dioptimalkan untuk koordinat
        self.ocr_params = {
            'width_ths': 0.7,      # Threshold untuk lebar karakter
            'height_ths': 0.7,     # Threshold untuk tinggi karakter
            'decoder': 'greedy',   # Decoder yang lebih cepat untuk text sederhana
            'beamWidth': 5,        # Beam width untuk decoder
            'batch_size': 1,       # Batch size
            'workers': 1,          # Jumlah worker
            'allowlist': '0123456789°\'\"NSEW.,-', # Karakter yang diizinkan
            'paragraph': False,    # Tidak perlu paragraph detection
            'x_ths': 1.0,         # Threshold untuk penggabungan text horizontal
            'y_ths': 0.5,         # Threshold untuk penggabungan text vertical
        }
    
    def read_coordinates_optimized(self, image_path: str) -> List[str]:
        """
        Baca teks dengan parameter yang dioptimalkan untuk koordinat
        """
        try:
            result = self.reader.readtext(
                image_path, 
                detail=0,
                paragraph=self.ocr_params['paragraph'],
                width_ths=self.ocr_params['width_ths'],
                height_ths=self.ocr_params['height_ths'],
                x_ths=self.ocr_params['x_ths'],
                y_ths=self.ocr_params['y_ths']
            )
            return result
        except Exception as e:
            print(f"Error in optimized OCR: {e}")
            return []

def enhance_image_for_coordinates(image_path: str) -> str:
    """
    Enhancement gambar yang lebih agresif untuk koordinat
    """
    try:
        # Baca gambar
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        # Convert ke grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Gaussian blur untuk mengurangi noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 2. Adaptive threshold dengan parameter yang dioptimalkan
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 15, 4
        )
        
        # 3. Morphological operations untuk membersihkan noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # 4. Sharpening untuk memperjelas karakter
        kernel_sharp = np.array([[-1,-1,-1], 
                                [-1, 9,-1], 
                                [-1,-1,-1]])
        sharpened = cv2.filter2D(cleaned, -1, kernel_sharp)
        
        # 5. Resize gambar untuk meningkatkan resolusi
        height, width = sharpened.shape
        new_width = int(width * 2)
        new_height = int(height * 2)
        resized = cv2.resize(sharpened, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Simpan hasil enhancement
        enhanced_path = image_path.replace('.', '_enhanced.')
        cv2.imwrite(enhanced_path, resized)
        
        return enhanced_path
        
    except Exception as e:
        print(f"Error in image enhancement: {e}")
        return image_path

def segment_coordinate_region(image_path: str) -> List[str]:
    """
    Segmentasi region yang kemungkinan mengandung koordinat
    """
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Deteksi kontur untuk menemukan area text
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        segments = []
        
        for i, contour in enumerate(contours):
            # Filter contour berdasarkan area dan aspect ratio
            area = cv2.contourArea(contour)
            if area > 100:  # Minimum area
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                # Area yang kemungkinan mengandung koordinat (horizontal text)
                if 2 < aspect_ratio < 20 and w > 50:
                    # Crop region
                    roi = img[y:y+h, x:x+w]
                    segment_path = image_path.replace('.', f'_segment_{i}.')
                    cv2.imwrite(segment_path, roi)
                    segments.append(segment_path)
        
        return segments
        
    except Exception as e:
        print(f"Error in segmentation: {e}")
        return [image_path]

# Fungsi utilitas tambahan
def validate_dms_format(coord_str: str) -> bool:
    """
    Validasi format DMS (Degrees Minutes Seconds)
    """
    pattern = r'^\d{1,3}°\s*\d{1,2}\'\s*\d{1,2}(?:\.\d+)?\"\s*[NSEW]$'
    return bool(re.match(pattern, coord_str.strip()))

def convert_dms_to_decimal(dms_str: str) -> float:
    """
    Konversi DMS ke decimal degrees untuk validasi
    """
    try:
        import re
        parts = re.findall(r'(\d+(?:\.\d+)?)', dms_str)
        direction = re.findall(r'[NSEW]', dms_str.upper())[0]
        
        if len(parts) >= 3:
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            
            decimal = degrees + (minutes / 60) + (seconds / 3600)
            
            # Negative untuk South dan West
            if direction in ['S', 'W']:
                decimal = -decimal
                
            return decimal
        return 0.0
    except:
        return 0.0

def is_coordinate_in_indonesia(lat_str: str, lon_str: str) -> bool:
    """
    Validasi apakah koordinat berada di wilayah Indonesia
    """
    try:
        lat_decimal = convert_dms_to_decimal(lat_str)
        lon_decimal = convert_dms_to_decimal(lon_str)
        
        # Batas wilayah Indonesia (approximate)
        # Latitude: 6°N to 11°S
        # Longitude: 95°E to 141°E
        if -11 <= lat_decimal <= 6 and 95 <= lon_decimal <= 141:
            return True
        return False
    except:
        return False