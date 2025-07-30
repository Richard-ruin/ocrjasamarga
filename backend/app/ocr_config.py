# app/ocr_config.py - Enhanced OCR configuration untuk Tesseract

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
    Enhanced OCR configuration untuk koordinat GPS menggunakan Tesseract
    Migrasi dari EasyOCR dengan optimasi khusus untuk koordinat
    """
    
    def __init__(self):
        """Initialize dengan konfigurasi optimal untuk koordinat"""
        
        # Set tesseract path untuk Windows (uncomment jika perlu)
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        # OCR configurations yang dioptimalkan untuk koordinat GPS
        self.ocr_configs = [
            # Config dengan whitelist karakter koordinat
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
            },
            {
                'name': 'general_word',
                'config': r'--oem 3 --psm 8',
                'description': 'General single word fallback'
            }
        ]
        
        logger.info("CoordinateOCRConfig initialized with Tesseract")

    def read_coordinates_optimized(self, image_path: str) -> List[str]:
        """
        OCR dengan konfigurasi yang dioptimalkan untuk koordinat
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Cannot read image: {image_path}")
                return []
            
            results = []
            
            for config_info in self.ocr_configs:
                try:
                    text = pytesseract.image_to_string(img, config=config_info['config'])
                    if text and text.strip():
                        results.append(text.strip())
                        logger.debug(f"OCR success with {config_info['name']}: {text.strip()[:50]}...")
                except Exception as e:
                    logger.debug(f"OCR failed with {config_info['name']}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error in read_coordinates_optimized: {e}")
            return []

    def extract_text_from_regions(self, image_path: str, regions: List[Dict]) -> Dict[str, List[str]]:
        """
        Extract text dari region-region spesifik dalam gambar
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {}
            
            results = {}
            
            for region in regions:
                region_name = region.get('name', 'unknown')
                x, y, w, h = region['x'], region['y'], region['width'], region['height']
                
                # Crop region
                roi = img[y:y+h, x:x+w]
                
                # OCR pada region
                region_texts = []
                for config_info in self.ocr_configs[:4]:  # Use first 4 configs only
                    try:
                        text = pytesseract.image_to_string(roi, config=config_info['config'])
                        if text and text.strip():
                            region_texts.append(text.strip())
                    except:
                        continue
                
                results[region_name] = region_texts
            
            return results
            
        except Exception as e:
            logger.error(f"Error in extract_text_from_regions: {e}")
            return {}


def enhance_image_for_coordinates(image_path: str) -> str:
    """
    Enhanced image preprocessing khusus untuk koordinat GPS
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Cannot read image: {image_path}")
            return image_path
        
        logger.debug(f"Enhancing image: {image_path}")
        
        # Convert ke grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Invert untuk teks putih di background gelap
        inverted = cv2.bitwise_not(gray)
        
        # Gaussian blur untuk reduce noise
        blurred = cv2.GaussianBlur(inverted, (3, 3), 0)
        
        # Adaptive threshold untuk kontras yang lebih baik
        adaptive = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 15, 4
        )
        
        # Morphological operations untuk cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        cleaned = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
        
        # Sharpening untuk karakter yang lebih jelas
        kernel_sharp = np.array([[-1,-1,-1], [-1, 9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(cleaned, -1, kernel_sharp)
        
        # Resize untuk meningkatkan resolusi
        height, width = sharpened.shape
        new_width = int(width * 2.5)
        new_height = int(height * 2.5)
        resized = cv2.resize(sharpened, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Save enhanced image
        enhanced_path = str(Path(image_path).with_suffix('')) + '_enhanced.jpg'
        cv2.imwrite(enhanced_path, resized)
        
        logger.debug(f"Enhanced image saved: {enhanced_path}")
        return enhanced_path
        
    except Exception as e:
        logger.error(f"Error in enhance_image_for_coordinates: {e}")
        return image_path

def segment_coordinate_region(image_path: str) -> List[str]:
    """
    Segmentasi gambar untuk fokus pada area koordinat
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return [image_path]
        
        height, width = img.shape[:2]
        
        # Define regions yang kemungkinan mengandung koordinat
        regions = [
            # Full coordinate area (center-bottom of overlay)
            {
                'name': 'full_coords',
                'y_start': int(height * 0.68),
                'y_end': int(height * 0.80),
                'x_start': int(width * 0.05),
                'x_end': int(width * 0.95)
            },
            # Upper coordinate area  
            {
                'name': 'upper_coords',
                'y_start': int(height * 0.70),
                'y_end': int(height * 0.76),
                'x_start': int(width * 0.10),
                'x_end': int(width * 0.90)
            },
            # Lower coordinate area
            {
                'name': 'lower_coords', 
                'y_start': int(height * 0.74),
                'y_end': int(height * 0.78),
                'x_start': int(width * 0.10),
                'x_end': int(width * 0.90)
            }
        ]
        
        segments = []
        
        for region in regions:
            try:
                y_start = region['y_start']
                y_end = region['y_end']
                x_start = region['x_start']
                x_end = region['x_end']
                
                # Crop region
                roi = img[y_start:y_end, x_start:x_end]
                
                # Save segment
                segment_path = str(Path(image_path).with_suffix('')) + f"_segment_{region['name']}.jpg"
                cv2.imwrite(segment_path, roi)
                segments.append(segment_path)
                
                logger.debug(f"Segment saved: {segment_path}")
                
            except Exception as e:
                logger.debug(f"Error creating segment {region['name']}: {e}")
                continue
        
        return segments if segments else [image_path]
        
    except Exception as e:
        logger.error(f"Error in segment_coordinate_region: {e}")
        return [image_path]

def validate_dms_format(coord_str: str) -> bool:
    """
    Validasi format DMS (Degrees Minutes Seconds)
    """
    if not coord_str:
        return False
    
    # Pattern untuk DMS format
    pattern = r'^\d{1,3}°\s*\d{1,2}\'\s*\d{1,2}(?:\.\d+)?\"\s*[NSEW]$'
    return bool(re.match(pattern, coord_str.strip()))

def convert_dms_to_decimal(dms_str: str) -> float:
    """
    Convert DMS string ke decimal degrees
    """
    try:
        if not dms_str:
            return 0.0
        
        # Extract numbers dan direction
        parts = re.findall(r'(\d+(?:\.\d+)?)', dms_str)
        direction_match = re.search(r'[NSEW]', dms_str.upper())
        
        if len(parts) >= 3 and direction_match:
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            direction = direction_match.group()
            
            # Convert ke decimal degrees
            decimal = degrees + (minutes / 60) + (seconds / 3600)
            
            # Apply direction (negative untuk South dan West)
            if direction in ['S', 'W']:
                decimal = -decimal
                
            return round(decimal, 6)
        
        return 0.0
        
    except Exception as e:
        logger.debug(f"Error converting DMS to decimal: {e}")
        return 0.0

def is_coordinate_in_indonesia(lat_str: str, lon_str: str) -> bool:
    """
    Validasi apakah koordinat berada di wilayah Indonesia
    """
    try:
        if not lat_str or not lon_str:
            return False
        
        lat_decimal = convert_dms_to_decimal(lat_str)
        lon_decimal = convert_dms_to_decimal(lon_str)
        
        # Batas wilayah Indonesia (approximate)
        # Latitude: 6°N to 11°S (-11 to 6)
        # Longitude: 95°E to 141°E (95 to 141)
        indonesia_bounds = {
            'lat_min': -11,
            'lat_max': 6,
            'lon_min': 95,
            'lon_max': 141
        }
        
        if (indonesia_bounds['lat_min'] <= lat_decimal <= indonesia_bounds['lat_max'] and
            indonesia_bounds['lon_min'] <= lon_decimal <= indonesia_bounds['lon_max']):
            return True
        
        logger.debug(f"Coordinates outside Indonesia: {lat_decimal}, {lon_decimal}")
        return False
        
    except Exception as e:
        logger.debug(f"Error validating Indonesia coordinates: {e}")
        return False

def extract_coordinates_from_text(text: str) -> Optional[Dict[str, str]]:
    """
    Extract koordinat dari text menggunakan regex patterns
    """
    if not text:
        return None
        
    try:
        logger.debug(f"Extracting coordinates from text: {text[:100]}...")
        
        # Clean text
        cleaned_text = text.replace('\n', ' ').replace('\r', ' ')
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        # Multiple coordinate patterns
        patterns = [
            # Standard format: 6°52'35.622"S 107°34'37.722"E
            r'(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:\.\d+)?)\"\s*([NS])\s+(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:\.\d+)?)\"\s*([EW])',
            
            # With comma decimal: 6°52'35,622"S 107°34'37,722"E
            r'(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:,\d+)?)\"\s*([NS])\s+(\d{1,3})°\s*(\d{1,2})\'\s*(\d{1,2}(?:,\d+)?)\"\s*([EW])',
            
            # Simplified: 6 52 35.622 S 107 34 37.722 E
            r'(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}(?:[.,]\d+)?)\s+([NS])\s+(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}(?:[.,]\d+)?)\s+([EW])',
            
            # Compact: 6°52'35.622"S107°34'37.722"E
            r'(\d{1,3})°(\d{1,2})\'(\d{1,2}(?:[.,]\d+)?)\"([NS])(\d{1,3})°(\d{1,2})\'(\d{1,2}(?:[.,]\d+)?)\"([EW])',
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
                    
                    # Normalize decimal separator
                    lat_sec = lat_sec.replace(',', '.')
                    lon_sec = lon_sec.replace(',', '.')
                    
                    # Format DMS strings
                    latitude = f"{lat_deg}° {lat_min}' {lat_sec}\" {lat_dir.upper()}"
                    longitude = f"{lon_deg}° {lon_min}' {lon_sec}\" {lon_dir.upper()}"
                    
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

# Utility functions untuk debugging
def test_ocr_configs(image_path: str) -> Dict[str, str]:
    """
    Test semua OCR configs pada gambar untuk debugging
    """
    if not Path(image_path).exists():
        return {}
    
    config = CoordinateOCRConfig()
    results = {}
    
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {}
        
        for config_info in config.ocr_configs:
            try:
                text = pytesseract.image_to_string(img, config=config_info['config'])
                results[config_info['name']] = text.strip() if text else ""
            except Exception as e:
                results[config_info['name']] = f"ERROR: {str(e)}"
        
        return results
        
    except Exception as e:
        logger.error(f"Error testing OCR configs: {e}")
        return {}

def debug_coordinate_extraction(image_path: str) -> Dict[str, Any]:
    """
    Debug function untuk testing koordinat extraction step by step
    """
    debug_info = {
        'image_path': image_path,
        'image_exists': Path(image_path).exists(),
        'enhanced_path': '',
        'segments': [],
        'ocr_results': {},
        'coordinates_found': None,
        'errors': []
    }
    
    try:
        if not debug_info['image_exists']:
            debug_info['errors'].append("Image file not found")
            return debug_info
        
        # Test image enhancement
        enhanced_path = enhance_image_for_coordinates(image_path)
        debug_info['enhanced_path'] = enhanced_path
        
        # Test segmentation
        segments = segment_coordinate_region(image_path)
        debug_info['segments'] = segments
        
        # Test OCR configs
        ocr_results = test_ocr_configs(enhanced_path)
        debug_info['ocr_results'] = ocr_results
        
        # Test coordinate extraction
        for config_name, text in ocr_results.items():
            if text and not text.startswith('ERROR'):
                coords = extract_coordinates_from_text(text)
                if coords:
                    debug_info['coordinates_found'] = {
                        'method': config_name,
                        'coordinates': coords,
                        'text': text
                    }
                    break
        
        return debug_info
        
    except Exception as e:
        debug_info['errors'].append(f"Debug error: {str(e)}")
        return debug_info