# app/services/ocr_service.py
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re
import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set tesseract path untuk Windows (uncomment jika perlu)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class EnhancedTesseractExtractor:
    """
    Enhanced GPS coordinate extractor menggunakan Tesseract OCR
    Migrasi dari EasyOCR untuk performa yang lebih baik
    """
    
    def __init__(self):
        """Initialize extractor dengan konfigurasi optimal"""
        self.debug_mode = True  # Enable untuk development
        
        # Multiple tesseract configurations untuk koordinat GPS
        self.ocr_configs = [
            # Whitelist karakter untuk koordinat GPS
            r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789°\'".,NSEW ',
            # Fallback tanpa whitelist
            r'--oem 3 --psm 6',
            r'--oem 3 --psm 7',
            r'--oem 3 --psm 8',
        ]
        
        logger.info("EnhancedTesseractExtractor initialized")

    def preprocess_image_for_coordinates(self, image_path: str) -> List[Tuple[str, np.ndarray]]:
        """
        Advanced preprocessing untuk meningkatkan akurasi OCR pada koordinat GPS
        Returns: List of (method_name, processed_image) tuples
        """
        try:
            logger.debug(f"Preprocessing image: {image_path}")
            
            # Baca gambar
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Cannot read image: {image_path}")
                return []
            
            height, width = img.shape[:2]
            logger.debug(f"Image dimensions: {width}x{height}")
            
            # Crop area koordinat GPS (fokus pada overlay teks)
            # Berdasarkan analisis: koordinat biasanya di bagian tengah-bawah overlay
            y_start = int(height * 0.70)  # 70% dari atas
            y_end = int(height * 0.78)    # 78% dari atas  
            x_start = int(width * 0.05)   # 5% dari kiri
            x_end = int(width * 0.95)     # 95% dari kiri
            
            cropped_img = img[y_start:y_end, x_start:x_end]
            logger.debug(f"Cropped to: {x_end-x_start}x{y_end-y_start}")
            
            # Save cropped image untuk debug
            if self.debug_mode:
                cv2.imwrite("debug_cropped.jpg", cropped_img)
            
            # Generate multiple enhanced versions
            enhanced_images = self._enhance_image_multiple_methods(cropped_img)
            
            return enhanced_images
            
        except Exception as e:
            logger.error(f"Error in preprocessing: {e}")
            return []

    def _enhance_image_multiple_methods(self, img: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """
        Generate multiple enhanced versions untuk OCR
        """
        enhanced_images = []
        
        try:
            # Convert ke grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Invert image (teks putih jadi hitam untuk OCR)
            inverted = cv2.bitwise_not(gray)
            
            # Apply Gaussian blur untuk mengurangi noise
            blurred = cv2.GaussianBlur(inverted, (3, 3), 0)
            
            # Method 1: Adaptive Mean Threshold
            adaptive_mean = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 10
            )
            enhanced_images.append(("adaptive_mean", self._post_process(adaptive_mean)))
            
            # Method 2: Adaptive Gaussian Threshold
            adaptive_gaussian = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
            )
            enhanced_images.append(("adaptive_gaussian", self._post_process(adaptive_gaussian)))
            
            # Method 3: OTSU Threshold
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            enhanced_images.append(("otsu", self._post_process(otsu)))
            
            # Method 4: Manual Threshold
            _, manual = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY)
            enhanced_images.append(("manual", self._post_process(manual)))
            
            # Save debug images
            if self.debug_mode:
                for name, processed_img in enhanced_images:
                    cv2.imwrite(f"debug_{name}.jpg", processed_img)
            
            logger.debug(f"Generated {len(enhanced_images)} enhanced images")
            return enhanced_images
            
        except Exception as e:
            logger.error(f"Error in image enhancement: {e}")
            return []

    def _post_process(self, img: np.ndarray) -> np.ndarray:
        """
        Post-processing untuk cleanup dan scale up
        """
        try:
            # Morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            
            # Closing untuk menghubungkan karakter terputus
            closed = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
            
            # Opening untuk menghilangkan noise
            opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
            
            # Scale up untuk OCR yang lebih baik
            scale_factor = 3
            scaled = cv2.resize(opened, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            
            return scaled
            
        except Exception as e:
            logger.error(f"Error in post-processing: {e}")
            return img

    def extract_text_with_multiple_methods(self, enhanced_images: List[Tuple[str, np.ndarray]]) -> List[Tuple[str, str, str]]:
        """
        Extract text menggunakan multiple preprocessing methods dan OCR configs
        Returns: List of (method_name, config, extracted_text) tuples
        """
        all_texts = []
        
        for method_name, img_array in enhanced_images:
            logger.debug(f"OCR processing method: {method_name}")
            
            # Convert ke PIL Image untuk additional enhancements
            pil_img = Image.fromarray(img_array)
            enhanced_pil = self._enhance_pil_image(pil_img)
            
            # Try multiple OCR configurations
            for config in self.ocr_configs:
                try:
                    text = pytesseract.image_to_string(enhanced_pil, config=config)
                    if text and text.strip():
                        clean_text = text.strip()
                        logger.debug(f"OCR result from {method_name}: {clean_text[:50]}...")
                        all_texts.append((method_name, config, clean_text))
                        
                except Exception as e:
                    logger.debug(f"OCR config failed for {method_name}: {e}")
                    continue
        
        logger.debug(f"Total OCR results: {len(all_texts)}")
        return all_texts

    def _enhance_pil_image(self, pil_img: Image.Image) -> Image.Image:
        """
        Additional PIL enhancements untuk OCR yang lebih baik
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
        Flexible coordinate extraction dengan multiple patterns
        """
        if not text:
            return None
        
        # Clean text
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        
        logger.debug(f"Analyzing text: {text}")
        
        # Multiple coordinate patterns
        patterns = [
            # Standard: 6°52'35,574"S 107°34'37,716"E
            r"(\d+)°\s*(\d+)'?\s*(\d+)[,.](\d+)\"?\s*([NSEW])\s*[,\s]*(\d+)°\s*(\d+)'?\s*(\d+)[,.](\d+)\"?\s*([NSEW])",
            
            # With spaces: 6° 52' 35.574" S 107° 34' 37.716" E
            r"(\d+)°\s+(\d+)'\s+(\d+)[,.](\d+)\"\s+([NSEW])\s*[,\s]*(\d+)°\s+(\d+)'\s+(\d+)[,.](\d+)\"\s+([NSEW])",
            
            # Simplified: 6 52 35.574 S 107 34 37.716 E
            r"(\d+)\s+(\d+)\s+(\d+)[,.](\d+)\s+([NSEW])\s*[,\s]*(\d+)\s+(\d+)\s+(\d+)[,.](\d+)\s+([NSEW])",
            
            # Without quotes: 6°52'35,574S 107°34'37,716E
            r"(\d+)°(\d+)'(\d+)[,.](\d+)([NSEW])\s*(\d+)°(\d+)'(\d+)[,.](\d+)([NSEW])",
            
            # OCR common errors (Z->S, missing characters)
            r"(\d+)°?\s*(\d+)['\s]*(\d+)[,.](\d+)[\"'\s]*([NSEWZ])\s*[,\s]*(\d+)°?\s*(\d+)['\s]*(\d+)[,.](\d+)[\"'\s]*([NSEWZ])",
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                logger.debug(f"Pattern {i+1} matched!")
                return self._parse_coordinate_match(match)
        
        # Fallback: try partial coordinates
        return self._extract_partial_coordinates(text)

    def _extract_partial_coordinates(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract koordinat parsial jika pattern lengkap tidak ditemukan
        """
        try:
            # Cari latitude dan longitude secara terpisah
            lat_pattern = r"(\d+)°?\s*(\d+)'?\s*(\d+)[,.](\d+)[\"']?\s*[SN]"
            lng_pattern = r"(\d+)°?\s*(\d+)'?\s*(\d+)[,.](\d+)[\"']?\s*[EW]"
            
            lat_match = re.search(lat_pattern, text, re.IGNORECASE)
            lng_match = re.search(lng_pattern, text, re.IGNORECASE)
            
            if lat_match and lng_match:
                logger.debug("Partial coordinates found!")
                
                # Reconstruct full match
                full_groups = list(lat_match.groups()) + ['S'] + list(lng_match.groups()) + ['E']
                
                class MockMatch:
                    def __init__(self, groups):
                        self._groups = groups
                    def groups(self):
                        return self._groups
                
                return self._parse_coordinate_match(MockMatch(full_groups))
            
            return None
            
        except Exception as e:
            logger.debug(f"Error in partial extraction: {e}")
            return None

    def _parse_coordinate_match(self, match) -> Optional[Dict[str, Any]]:
        """
        Parse coordinate match groups menjadi format yang diinginkan
        """
        try:
            groups = match.groups()
            
            if len(groups) < 10:
                logger.debug(f"Insufficient groups: {len(groups)}")
                return None
            
            # Parse latitude
            lat_deg = int(groups[0])
            lat_min = int(groups[1])
            lat_sec = int(groups[2])
            lat_decimal = int(groups[3])
            lat_dir = groups[4].upper()
            
            # Parse longitude
            lng_deg = int(groups[5])
            lng_min = int(groups[6])
            lng_sec = int(groups[7])
            lng_decimal = int(groups[8])
            lng_dir = groups[9].upper()
            
            # Fix common OCR errors
            if lat_dir == 'Z': lat_dir = 'S'
            if lng_dir == 'Z': lng_dir = 'E'
            
            # Format DMS strings
            lat_dms = f"{lat_deg}° {lat_min}' {lat_sec}.{lat_decimal:03d}\" {lat_dir}"
            lng_dms = f"{lng_deg}° {lng_min}' {lng_sec}.{lng_decimal:03d}\" {lng_dir}"
            
            # Convert ke decimal degrees untuk validasi
            lat_decimal_deg = self._dms_to_decimal(lat_deg, lat_min, lat_sec, lat_decimal, lat_dir)
            lng_decimal_deg = self._dms_to_decimal(lng_deg, lng_min, lng_sec, lng_decimal, lng_dir)
            
            logger.debug(f"Parsed coordinates: {lat_dms}, {lng_dms}")
            
            return {
                'latitude': lat_dms,
                'longitude': lng_dms,
                'latitude_decimal': lat_decimal_deg,
                'longitude_decimal': lng_decimal_deg,
                'coordinate_string': f"{lat_decimal_deg}, {lng_decimal_deg}",
                'google_maps_url': f"https://maps.google.com/maps?q={lat_decimal_deg},{lng_decimal_deg}"
            }
            
        except Exception as e:
            logger.error(f"Error parsing coordinates: {e}")
            return None

    def _dms_to_decimal(self, degrees: int, minutes: int, seconds: int, decimal_seconds: int, direction: str) -> float:
        """
        Convert DMS ke Decimal Degrees
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
        Returns: (latitude_dms, longitude_dms) tuple
        """
        try:
            logger.info(f"Extracting coordinates from: {image_path}")
            
            # Preprocess image
            enhanced_images = self.preprocess_image_for_coordinates(image_path)
            if not enhanced_images:
                logger.warning("No enhanced images generated")
                return "", ""
            
            # Extract text dengan multiple methods
            all_texts = self.extract_text_with_multiple_methods(enhanced_images)
            if not all_texts:
                logger.warning("No text extracted from image")
                return "", ""
            
            # Try to extract coordinates from each OCR result
            for method, config, text in all_texts:
                coordinates = self.extract_coordinates_flexible(text)
                if coordinates:
                    logger.info(f"Coordinates found using {method}: {coordinates['latitude']}, {coordinates['longitude']}")
                    return coordinates['latitude'], coordinates['longitude']
            
            logger.warning("No coordinates found in any OCR result")
            return "", ""
            
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
    Main function untuk ekstrak koordinat dari gambar (compatible dengan kode existing)
    """
    extractor = get_extractor()
    return extractor.extract_coordinates_from_image(image_path)

# Legacy functions untuk backward compatibility
def preprocess_image_for_coordinates(image_path: str) -> str:
    """Legacy function untuk backward compatibility"""
    logger.warning("Using legacy preprocess function - consider using new extractor directly")
    return image_path

def clean_ocr_text(text: str) -> str:
    """Legacy function untuk backward compatibility"""
    char_mapping = {
        'o': '°', 'O': '°', '*': '°', '0': '°',
        '/': "'", '\\': "'", '|': "'", 'I': "'",
        ',': '.',
        '"': '"', '"': '"', "'": "'", "'": "'",
    }
    
    cleaned = text
    for old_char, new_char in char_mapping.items():
        cleaned = cleaned.replace(old_char, new_char)
    
    cleaned = re.sub(r'[^\d°\'\"NSEW\s\.]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def is_valid_coordinate(latitude: str, longitude: str) -> bool:
    """Validasi koordinat"""
    try:
        lat_deg = re.search(r'(\d+)°', latitude)
        lon_deg = re.search(r'(\d+)°', longitude)
        
        if lat_deg and lon_deg:
            lat_val = int(lat_deg.group(1))
            lon_val = int(lon_deg.group(1))
            
            if 0 <= lat_val <= 90 and 0 <= lon_val <= 180:
                return True
        
        return False
    except:
        return False