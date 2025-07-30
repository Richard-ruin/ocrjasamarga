# app/ocr_config.py - Enhanced dengan train project logic untuk fix longitude parsing

import cv2
import numpy as np
import pytesseract
import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class CoordinateOCRConfig:
    """
    Enhanced OCR configuration untuk koordinat GPS
    DENGAN LOGIKA TRAIN PROJECT untuk fix masalah longitude 1073° -> 107°34'
    """
    
    def __init__(self):
        """Initialize dengan konfigurasi optimal dari train project"""
        
        # Set tesseract path untuk Windows (uncomment jika perlu)
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        # OCR configurations yang sudah dioptimalkan berdasarkan train project
        self.ocr_configs = [
            # Config dengan whitelist karakter koordinat (terbaik dari train project)
            {
                'name': 'coordinate_optimized',
                'config': r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
                'description': 'Optimized for GPS coordinates with character whitelist'
            },
            {
                'name': 'single_line_coordinates',
                'config': r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
                'description': 'Single line text with coordinate characters only'
            },
            {
                'name': 'single_word_coordinates',
                'config': r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
                'description': 'Single word mode for tight coordinate text'
            },
            {
                'name': 'raw_line',
                'config': r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
                'description': 'Raw line without structure detection'
            },
            # Fallback configs tanpa whitelist
            {
                'name': 'general_block',
                'config': r'--oem 3 --psm 6',
                'description': 'General block detection fallback'
            },
            {
                'name': 'general_line',
                'config': r'--oem 3 --psm 7',
                'description': 'General single line fallback'
            }
        ]
        
        logger.info("CoordinateOCRConfig initialized with train project logic")

    def read_coordinates_optimized(self, image_path: str) -> List[str]:
        """
        OCR dengan konfigurasi yang dioptimalkan untuk koordinat
        Enhanced version dengan train project logic
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Cannot read image: {image_path}")
                return []
            
            results = []
            
            # Gunakan semua config untuk maximum coverage
            for config_info in self.ocr_configs:
                try:
                    text = pytesseract.image_to_string(img, config=config_info['config'])
                    if text and text.strip():
                        cleaned_text = clean_ocr_text_enhanced(text.strip())
                        results.append(cleaned_text)
                        logger.debug(f"OCR success with {config_info['name']}: {cleaned_text[:50]}...")
                except Exception as e:
                    logger.debug(f"OCR failed with {config_info['name']}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error in read_coordinates_optimized: {e}")
            return []


def enhance_image_for_coordinates(image_path: str) -> str:
    """
    Enhanced image preprocessing dengan multiple methods dari train project
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Cannot read image: {image_path}")
            return image_path
        
        logger.debug(f"Enhancing image with train project methods: {image_path}")
        
        height, width = img.shape[:2]
        
        # Crop area koordinat GPS (sama dengan train project)
        y_start = int(height * 0.72)
        y_end = int(height * 0.76)
        x_start = int(width * 0.25)
        x_end = int(width * 0.96)
        
        cropped_img = img[y_start:y_end, x_start:x_end]
        
        # Enhanced preprocessing dengan multiple methods
        # Convert ke grayscale
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        
        # Invert untuk teks putih di background gelap
        inverted = cv2.bitwise_not(gray)
        
        # Gaussian blur untuk reduce noise
        blurred = cv2.GaussianBlur(inverted, (3, 3), 0)
        
        # Adaptive Gaussian threshold (terbaik dari train project)
        adaptive = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 15, 10
        )
        
        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
        opened = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        
        # Resize untuk meningkatkan resolusi (train project scaling)
        scale_factor = 3
        resized = cv2.resize(opened, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        
        # Save enhanced image
        enhanced_path = str(Path(image_path).with_suffix('')) + '_enhanced.jpg'
        cv2.imwrite(enhanced_path, resized)
        
        logger.debug(f"Enhanced image saved: {enhanced_path}")
        return enhanced_path
        
    except Exception as e:
        logger.error(f"Error in enhance_image_for_coordinates: {e}")
        return image_path

def clean_ocr_text_enhanced(text: str) -> str:
    """
    Enhanced OCR text cleaning dengan train project character corrections
    """
    if not text:
        return ""
    
    # Character corrections dari train project analysis
    char_mapping = {
        'o': '°', 'O': '°', '*': '°', '0': '°',
        '§': '5',  # PENTING: Fix untuk 6° §2' -> 6° 52'
        '/': "'", '\\': "'", '|': "'", 'I': "'",
        ',': '.',
        'Z': 'S',  # Common OCR error
        '`': "'",  # Backtick to apostrophe
        '’': "'",  # Apostrof kanan (U+2019)
        '‘': "'",  # Apostrof kiri (U+2018)
        '′': "'",  # Prime symbol (U+2032)
        '"': '"',  # Smart quote normalization
    }
    
    cleaned = text
    for old_char, new_char in char_mapping.items():
        cleaned = cleaned.replace(old_char, new_char)
    
    # Remove unwanted characters tapi keep coordinate chars
    cleaned = re.sub(r'[^\d°\'\"NSEW\s\.,]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def is_coordinate_in_indonesia(lat_str: str, lon_str: str) -> bool:
    """
    Enhanced validation untuk koordinat Indonesia dengan train project logic
    """
    try:
        if not lat_str or not lon_str:
            return False
        
        # Extract degrees dari DMS format dengan better parsing
        lat_match = re.search(r'(\d+)°', lat_str)
        lon_match = re.search(r'(\d+)°', lon_str)
        
        if lat_match and lon_match:
            lat_deg = int(lat_match.group(1))
            lon_deg = int(lon_match.group(1))
            
            # VALIDASI ADDITIONAL: cek apakah parsing benar
            if lat_deg > 90 or lon_deg > 180:
                logger.warning(f"Invalid coordinate parsing detected: lat={lat_deg}°, lon={lon_deg}°")
                return False
            
            # Indonesia bounds check
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

def extract_coordinates_from_text(text: str) -> Optional[Dict[str, str]]:
    """
    Extract koordinat dari text menggunakan ENHANCED PATTERNS dari train project
    INI YANG AKAN MEMPERBAIKI MASALAH LONGITUDE 1073° -> 107°34'
    """
    if not text:
        return None
        
    try:
        logger.debug(f"Extracting coordinates from text: {text[:100]}...")
        
        # Clean text dengan enhanced cleaning
        cleaned_text = clean_ocr_text_enhanced(text.replace('\n', ' ').replace('\r', ' '))
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        # ENHANCED Coordinate patterns dari train project
        patterns = [
            # Standard format: 6°52'35.622"S 107°34'37.722"E
            r'(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:\.\d+)?)\"\s*([NS])\s*[,\s]*(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:\.\d+)?)\"\s*([EW])',
            
            # With comma decimal: 6°52'35,622"S 107°34'37,722"E
            r'(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:,\d+)?)\"\s*([NS])\s*[,\s]*(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:,\d+)?)\"\s*([EW])',
            
            # With extra spaces: 6° 52' 35.622" S 107° 34' 37.722" E
            r'(\d{1,3})°\s+(\d{1,2})\'\s+(\d{1,2}(?:[.,]\d+)?)\"\s+([NS])\s*[,\s]*(\d{1,3})°\s+(\d{1,2})\'\s+(\d{1,2}(?:[.,]\d+)?)\"\s+([EW])',
            
            # Simplified: 6 52 35.622 S 107 34 37.722 E
            r'(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}(?:[.,]\d+)?)\s+([NS])\s*[,\s]*(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}(?:[.,]\d+)?)\s+([EW])',
            
            # Compact: 6°52'35.622"S107°34'37.722"E
            r'(\d{1,3})°(\d{1,2})\'(\d{1,2}(?:[.,]\d+)?)\"([NS])(\d{1,3})°(\d{1,2})\'(\d{1,2}(?:[.,]\d+)?)\"([EW])',
            
            # OCR errors with Z->S correction
            r'(\d{1,3})°\s*(\d{1,2})[\']*\s*(\d{1,2}(?:[.,]\d+)?)[\"]*\s*([NSEWZ])\s*[,\s]*(\d{1,3})°\s*(\d{1,2})[\']*\s*(\d{1,2}(?:[.,]\d+)?)[\"]*\s*([NSEWZ])',
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 8:
                    # Parse latitude
                    lat_deg, lat_min, lat_sec, lat_dir = groups[0], groups[1], groups[2], groups[3]
                    # Parse longitude  
                    lon_deg, lon_min, lon_sec, lon_dir = groups[4], groups[5], groups[6], groups[7]
                    
                    # VALIDASI COORDINATE VALUES (ini yang akan fix masalah 1073°)
                    try:
                        lat_deg_int = int(lat_deg)
                        lon_deg_int = int(lon_deg)
                        
                        if lat_deg_int > 90 or lon_deg_int > 180:
                            logger.warning(f"Invalid coordinate values detected: lat={lat_deg_int}°, lon={lon_deg_int}°")
                            continue  # Skip pattern ini, coba pattern berikutnya
                            
                    except ValueError:
                        logger.warning(f"Cannot parse coordinate degrees: lat={lat_deg}, lon={lon_deg}")
                        continue
                    
                    # Fix common OCR errors
                    lat_dir = lat_dir.upper()
                    lon_dir = lon_dir.upper()
                    if lat_dir == 'Z': lat_dir = 'S'
                    if lon_dir == 'Z': lon_dir = 'E'
                    
                    # Normalize decimal separator
                    lat_sec = lat_sec.replace(',', '.')
                    lon_sec = lon_sec.replace(',', '.')
                    
                    # Format DMS strings
                    latitude = f"{lat_deg}° {lat_min}' {lat_sec}\" {lat_dir}"
                    longitude = f"{lon_deg}° {lon_min}' {lon_sec}\" {lon_dir}"
                    
                    logger.debug(f"Pattern {i+1} matched: {latitude}, {longitude}")
                    
                    return {
                        'latitude': latitude,
                        'longitude': longitude
                    }
        
        logger.debug("No coordinate patterns matched")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting coordinates from text: {e}")
        return None

# Utility functions untuk debugging (enhanced)
def test_ocr_configs(image_path: str) -> Dict[str, str]:
    """
    Test OCR configs pada gambar untuk debugging dengan enhanced logic
    """
    if not Path(image_path).exists():
        return {}
    
    config = CoordinateOCRConfig()
    results = {}
    
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {}
        
        # Test semua config
        for config_info in config.ocr_configs:
            try:
                text = pytesseract.image_to_string(img, config=config_info['config'])
                cleaned = clean_ocr_text_enhanced(text.strip()) if text else ""
                results[config_info['name']] = cleaned
            except Exception as e:
                results[config_info['name']] = f"ERROR: {str(e)}"
        
        return results
        
    except Exception as e:
        logger.error(f"Error testing OCR configs: {e}")
        return {}

def debug_coordinate_extraction(image_path: str) -> Dict[str, Any]:
    """
    Enhanced debug function untuk testing koordinat extraction
    """
    debug_info = {
        'image_path': image_path,
        'image_exists': Path(image_path).exists(),
        'enhanced_path': '',
        'ocr_results': {},
        'coordinates_found': None,
        'coordinate_parsing_attempts': [],
        'errors': []
    }
    
    try:
        if not debug_info['image_exists']:
            debug_info['errors'].append("Image file not found")
            return debug_info
        
        # Test image enhancement
        enhanced_path = enhance_image_for_coordinates(image_path)
        debug_info['enhanced_path'] = enhanced_path
        
        # Test OCR configs
        ocr_results = test_ocr_configs(enhanced_path)
        debug_info['ocr_results'] = ocr_results
        
        # Test coordinate extraction dengan detailed attempts
        for config_name, text in ocr_results.items():
            if text and not text.startswith('ERROR'):
                coords = extract_coordinates_from_text(text)
                attempt_info = {
                    'config': config_name,
                    'text': text[:100] + "..." if len(text) > 100 else text,
                    'coordinates_found': bool(coords),
                    'coordinates': coords if coords else None,
                    'text_length': len(text)
                }
                debug_info['coordinate_parsing_attempts'].append(attempt_info)
                
                if coords and not debug_info['coordinates_found']:
                    debug_info['coordinates_found'] = {
                        'method': config_name,
                        'coordinates': coords,
                        'text': text,
                        'indonesia_validation': is_coordinate_in_indonesia(coords['latitude'], coords['longitude'])
                    }
        
        return debug_info
        
    except Exception as e:
        debug_info['errors'].append(f"Debug error: {str(e)}")
        return debug_info

def validate_coordinate_parsing(test_text: str) -> Dict[str, Any]:
    """
    Function untuk test parsing koordinat dengan text sample
    """
    result = {
        'input_text': test_text,
        'cleaned_text': clean_ocr_text_enhanced(test_text),
        'coordinates': extract_coordinates_from_text(test_text),
        'parsing_successful': False,
        'indonesia_validation': False
    }
    
    if result['coordinates']:
        result['parsing_successful'] = True
        result['indonesia_validation'] = is_coordinate_in_indonesia(
            result['coordinates']['latitude'], 
            result['coordinates']['longitude']
        )
    
    return result