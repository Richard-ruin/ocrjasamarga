# ocr_service.py
import re
import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from typing import Tuple, Optional, Dict, List
import traceback

from app.ocr_config import (
    get_ocr_instance, 
    COORDINATE_PATTERNS, 
    INDONESIA_BOUNDS, 
    BANDUNG_BOUNDS,
    WEST_JAVA_BOUNDS,
    OCR_CONFIG,
    OCR_CORRECTIONS,
    VALID_COORDINATE_CHARS,
    validate_coordinate_bounds,
    RETRY_STRATEGIES
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoordinateExtractor:
    """
    Enhanced coordinate extraction class dengan multi-stage processing
    """
    
    def __init__(self):
        self.ocr = None
        self.debug_images = []
        self.processing_stats = {
            'total_attempts': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'preprocessing_errors': 0,
            'ocr_errors': 0,
            'parsing_errors': 0
        }
    
    def get_ocr_instance(self):
        """Get or initialize OCR instance"""
        if self.ocr is None:
            self.ocr = get_ocr_instance()
        return self.ocr
    
    def save_debug_image(self, image: np.ndarray, image_path: str, suffix: str = "debug") -> Optional[str]:
        """Save debug image untuk troubleshooting"""
        try:
            debug_path = str(Path(image_path).parent / f"{Path(image_path).stem}_{suffix}.jpg")
            cv2.imwrite(debug_path, image)
            self.debug_images.append(debug_path)
            logger.info(f"🔍 Debug image saved: {debug_path}")
            return debug_path
        except Exception as e:
            logger.error(f"❌ Failed to save debug image: {e}")
            return None

    def get_image_info(self, image_path: str) -> Dict:
        """Get comprehensive image information"""
        try:
            img = cv2.imread(image_path)
            if img is not None:
                height, width, channels = img.shape
                file_size = Path(image_path).stat().st_size
                return {
                    "width": width,
                    "height": height,
                    "channels": channels,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "aspect_ratio": round(width/height, 2),
                    "total_pixels": width * height,
                    "readable": True
                }
            return {"readable": False, "error": "Cannot read image with OpenCV"}
        except Exception as e:
            return {"readable": False, "error": str(e)}

    def smart_crop_coordinate_area(self, image: np.ndarray, crop_strategy: str = 'bottom_right') -> np.ndarray:
        """
        Smart cropping untuk area koordinat dengan berbagai strategi
        """
        try:
            height, width = image.shape[:2]
            crop_config = OCR_CONFIG['crop_areas'].get(crop_strategy, OCR_CONFIG['crop_areas']['bottom_right'])
            
            # Calculate crop coordinates
            x_start = int(width * crop_config['x_start'])
            y_start = int(height * crop_config['y_start'])
            crop_width = int(width * crop_config['width'])
            crop_height = int(height * crop_config['height'])
            
            x_end = min(x_start + crop_width, width)
            y_end = min(y_start + crop_height, height)
            
            # Ensure minimum size
            if (x_end - x_start) < 100 or (y_end - y_start) < 50:
                logger.warning(f"⚠️ Crop area too small, using larger area")
                x_start = max(0, int(width * 0.3))
                y_start = max(0, int(height * 0.6))
                x_end = width
                y_end = height
            
            cropped = image[y_start:y_end, x_start:x_end]
            
            logger.info(f"📐 Crop strategy '{crop_strategy}': {x_start},{y_start} to {x_end},{y_end}")
            logger.info(f"📏 Original: {width}x{height}, Cropped: {cropped.shape[1]}x{cropped.shape[0]}")
            
            return cropped
            
        except Exception as e:
            logger.error(f"❌ Error cropping image: {e}")
            return image

    def enhance_for_coordinate_text(self, image: np.ndarray, enhancement_level: str = 'advanced') -> np.ndarray:
        """
        Enhanced preprocessing khusus untuk watermark koordinat
        """
        try:
            original_image = image.copy()
            
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            if enhancement_level == 'basic':
                return self._basic_enhancement(gray)
            elif enhancement_level == 'advanced':
                return self._advanced_enhancement(gray)
            else:  # aggressive
                return self._aggressive_enhancement(gray)
                
        except Exception as e:
            logger.error(f"❌ Error in image enhancement: {e}")
            return image

    def _basic_enhancement(self, gray: np.ndarray) -> np.ndarray:
        """Basic enhancement untuk images berkualitas baik"""
        try:
            # Resize untuk OCR optimal
            height, width = gray.shape
            if width < 800:
                scale_factor = OCR_CONFIG['preprocessing']['resize_factor']
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # CLAHE untuk adaptive contrast
            clahe = cv2.createCLAHE(
                clipLimit=OCR_CONFIG['preprocessing']['clahe_clip_limit'],
                tileGridSize=(8,8)
            )
            enhanced = clahe.apply(gray)
            
            # Light noise reduction
            denoised = cv2.medianBlur(enhanced, 3)
            
            return denoised
            
        except Exception as e:
            logger.error(f"❌ Basic enhancement error: {e}")
            return gray

    def _advanced_enhancement(self, gray: np.ndarray) -> np.ndarray:
        """Advanced enhancement untuk most cases"""
        try:
            # Resize untuk OCR optimal
            height, width = gray.shape
            if width < 800:
                scale_factor = OCR_CONFIG['preprocessing']['resize_factor']
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Gamma correction untuk enhance light text
            gamma = OCR_CONFIG['preprocessing']['gamma_correction']
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            gamma_corrected = cv2.LUT(gray, table)
            
            # Bilateral filter untuk noise reduction with edge preservation
            bilateral = cv2.bilateralFilter(
                gamma_corrected, 
                OCR_CONFIG['preprocessing']['bilateral_d'],
                OCR_CONFIG['preprocessing']['bilateral_sigma_color'],
                OCR_CONFIG['preprocessing']['bilateral_sigma_space']
            )
            
            # CLAHE untuk adaptive histogram equalization
            clahe = cv2.createCLAHE(
                clipLimit=OCR_CONFIG['preprocessing']['clahe_clip_limit'],
                tileGridSize=(8,8)
            )
            enhanced = clahe.apply(bilateral)
            
            # Morphological operations untuk clean small noise
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
            
            # Sharpening untuk crisp text
            kernel_sharpen = np.array(OCR_CONFIG['preprocessing']['sharpen_kernel'])
            sharpened = cv2.filter2D(cleaned, -1, kernel_sharpen)
            
            return sharpened
            
        except Exception as e:
            logger.error(f"❌ Advanced enhancement error: {e}")
            return self._basic_enhancement(gray)

    def _aggressive_enhancement(self, gray: np.ndarray) -> np.ndarray:
        """Aggressive enhancement untuk images berkualitas rendah"""
        try:
            # Resize lebih besar untuk OCR
            height, width = gray.shape
            scale_factor = OCR_CONFIG['preprocessing']['resize_factor'] * 1.5
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Multiple gamma corrections
            gamma_light = 0.8  # Darken untuk highlight light text
            inv_gamma = 1.0 / gamma_light
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            gamma_corrected = cv2.LUT(gray, table)
            
            # Strong noise reduction
            denoised = cv2.bilateralFilter(gamma_corrected, 15, 100, 100)
            
            # Aggressive CLAHE
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4,4))
            enhanced = clahe.apply(denoised)
            
            # Edge enhancement
            edges = cv2.Canny(enhanced, 50, 150)
            edge_enhanced = cv2.addWeighted(enhanced, 0.8, edges, 0.2, 0)
            
            # Strong sharpening
            kernel_sharp = np.array([[-2,-2,-2], [-2,17,-2], [-2,-2,-2]])
            sharpened = cv2.filter2D(edge_enhanced, -1, kernel_sharp)
            
            # Final threshold untuk binary
            _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return thresh
            
        except Exception as e:
            logger.error(f"❌ Aggressive enhancement error: {e}")
            return self._advanced_enhancement(gray)

    def correct_ocr_text(self, text: str) -> str:
        """
        Enhanced OCR text correction dengan context awareness
        """
        try:
            corrected = text
            
            # Apply character corrections
            for wrong_char, correct_char in OCR_CORRECTIONS.items():
                corrected = corrected.replace(wrong_char, correct_char)
            
            # Context-aware corrections untuk koordinat
            # Fix degree symbol dalam konteks koordinat
            corrected = re.sub(r'(\d+)[o0O](\d+)', r'\1°\2', corrected)
            
            # Fix apostrophe dalam konteks koordinat  
            corrected = re.sub(r'(\d+)°(\d+)[`´]', r'\1°\2\'', corrected)
            
            # Clean extra spaces
            corrected = ' '.join(corrected.split())
            
            # Remove invalid characters but keep coordinate essentials
            valid_chars = ''.join(c for c in corrected if c in VALID_COORDINATE_CHARS)
            
            logger.debug(f"🔧 Text correction: '{text}' -> '{valid_chars}'")
            return valid_chars
            
        except Exception as e:
            logger.error(f"❌ Text correction error: {e}")
            return text

    def dms_to_decimal(self, degrees: int, minutes: int, seconds: float) -> float:
        """Convert DMS to decimal degrees dengan validation"""
        try:
            if not (0 <= degrees <= 180 and 0 <= minutes < 60 and 0 <= seconds < 60):
                raise ValueError(f"Invalid DMS values: {degrees}°{minutes}'{seconds}\"")
            
            decimal = degrees + (minutes / 60) + (seconds / 3600)
            return round(decimal, 6)
            
        except Exception as e:
            logger.error(f"❌ DMS conversion error: {e}")
            return 0.0

    def parse_coordinate_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Enhanced coordinate parsing dengan multiple pattern attempts
        """
        try:
            # Clean and correct text
            cleaned_text = self.correct_ocr_text(text.strip())
            logger.info(f"🔍 Parsing text: '{cleaned_text}'")
            
            latitude = None
            longitude = None
            
            # Try primary patterns first
            lat_match = re.search(COORDINATE_PATTERNS['latitude_primary'], cleaned_text, re.IGNORECASE)
            lon_match = re.search(COORDINATE_PATTERNS['longitude_primary'], cleaned_text, re.IGNORECASE)
            
            # If primary patterns fail, try alternatives
            if not lat_match:
                for i, pattern in enumerate(COORDINATE_PATTERNS['latitude_alternatives']):
                    lat_match = re.search(pattern, cleaned_text, re.IGNORECASE)
                    if lat_match:
                        logger.info(f"✅ Latitude found with alternative pattern #{i+1}")
                        break
            
            if not lon_match:
                for i, pattern in enumerate(COORDINATE_PATTERNS['longitude_alternatives']):
                    lon_match = re.search(pattern, cleaned_text, re.IGNORECASE)
                    if lon_match:
                        logger.info(f"✅ Longitude found with alternative pattern #{i+1}")
                        break
            
            # Parse latitude
            if lat_match:
                try:
                    deg = int(lat_match.group(1))
                    min_val = int(lat_match.group(2))
                    sec_str = lat_match.group(3).replace(',', '.')
                    sec = float(sec_str)
                    
                    # Convert to decimal and make negative for South
                    lat_decimal = -self.dms_to_decimal(deg, min_val, sec)
                    latitude = str(lat_decimal)
                    logger.info(f"✅ Latitude parsed: {lat_match.group(0)} -> {latitude}")
                    
                except (ValueError, IndexError) as e:
                    logger.error(f"❌ Latitude parsing error: {e}")
            
            # Parse longitude  
            if lon_match:
                try:
                    deg = int(lon_match.group(1))
                    min_val = int(lon_match.group(2))
                    sec_str = lon_match.group(3).replace(',', '.')
                    sec = float(sec_str)
                    
                    # Convert to decimal (positive for East)
                    lon_decimal = self.dms_to_decimal(deg, min_val, sec)
                    longitude = str(lon_decimal)
                    logger.info(f"✅ Longitude parsed: {lon_match.group(0)} -> {longitude}")
                    
                except (ValueError, IndexError) as e:
                    logger.error(f"❌ Longitude parsing error: {e}")
            
            return latitude, longitude
            
        except Exception as e:
            logger.error(f"❌ Coordinate parsing error: {e}")
            return None, None

    def perform_ocr_with_confidence(self, image: np.ndarray, min_confidence: float = 0.3) -> List[Dict]:
        """
        Perform OCR dengan confidence filtering dan comprehensive results
        """
        try:
            ocr = self.get_ocr_instance()
            results = ocr.ocr(image, cls=True)
            
            if not results or not results[0]:
                return []
            
            extracted_data = []
            for line in results[0]:
                if len(line) >= 2:
                    bbox = line[0]  # Bounding box coordinates
                    text_info = line[1]  # (text, confidence)
                    
                    if len(text_info) >= 2:
                        text = text_info[0]
                        confidence = text_info[1]
                        
                        extracted_data.append({
                            'text': text,
                            'confidence': confidence,
                            'bbox': bbox,
                            'meets_threshold': confidence >= min_confidence
                        })
            
            # Sort by confidence descending
            extracted_data.sort(key=lambda x: x['confidence'], reverse=True)
            
            logger.info(f"  📄 Text: '{data['text']}' (conf: {data['confidence']:.2f})")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"❌ OCR processing error: {e}")
            return []

    def multi_strategy_extraction(self, image_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Multi-strategy coordinate extraction dengan berbagai pendekatan
        """
        try:
            self.processing_stats['total_attempts'] += 1
            
            # Load original image
            original_image = cv2.imread(image_path)
            if original_image is None:
                raise ValueError(f"Cannot read image: {image_path}")
            
            image_info = self.get_image_info(image_path)
            logger.info(f"🔍 Processing image: {Path(image_path).name}")
            logger.info(f"📊 Image specs: {image_info}")
            
            # Strategy 1: Full image dengan basic enhancement
            logger.info("🎯 Strategy 1: Full image basic enhancement")
            result = self._try_extraction_strategy(
                original_image, image_path, 
                crop_strategy=None, 
                enhancement_level='basic'
            )
            if result[0] and result[1]:
                logger.info("✅ Strategy 1 successful!")
                self.processing_stats['successful_extractions'] += 1
                return result
            
            # Strategy 2: Cropped area dengan advanced enhancement
            logger.info("🎯 Strategy 2: Cropped area advanced enhancement")
            result = self._try_extraction_strategy(
                original_image, image_path,
                crop_strategy='bottom_right',
                enhancement_level='advanced'
            )
            if result[0] and result[1]:
                logger.info("✅ Strategy 2 successful!")
                self.processing_stats['successful_extractions'] += 1
                return result
            
            # Strategy 3: Multiple crop areas
            for crop_strategy in ['bottom_center', 'full_bottom']:
                logger.info(f"🎯 Strategy 3.{crop_strategy}: Different crop area")
                result = self._try_extraction_strategy(
                    original_image, image_path,
                    crop_strategy=crop_strategy,
                    enhancement_level='advanced'
                )
                if result[0] and result[1]:
                    logger.info(f"✅ Strategy 3.{crop_strategy} successful!")
                    self.processing_stats['successful_extractions'] += 1
                    return result
            
            # Strategy 4: Aggressive enhancement pada cropped area
            logger.info("🎯 Strategy 4: Aggressive enhancement")
            result = self._try_extraction_strategy(
                original_image, image_path,
                crop_strategy='bottom_right',
                enhancement_level='aggressive'
            )
            if result[0] and result[1]:
                logger.info("✅ Strategy 4 successful!")
                self.processing_stats['successful_extractions'] += 1
                return result
            
            # All strategies failed
            logger.warning("❌ All extraction strategies failed")
            self.processing_stats['failed_extractions'] += 1
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Multi-strategy extraction error: {e}")
            self.processing_stats['failed_extractions'] += 1
            return None, None

    def _try_extraction_strategy(self, original_image: np.ndarray, image_path: str, 
                               crop_strategy: Optional[str], enhancement_level: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Try specific extraction strategy
        """
        try:
            # Prepare image
            working_image = original_image.copy()
            
            # Apply cropping if specified
            if crop_strategy:
                working_image = self.smart_crop_coordinate_area(working_image, crop_strategy)
                debug_suffix = f"crop_{crop_strategy}_{enhancement_level}"
            else:
                debug_suffix = f"full_{enhancement_level}"
            
            # Apply enhancement
            enhanced_image = self.enhance_for_coordinate_text(working_image, enhancement_level)
            
            # Save debug image
            self.save_debug_image(enhanced_image, image_path, debug_suffix)
            
            # Perform OCR
            ocr_results = self.perform_ocr_with_confidence(enhanced_image, min_confidence=0.25)
            
            if not ocr_results:
                logger.debug(f"No OCR results for strategy {crop_strategy}/{enhancement_level}")
                return None, None
            
            # Process OCR results
            all_text = ' '.join([result['text'] for result in ocr_results 
                               if result['meets_threshold']])
            
            logger.debug(f"📝 Combined OCR text: '{all_text}'")
            
            # Parse coordinates
            latitude, longitude = self.parse_coordinate_text(all_text)
            
            # Validate coordinates if found
            if latitude and longitude:
                try:
                    lat_val = float(latitude)
                    lon_val = float(longitude)
                    
                    validation = validate_coordinate_bounds(lat_val, lon_val)
                    if validation['valid']:
                        logger.info(f"✅ Valid coordinates found: {latitude}, {longitude} ({validation['region']})")
                        return latitude, longitude
                    else:
                        logger.warning(f"⚠️ Invalid coordinate bounds: {latitude}, {longitude}")
                        logger.warning(f"⚠️ Warnings: {validation['warnings']}")
                        
                except ValueError as e:
                    logger.error(f"❌ Invalid coordinate format: {e}")
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Strategy execution error: {e}")
            return None, None

    def extract_with_fallback_ocr(self, image_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract coordinates dengan fallback OCR configurations
        """
        try:
            # Try primary OCR configuration
            result = self.multi_strategy_extraction(image_path)
            if result[0] and result[1]:
                return result
            
            # Try with fallback OCR configurations
            logger.info("🔄 Trying fallback OCR configurations...")
            
            for strategy in RETRY_STRATEGIES:
                try:
                    logger.info(f"🎯 Trying {strategy['name']} strategy")
                    
                    # Reinitialize OCR with different parameters
                    # Note: PaddleOCR doesn't support runtime parameter changes
                    # This is a placeholder for future implementation
                    
                    result = self.multi_strategy_extraction(image_path)
                    if result[0] and result[1]:
                        logger.info(f"✅ Success with {strategy['name']} strategy")
                        return result
                        
                except Exception as e:
                    logger.error(f"❌ Fallback strategy {strategy['name']} failed: {e}")
                    continue
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Fallback OCR extraction error: {e}")
            return None, None

    def get_processing_stats(self) -> Dict:
        """Get comprehensive processing statistics"""
        stats = self.processing_stats.copy()
        if stats['total_attempts'] > 0:
            stats['success_rate'] = round(
                (stats['successful_extractions'] / stats['total_attempts']) * 100, 2
            )
        else:
            stats['success_rate'] = 0.0
        
        stats['debug_images'] = len(self.debug_images)
        return stats

    def cleanup_debug_images(self):
        """Clean up debug images"""
        for debug_path in self.debug_images:
            try:
                if Path(debug_path).exists():
                    Path(debug_path).unlink()
                    logger.debug(f"🧹 Cleaned debug image: {debug_path}")
            except Exception as e:
                logger.error(f"❌ Failed to clean debug image {debug_path}: {e}")
        
        self.debug_images.clear()

# Main function untuk coordinate extraction
def extract_coordinates_with_validation(image_path: str, 
                                      cleanup_debug: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Main function untuk ekstraksi koordinat dengan validasi komprehensif
    
    Args:
        image_path: Path ke image file
        cleanup_debug: Whether to cleanup debug images after processing
    
    Returns:
        Tuple of (latitude, longitude) sebagai string, atau (None, None) jika gagal
    """
    extractor = None
    try:
        logger.info(f"🚀 Starting coordinate extraction from: {Path(image_path).name}")
        
        # Validate file exists
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Initialize extractor
        extractor = CoordinateExtractor()
        
        # Perform extraction dengan multiple strategies
        latitude, longitude = extractor.extract_with_fallback_ocr(image_path)
        
        # Log results
        stats = extractor.get_processing_stats()
        logger.info(f"📊 Processing completed. Stats: {stats}")
        
        if latitude and longitude:
            logger.info(f"✅ Final result: Latitude={latitude}, Longitude={longitude}")
            return latitude, longitude
        else:
            logger.warning("❌ No valid coordinates extracted")
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Coordinate extraction failed: {e}")
        logger.error(f"📋 Full traceback: {traceback.format_exc()}")
        return None, None
        
    finally:
        # Cleanup debug images if requested
        if extractor and cleanup_debug:
            extractor.cleanup_debug_images()

# Additional utility functions
def batch_extract_coordinates(image_paths: List[str], 
                            max_workers: int = 4) -> List[Dict]:
    """
    Batch extraction untuk multiple images dengan parallel processing
    """
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(extract_coordinates_with_validation, path): path 
                for path in image_paths
            }
            
            # Collect results
            for future in as_completed(future_to_path):
                image_path = future_to_path[future]
                try:
                    latitude, longitude = future.result()
                    results.append({
                        'image_path': image_path,
                        'latitude': latitude,
                        'longitude': longitude,
                        'success': bool(latitude and longitude)
                    })
                except Exception as e:
                    logger.error(f"❌ Batch processing error for {image_path}: {e}")
                    results.append({
                        'image_path': image_path,
                        'latitude': None,
                        'longitude': None,
                        'success': False,
                        'error': str(e)
                    })
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Batch extraction error: {e}")
        return []

def test_coordinate_extraction(image_path: str, save_debug: bool = True) -> Dict:
    """
    Test function untuk debugging coordinate extraction
    """
    try:
        extractor = CoordinateExtractor()
        
        # Get image info
        image_info = extractor.get_image_info(image_path)
        
        # Perform extraction
        latitude, longitude = extractor.extract_with_fallback_ocr(image_path)
        
        # Get processing stats
        stats = extractor.get_processing_stats()
        
        # Prepare test results
        result = {
            'image_path': image_path,
            'image_info': image_info,
            'extracted_coordinates': {
                'latitude': latitude,
                'longitude': longitude,
                'success': bool(latitude and longitude)
            },
            'processing_stats': stats,
            'debug_images': extractor.debug_images.copy() if save_debug else []
        }
        
        # Cleanup if not saving debug
        if not save_debug:
            extractor.cleanup_debug_images()
            
        return result
        
    except Exception as e:
        return {
            'image_path': image_path,
            'error': str(e),
            'success': False
        }

# Performance monitoring
class OCRPerformanceMonitor:
    """Monitor OCR performance untuk optimization"""
    
    def __init__(self):
        self.metrics = {
            'total_processed': 0,
            'successful_extractions': 0,
            'average_processing_time': 0.0,
            'strategy_success_rates': {}
        }
    
    def record_extraction(self, success: bool, processing_time: float, strategy: str):
        """Record extraction result"""
        self.metrics['total_processed'] += 1
        
        if success:
            self.metrics['successful_extractions'] += 1
        
        # Update average processing time
        current_avg = self.metrics['average_processing_time']
        total = self.metrics['total_processed']
        self.metrics['average_processing_time'] = (
            (current_avg * (total - 1) + processing_time) / total
        )
        
        # Update strategy success rates
        if strategy not in self.metrics['strategy_success_rates']:
            self.metrics['strategy_success_rates'][strategy] = {'attempts': 0, 'successes': 0}
        
        self.metrics['strategy_success_rates'][strategy]['attempts'] += 1
        if success:
            self.metrics['strategy_success_rates'][strategy]['successes'] += 1
    
    def get_success_rate(self) -> float:
        """Get overall success rate"""
        if self.metrics['total_processed'] == 0:
            return 0.0
        return (self.metrics['successful_extractions'] / self.metrics['total_processed']) * 100
    
    def get_metrics(self) -> Dict:
        """Get comprehensive metrics"""
        metrics = self.metrics.copy()
        metrics['overall_success_rate'] = self.get_success_rate()
        
        # Calculate strategy success rates
        for strategy, data in metrics['strategy_success_rates'].items():
            if data['attempts'] > 0:
                data['success_rate'] = (data['successes'] / data['attempts']) * 100
            else:
                data['success_rate'] = 0.0
        
        return metrics

# Global performance monitor instance
performance_monitor = OCRPerformanceMonitor()

if __name__ == "__main__":
    # Test extraction
    import sys
    
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
        print(f"Testing coordinate extraction on: {test_image}")
        
        result = test_coordinate_extraction(test_image)
        print(f"Result: {result}")
    else:
        print("Usage: python ocr_service.py <image_path>")