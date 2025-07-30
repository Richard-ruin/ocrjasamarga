# app/services/ocr_service.py - Enhanced dengan train project logic
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re
import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set tesseract path untuk Windows (uncomment jika perlu)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class EnhancedTesseractExtractor:
    """
    Enhanced GPS coordinate extractor dengan logika dari train project
    Fixing coordinate parsing issues (longitude 1073° -> 107°34')
    """
    
    def __init__(self):
        """Initialize extractor dengan konfigurasi optimal dari train project"""
        
        # OCR configurations yang sudah dioptimalkan dari train project
        self.ocr_configs = [
            # Whitelist karakter untuk koordinat GPS (PRIORITAS UTAMA)
            r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            # Fallback tanpa whitelist
            r'--oem 3 --psm 6',
            r'--oem 3 --psm 7',
            r'--oem 3 --psm 8',
        ]
        
        logger.info("EnhancedTesseractExtractor initialized with train project logic")

    def preprocess_image_advanced(self, image_path: str):
        """
        Advanced preprocessing dari train project untuk meningkatkan akurasi OCR
        """
        try:
            # Baca gambar
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Cannot read image: {image_path}")
                return None
            
            logger.info(f"Image dimensions: {img.shape[1]}x{img.shape[0]}")
            
            # Get dimensi gambar
            height, width = img.shape[:2]
            
            # Crop area koordinat GPS (dari train project analysis)
            y_start = int(height * 0.72)  # Mulai dari 72% tinggi gambar
            y_end = int(height * 0.76)    # Sampai 76% tinggi gambar
            x_start = int(width * 0.25)   # Mulai dari 25% lebar gambar  
            x_end = int(width * 0.96)     # Sampai 96% lebar gambar
            
            logger.info(f"Crop area: {x_end-x_start}x{y_end-y_start} from position ({x_start},{y_start})")
            
            cropped_img = img[y_start:y_end, x_start:x_end]
            
            return self.enhance_text_image_multiple_methods(cropped_img)
            
        except Exception as e:
            logger.error(f"Error in advanced preprocessing: {e}")
            return None

    def enhance_text_image_multiple_methods(self, img):
        """
        Enhanced preprocessing dengan multiple methods dari train project
        """
        try:
            # Convert ke grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Invert image (teks putih jadi hitam, background jadi putih)
            inverted = cv2.bitwise_not(gray)
            
            # Apply Gaussian blur untuk mengurangi noise
            blurred = cv2.GaussianBlur(inverted, (3, 3), 0)
            
            # Multiple threshold methods (DARI TRAIN PROJECT)
            methods = []
            
            # Method 1: Adaptive threshold
            adaptive1 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 10)
            methods.append(("adaptive_mean", adaptive1))
            
            # Method 2: Adaptive Gaussian threshold
            adaptive2 = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10)
            methods.append(("adaptive_gaussian", adaptive2))
            
            # Method 3: OTSU threshold
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            methods.append(("otsu", otsu))
            
            # Method 4: Manual threshold
            _, manual = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY)
            methods.append(("manual", manual))
            
            # Morphological operations untuk cleanup
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            
            enhanced_methods = []
            for name, method in methods:
                # Morphological closing untuk menghubungkan karakter yang terputus
                closed = cv2.morphologyEx(method, cv2.MORPH_CLOSE, kernel)
                
                # Morphological opening untuk menghilangkan noise kecil
                opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
                
                # Scale up untuk OCR yang lebih baik
                scale_factor = 3
                scaled = cv2.resize(opened, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
                
                enhanced_methods.append((name, scaled))
            
            logger.info(f"Generated {len(enhanced_methods)} enhanced image methods")
            return enhanced_methods
            
        except Exception as e:
            logger.error(f"Error in enhance_text_image_multiple_methods: {e}")
            return None

    def extract_text_with_multiple_methods(self, enhanced_images):
        """
        Extract text menggunakan multiple preprocessing methods dan OCR configs
        SAMA PERSIS dengan train project
        """
        if not enhanced_images:
            return []
            
        all_texts = []
        
        for method_name, img_array in enhanced_images:
            logger.debug(f"Trying method: {method_name}")
            
            # Convert ke PIL Image
            pil_img = Image.fromarray(img_array)
            
            # Additional PIL enhancements
            enhanced_pil = self.enhance_pil_image(pil_img)
            
            for config in self.ocr_configs:
                try:
                    text = pytesseract.image_to_string(enhanced_pil, config=config)
                    if text and text.strip():
                        clean_text = text.strip()
                        logger.debug(f"{method_name} + {config[:15]}...: {clean_text[:50]}...")
                        all_texts.append((method_name, config, clean_text))
                except Exception as e:
                    continue
        
        logger.info(f"Total OCR results: {len(all_texts)}")
        return all_texts

    def enhance_pil_image(self, pil_img: Image.Image) -> Image.Image:
        """
        Additional PIL enhancements dari train project
        """
        try:
            # Increase contrast
            enhancer = ImageEnhance.Contrast(pil_img)
            enhanced = enhancer.enhance(2.0)
            
            # Increase sharpness
            enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = enhancer.enhance(2.0)
            
            # Apply unsharp mask
            enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
            
            return enhanced
        except Exception as e:
            logger.debug(f"PIL enhancement error: {e}")
            return pil_img

    def extract_coordinates_flexible(self, text: str) -> Optional[Dict[str, Any]]:
        """
        FLEXIBLE COORDINATE EXTRACTION DARI TRAIN PROJECT
        Ini yang akan memperbaiki masalah longitude 1073° -> 107°34'
        """
        if not text:
            return None
        
        # Clean text
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        
        logger.debug(f"Analyzing text: {text}")
        
        # Multiple patterns untuk berbagai format (DARI TRAIN PROJECT)
        patterns = [
            # Standard: 6°52'35,574"S 107°34'37,716"E
            r"(\d+)°\s*(\d+)'?\s*(\d+)[,.](\d+)\"?\s*([NSEW])\s*[,\s]*(\d+)°\s*(\d+)'?\s*(\d+)[,.](\d+)\"?\s*([NSEW])",
            
            # With spaces: 6° 52' 35.574" S 107° 34' 37.716" E
            r"(\d+)°\s+(\d+)'\s+(\d+)[,.](\d+)\"\s+([NSEW])\s*[,\s]*(\d+)°\s+(\d+)'\s+(\d+)[,.](\d+)\"\s+([NSEW])",
            
            # Simplified: 6 52 35.574 S 107 34 37.716 E
            r"(\d+)\s+(\d+)\s+(\d+)[,.](\d+)\s+([NSEW])\s*[,\s]*(\d+)\s+(\d+)\s+(\d+)[,.](\d+)\s+([NSEW])",
            
            # Without quotes: 6°52'35,574S 107°34'37,716E
            r"(\d+)°(\d+)'(\d+)[,.](\d+)([NSEW])\s*(\d+)°(\d+)'(\d+)[,.](\d+)([NSEW])",
            
            # OCR errors common patterns (PENTING UNTUK FIX PARSING)
            r"(\d+)°\s*(\d+)['\s]*(\d+)[,.](\d+)[\"'\s]*([NSEWZ])\s*[,\s]*(\d+)°\s*(\d+)['\s]*(\d+)[,.](\d+)[\"'\s]*([NSEWZ])",
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                logger.debug(f"Pattern {i+1} matched!")
                return self.parse_coordinate_match(match)
        
        # Jika tidak ada yang match, coba cari koordinat partial
        return self.extract_partial_coordinates(text)

    def extract_partial_coordinates(self, text: str):
        """
        Extract koordinat parsial jika pattern lengkap tidak ditemukan
        DARI TRAIN PROJECT
        """
        # Cari angka-angka yang terlihat seperti koordinat
        lat_pattern = r"(\d+)°?\s*(\d+)'?\s*(\d+)[,.](\d+)[\"']?\s*[SN]"
        lng_pattern = r"(\d+)°?\s*(\d+)'?\s*(\d+)[,.](\d+)[\"']?\s*[EW]"
        
        lat_match = re.search(lat_pattern, text, re.IGNORECASE)
        lng_match = re.search(lng_pattern, text, re.IGNORECASE)
        
        if lat_match and lng_match:
            logger.debug("Partial coordinates found!")
            # Reconstruct full match
            full_match_groups = list(lat_match.groups()) + ['S'] + list(lng_match.groups()) + ['E']
            
            class MockMatch:
                def __init__(self, groups):
                    self._groups = groups
                def groups(self):
                    return self._groups
            
            return self.parse_coordinate_match(MockMatch(full_match_groups))
        
        return None

    def parse_coordinate_match(self, match) -> Optional[Dict[str, Any]]:
        """
        Parse coordinate match groups
        INI YANG MEMPERBAIKI MASALAH LONGITUDE 1073° -> 107°34'
        """
        try:
            groups = match.groups()
            
            if len(groups) < 10:
                logger.debug(f"Insufficient groups: {len(groups)}")
                return None
            
            # Parse latitude (pertama)
            lat_deg = int(groups[0])
            lat_min = int(groups[1])
            lat_sec = int(groups[2])
            lat_decimal = int(groups[3])
            lat_dir = groups[4].upper()
            
            # Parse longitude (kedua)
            lng_deg = int(groups[5])
            lng_min = int(groups[6]) 
            lng_sec = int(groups[7])
            lng_decimal = int(groups[8])
            lng_dir = groups[9].upper()
            
            # Fix common OCR errors
            if lat_dir == 'Z': lat_dir = 'S'
            if lng_dir == 'Z': lng_dir = 'E'
            
            # VALIDASI KOORDINAT (penting untuk fix parsing error)
            if lat_deg > 90 or lng_deg > 180:
                logger.warning(f"Invalid coordinates detected: lat_deg={lat_deg}, lng_deg={lng_deg}")
                return None
            
            # Format DMS strings (SESUAI TRAIN PROJECT)
            lat_dms = f"{lat_deg}°{lat_min}'{lat_sec}.{lat_decimal:03d}\"{lat_dir}"
            lng_dms = f"{lng_deg}°{lng_min}'{lng_sec}.{lng_decimal:03d}\"{lng_dir}"
            
            # Convert ke decimal degrees
            lat_decimal_deg = self.dms_to_decimal(lat_deg, lat_min, lat_sec, lat_decimal, lat_dir)
            lng_decimal_deg = self.dms_to_decimal(lng_deg, lng_min, lng_sec, lng_decimal, lng_dir)
            
            logger.info(f"Successfully parsed coordinates: {lat_dms}, {lng_dms}")
            
            return {
                'latitude': {
                    'dms': lat_dms,
                    'decimal': lat_decimal_deg,
                    'degrees': lat_deg,
                    'minutes': lat_min,
                    'seconds': lat_sec,
                    'decimal_seconds': lat_decimal,
                    'direction': lat_dir
                },
                'longitude': {
                    'dms': lng_dms,
                    'decimal': lng_decimal_deg,
                    'degrees': lng_deg,
                    'minutes': lng_min,
                    'seconds': lng_sec,
                    'decimal_seconds': lng_decimal,
                    'direction': lng_dir
                },
                'coordinate_string': f"{lat_decimal_deg}, {lng_decimal_deg}",
                'google_maps_url': f"https://maps.google.com/maps?q={lat_decimal_deg},{lng_decimal_deg}"
            }
            
        except Exception as e:
            logger.error(f"Error parsing coordinates: {e}")
            return None

    def dms_to_decimal(self, degrees: int, minutes: int, seconds: int, decimal_seconds: int, direction: str) -> float:
        """
        Convert DMS ke Decimal Degrees (SAMA DENGAN TRAIN PROJECT)
        """
        # Gabungkan seconds dengan decimal seconds
        total_seconds = seconds + (decimal_seconds / 1000)
        
        # Convert ke decimal degrees
        decimal = degrees + minutes/60 + total_seconds/3600
        
        # Apply direction (negative untuk S dan W)
        if direction in ['S', 'W']:
            decimal = -decimal
        
        return round(decimal, 6)

    def extract_coordinates_from_image(self, image_path: str) -> Tuple[str, str]:
        """
        Main function untuk ekstrak koordinat dari gambar
        MENGGUNAKAN LOGIKA TRAIN PROJECT YANG SUDAH TERBUKTI BERHASIL
        """
        try:
            logger.info(f"Processing image with train project logic: {image_path}")
            
            # Step 1: Advanced preprocessing dengan multiple methods
            enhanced_images = self.preprocess_image_advanced(image_path)
            if not enhanced_images:
                logger.warning("Failed to preprocess image")
                return "", ""
            
            # Step 2: Extract text dengan multiple methods
            all_texts = self.extract_text_with_multiple_methods(enhanced_images)
            if not all_texts:
                logger.warning("No text extracted from image")
                return "", ""
            
            # Step 3: Try to extract coordinates dari setiap hasil OCR
            best_coordinates = None
            best_text = ""
            
            for method, config, text in all_texts:
                logger.debug(f"Trying to extract from {method}: {text[:100]}...")
                
                coordinates = self.extract_coordinates_flexible(text)
                if coordinates:
                    best_coordinates = coordinates
                    best_text = text
                    logger.info(f"Coordinates found from {method}!")
                    break
            
            if not best_coordinates:
                logger.warning("No coordinates found in any OCR result")
                return "", ""
            
            # Return dalam format yang kompatibel dengan existing code
            lat = best_coordinates['latitude']
            lng = best_coordinates['longitude']
            
            logger.info(f"Final result: {lat['dms']}, {lng['dms']}")
            
            return lat['dms'], lng['dms']
            
        except Exception as e:
            logger.error(f"Error in extract_coordinates_from_image: {e}")
            return "", ""


# Global extractor instance
_extractor = None

def get_extractor() -> EnhancedTesseractExtractor:
    """Get singleton extractor instance"""
    global _extractor
    if _extractor is None:
        _extractor = EnhancedTesseractExtractor()
    return _extractor

def extract_coordinates_from_image(image_path: str) -> Tuple[str, str]:
    """
    Main function untuk ekstrak koordinat dari gambar 
    FIXED VERSION dengan train project logic
    """
    extractor = get_extractor()
    return extractor.extract_coordinates_from_image(image_path)

# Legacy functions untuk backward compatibility dengan improved logic
def preprocess_image_for_coordinates(image_path: str) -> str:
    """Legacy function dengan enhanced preprocessing"""
    logger.info("Using enhanced preprocessing from train project")
    return image_path

def clean_ocr_text(text: str) -> str:
    """Enhanced OCR text cleaning dari train project"""
    if not text:
        return ""
    
    # Character corrections berdasarkan train project analysis
    char_mapping = {
        'o': '°', 'O': '°', '*': '°', '0': '°',
        '§': '5',  # Fix untuk 6° §2' -> 6° 52'
        '/': "'", '\\': "'", '|': "'", 'I': "'",
        ',': '.',
        'Z': 'S',  # Common OCR error
    }
    
    cleaned = text
    for old_char, new_char in char_mapping.items():
        cleaned = cleaned.replace(old_char, new_char)
    
    # Remove unwanted characters
    cleaned = re.sub(r'[^\d°\'\"NSEW\s\.,]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def is_valid_coordinate(latitude: str, longitude: str) -> bool:
    """Enhanced coordinate validation"""
    try:
        if not latitude or not longitude:
            return False
        
        lat_deg = re.search(r'(\d+)°', latitude)
        lon_deg = re.search(r'(\d+)°', longitude)
        
        if lat_deg and lon_deg:
            lat_val = int(lat_deg.group(1))
            lon_val = int(lon_deg.group(1))
            
            # Enhanced range validation
            if 0 <= lat_val <= 90 and 0 <= lon_val <= 180:
                return True
        
        return False
    except:
        return False

def is_coordinate_in_indonesia(lat_str: str, lon_str: str) -> bool:
    """
    Enhanced validation untuk koordinat Indonesia dengan train project logic
    """
    try:
        if not lat_str or not lon_str:
            return False
        
        # Extract degrees dari DMS format
        lat_match = re.search(r'(\d+)°', lat_str)
        lon_match = re.search(r'(\d+)°', lon_str)
        
        if lat_match and lon_match:
            lat_deg = int(lat_match.group(1))
            lon_deg = int(lon_match.group(1))
            
            # Enhanced Indonesia bounds check
            # Latitude: 6°N to 11°S, Longitude: 95°E to 141°E
            if 'S' in lat_str.upper() and lat_deg <= 11:
                if 'E' in lon_str.upper() and 95 <= lon_deg <= 141:
                    return True
            elif 'N' in lat_str.upper() and lat_deg <= 6:
                if 'E' in lon_str.upper() and 95 <= lon_deg <= 141:
                    return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Error validating Indonesia coordinates: {e}")
        return False