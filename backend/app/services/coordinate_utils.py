"""
Coordinate Utils - Utility functions untuk OCR koordinat GPS
Disesuaikan dengan routes FastAPI
"""

import re
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
import shutil
import uuid
from fastapi import UploadFile

# Import services
from app.services.ocr_service import extract_coordinates_from_image
from app.ocr_config import CoordinateOCRConfig, enhance_image_for_coordinates, is_coordinate_in_indonesia

# Setup logging
logger = logging.getLogger(__name__)

# Inisialisasi OCR config
ocr_config = CoordinateOCRConfig()

@dataclass
class GPSExtractionResult:
    """
    Dataclass untuk menyimpan hasil ekstraksi GPS
    """
    latitude: str = ""
    longitude: str = ""
    confidence: float = 0.0
    method: str = ""
    processing_time: float = 0.0
    is_valid: bool = False
    context: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

def validate_image_file(filename: str) -> bool:
    """
    Validasi apakah file adalah gambar yang didukung
    """
    if not filename:
        return False
    
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    ext = Path(filename).suffix.lower()
    return ext in supported_extensions

def save_uploaded_image(upload_file: UploadFile, temp_dir: Path) -> str:
    """
    Simpan uploaded file ke direktori sementara
    """
    try:
        # Pastikan direktori exists
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate nama file unik
        ext = Path(upload_file.filename).suffix.lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        save_path = temp_dir / filename
        
        # Simpan file
        with save_path.open("wb") as f:
            shutil.copyfileobj(upload_file.file, f)
        
        logger.debug(f"Image saved to: {save_path}")
        return str(save_path)
        
    except Exception as e:
        logger.error(f"Error saving uploaded image: {e}")
        raise

def extract_coordinates_with_validation(image_path: str) -> Tuple[str, str]:
    """
    Ekstrak koordinat dengan multiple validation dan enhancement
    """
    try:
        logger.info(f"Extracting coordinates from: {image_path}")
        
        # Step 1: Enhance gambar untuk OCR yang lebih baik
        enhanced_path = enhance_image_for_coordinates(image_path)
        
        # Step 2: Multiple OCR attempts dengan berbagai metode
        coordinates_attempts = []
        
        # Attempt 1: OCR dengan image asli
        try:
            lat1, lon1 = extract_coordinates_from_image(image_path)
            if lat1 and lon1:
                coordinates_attempts.append((lat1, lon1, "original"))
                logger.debug(f"Original OCR result: {lat1}, {lon1}")
        except Exception as e:
            logger.debug(f"Original OCR failed: {e}")
        
        # Attempt 2: OCR dengan enhanced image
        if enhanced_path != image_path:
            try:
                lat2, lon2 = extract_coordinates_from_image(enhanced_path)
                if lat2 and lon2:
                    coordinates_attempts.append((lat2, lon2, "enhanced"))
                    logger.debug(f"Enhanced OCR result: {lat2}, {lon2}")
            except Exception as e:
                logger.debug(f"Enhanced OCR failed: {e}")
        
        # Attempt 3: OCR dengan konfigurasi yang dioptimalkan
        try:
            optimized_result = ocr_config.read_coordinates_optimized(image_path)
            if optimized_result:
                text_optimized = " ".join(optimized_result)
                lat3, lon3 = parse_coordinates_from_text(text_optimized)
                if lat3 and lon3:
                    coordinates_attempts.append((lat3, lon3, "optimized"))
                    logger.debug(f"Optimized OCR result: {lat3}, {lon3}")
        except Exception as e:
            logger.debug(f"Optimized OCR failed: {e}")
        
        # Step 3: Pilih hasil terbaik berdasarkan prioritas dan validasi
        if coordinates_attempts:
            # Prioritas: enhanced > optimized > original
            priority_order = ["enhanced", "optimized", "original"]
            
            # Cari koordinat yang valid untuk wilayah Indonesia
            for method in priority_order:
                for lat, lon, source in coordinates_attempts:
                    if source == method:
                        if is_coordinate_in_indonesia(lat, lon):
                            logger.info(f"Selected valid coordinates from {source}: {lat}, {lon}")
                            return lat, lon
                        else:
                            logger.warning(f"Coordinates from {source} outside Indonesia: {lat}, {lon}")
            
            # Jika tidak ada yang valid untuk Indonesia, ambil yang pertama
            lat, lon, source = coordinates_attempts[0]
            logger.info(f"Selected coordinates (fallback) from {source}: {lat}, {lon}")
            return lat, lon
        
        logger.warning(f"No coordinates found in image: {image_path}")
        return "", ""
        
    except Exception as e:
        logger.error(f"Error in extract_coordinates_with_validation: {e}")
        return "", ""
    
    finally:
        # Cleanup enhanced image jika berbeda dari original
        try:
            if 'enhanced_path' in locals() and enhanced_path != image_path:
                if Path(enhanced_path).exists():
                    Path(enhanced_path).unlink()
                    logger.debug(f"Cleaned up enhanced image: {enhanced_path}")
        except Exception as cleanup_error:
            logger.debug(f"Failed to cleanup enhanced image: {cleanup_error}")

def extract_gps_coordinates_advanced(image_path: str) -> GPSExtractionResult:
    """
    Ekstrak koordinat GPS dengan hasil yang lebih detail
    """
    start_time = time.time()
    result = GPSExtractionResult()
    
    try:
        logger.info(f"Advanced GPS extraction from: {image_path}")
        
        # Multiple extraction attempts
        extraction_methods = []
        
        # Method 1: Standard OCR
        try:
            lat1, lon1 = extract_coordinates_from_image(image_path)
            if lat1 and lon1:
                extraction_methods.append({
                    'latitude': lat1,
                    'longitude': lon1,
                    'method': 'standard_ocr',
                    'confidence': 0.7
                })
        except Exception as e:
            logger.debug(f"Standard OCR failed: {e}")
        
        # Method 2: Enhanced OCR
        try:
            enhanced_path = enhance_image_for_coordinates(image_path)
            if enhanced_path != image_path:
                lat2, lon2 = extract_coordinates_from_image(enhanced_path)
                if lat2 and lon2:
                    extraction_methods.append({
                        'latitude': lat2,
                        'longitude': lon2,
                        'method': 'enhanced_ocr',
                        'confidence': 0.8
                    })
        except Exception as e:
            logger.debug(f"Enhanced OCR failed: {e}")
        
        # Method 3: Optimized OCR
        try:
            optimized_result = ocr_config.read_coordinates_optimized(image_path)
            if optimized_result:
                text_optimized = " ".join(optimized_result)
                lat3, lon3 = parse_coordinates_from_text(text_optimized)
                if lat3 and lon3:
                    extraction_methods.append({
                        'latitude': lat3,
                        'longitude': lon3,
                        'method': 'optimized_ocr',
                        'confidence': 0.9
                    })
        except Exception as e:
            logger.debug(f"Optimized OCR failed: {e}")
        
        # Select best result
        if extraction_methods:
            # Sort by confidence (highest first)
            extraction_methods.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Find best valid coordinate for Indonesia
            best_method = None
            for method in extraction_methods:
                if is_coordinate_in_indonesia(method['latitude'], method['longitude']):
                    best_method = method
                    break
            
            # If no valid Indonesia coordinate, take highest confidence
            if not best_method:
                best_method = extraction_methods[0]
            
            # Fill result
            result.latitude = best_method['latitude']
            result.longitude = best_method['longitude']
            result.confidence = best_method['confidence']
            result.method = best_method['method']
            result.is_valid = bool(result.latitude and result.longitude)
            result.context = {
                'attempts': len(extraction_methods),
                'indonesia_valid': is_coordinate_in_indonesia(result.latitude, result.longitude),
                'image_path': image_path
            }
            
            logger.info(f"GPS extraction successful: {result.latitude}, {result.longitude} "
                       f"(method: {result.method}, confidence: {result.confidence})")
        else:
            result.error = "No coordinates found with any method"
            logger.warning(f"No coordinates found in image: {image_path}")
        
    except Exception as e:
        result.error = str(e)
        logger.error(f"Error in advanced GPS extraction: {e}")
    
    finally:
        result.processing_time = time.time() - start_time
    
    return result

def parse_coordinates_from_text(text: str) -> Tuple[str, str]:
    """
    Parse koordinat dari teks dengan regex yang lebih robust
    """
    # Pattern untuk berbagai format koordinat
    patterns = [
        # Format standar: 6°52'35.622"S 107°34'37.722"E
        r'(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:\.\d+)?)[\"″]\s*([NS])\s+(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:\.\d+)?)[\"″]\s*([EW])',
        
        # Format dengan koma: 6°52'35,622"S 107°34'37,722"E
        r'(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:,\d+)?)[\"″]\s*([NS])\s+(\d{1,3})[°*]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:,\d+)?)[\"″]\s*([EW])',
        
        # Format tanpa spasi: 6°52'35.622"S107°34'37.722"E
        r'(\d{1,3})[°*](\d{1,2})[\'′](\d{1,2}(?:\.\d+)?)[\"″]([NS])(\d{1,3})[°*](\d{1,2})[\'′](\d{1,2}(?:\.\d+)?)[\"″]([EW])',
        
        # Format dengan karakter berbeda: 6*52'35.622"S 107*34'37.722"E
        r'(\d{1,3})[°*o]\s*(\d{1,2})[\'′/]\s*(\d{1,2}(?:[.,]\d+)?)[\"″]\s*([NS])\s+(\d{1,3})[°*o]\s*(\d{1,2})[\'′/]\s*(\d{1,2}(?:[.,]\d+)?)[\"″]\s*([EW])',
        
        # Format decimal degrees: -6.876562, 107.577145
        r'(-?\d{1,3}\.\d+),\s*(-?\d{1,3}\.\d+)',
        
        # Format dengan plus/minus: +6.876562, +107.577145
        r'([+-]?\d{1,3}\.\d+),?\s+([+-]?\d{1,3}\.\d+)',
    ]
    
    # Normalisasi teks
    cleaned_text = (text
                   .replace(',', '.')
                   .replace('*', '°')
                   .replace('o', '°')
                   .replace('O', '°')
                   .replace('′', "'")
                   .replace('″', '"')
                   .replace('/', "'")
                   .replace('\\', "'"))
    
    logger.debug(f"Parsing coordinates from cleaned text: {cleaned_text}")
    
    for i, pattern in enumerate(patterns):
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        if matches:
            match = matches[0]
            
            # Handle DMS format (patterns 0-3)
            if len(match) == 8:
                lat_deg, lat_min, lat_sec, lat_dir = match[0], match[1], match[2], match[3]
                lon_deg, lon_min, lon_sec, lon_dir = match[4], match[5], match[6], match[7]
                
                latitude = f"{lat_deg}° {lat_min}' {lat_sec}\" {lat_dir.upper()}"
                longitude = f"{lon_deg}° {lon_min}' {lon_sec}\" {lon_dir.upper()}"
                
                logger.debug(f"DMS Pattern {i+1} matched: {latitude}, {longitude}")
                return latitude, longitude
            
            # Handle decimal degrees format (patterns 4-5)
            elif len(match) == 2:
                lat_decimal, lon_decimal = match[0], match[1]
                
                # Convert to DMS format for consistency
                latitude = convert_decimal_to_dms(float(lat_decimal), is_latitude=True)
                longitude = convert_decimal_to_dms(float(lon_decimal), is_latitude=False)
                
                logger.debug(f"Decimal Pattern {i+1} matched: {latitude}, {longitude}")
                return latitude, longitude
    
    logger.debug("No coordinate patterns matched")
    return "", ""

def convert_decimal_to_dms(decimal_coord: float, is_latitude: bool = True) -> str:
    """
    Convert decimal degrees ke DMS (Degrees, Minutes, Seconds) format
    """
    try:
        # Tentukan arah (N/S untuk latitude, E/W untuk longitude)
        if is_latitude:
            direction = 'S' if decimal_coord < 0 else 'N'
        else:
            direction = 'W' if decimal_coord < 0 else 'E'
        
        # Ambil nilai absolut
        abs_coord = abs(decimal_coord)
        
        # Extract degrees, minutes, seconds
        degrees = int(abs_coord)
        minutes_float = (abs_coord - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        
        # Format dengan presisi yang tepat
        return f"{degrees}° {minutes}' {seconds:.3f}\" {direction}"
        
    except Exception as e:
        logger.error(f"Error converting decimal to DMS: {e}")
        return ""

def create_empty_entry(no: int, entry: Dict[str, Any], error: str = "") -> Dict[str, Any]:
    """
    Buat entry kosong ketika ekstraksi gagal
    """
    return {
        "no": no,
        "jalur": entry.get("jalur", ""),
        "latitude": "",
        "longitude": "",
        "kondisi": entry.get("kondisi", ""),
        "keterangan": entry.get("keterangan", ""),
        "foto_path": "",
        "image": "",
        "gps_confidence": "",
        "extraction_method": "failed",
        "processing_time": "0.00s",
        "gps_context": json.dumps({"error": error}) if error else ""
    }

def generate_processing_report(gps_results: List[GPSExtractionResult]) -> Dict[str, Any]:
    """
    Generate laporan processing dari hasil ekstraksi GPS
    """
    total_images = len(gps_results)
    successful_extractions = sum(1 for r in gps_results if r.is_valid)
    failed_extractions = total_images - successful_extractions
    
    # Hitung rata-rata processing time
    avg_processing_time = 0
    if total_images > 0:
        total_time = sum(r.processing_time for r in gps_results)
        avg_processing_time = total_time / total_images
    
    # Group by method
    method_stats = {}
    for result in gps_results:
        method = result.method or "unknown"
        if method not in method_stats:
            method_stats[method] = {"count": 0, "success": 0}
        method_stats[method]["count"] += 1
        if result.is_valid:
            method_stats[method]["success"] += 1
    
    # Hitung confidence stats
    confidences = [r.confidence for r in gps_results if r.confidence > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Errors
    errors = [r.error for r in gps_results if r.error]
    
    report = {
        "total_images": total_images,
        "successful_extractions": successful_extractions,
        "failed_extractions": failed_extractions,
        "success_rate": (successful_extractions / total_images * 100) if total_images > 0 else 0,
        "average_processing_time": round(avg_processing_time, 2),
        "average_confidence": round(avg_confidence, 2),
        "method_statistics": method_stats,
        "error_count": len(errors),
        "unique_errors": len(set(errors)),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return report

def cleanup_temp_files(file_paths: List[str]):
    """
    Cleanup file-file sementara
    """
    cleaned_count = 0
    for file_path in file_paths:
        try:
            if file_path and Path(file_path).exists():
                Path(file_path).unlink()
                cleaned_count += 1
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
    
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} temporary files")

def validate_coordinate_format(latitude: str, longitude: str) -> bool:
    """
    Validasi format koordinat
    """
    try:
        if not latitude or not longitude:
            return False
        
        # Pattern untuk DMS format
        dms_pattern = r'^\d{1,3}°\s*\d{1,2}\'\s*\d{1,2}(?:\.\d+)?\"\s*[NSEW]$'
        
        lat_valid = bool(re.match(dms_pattern, latitude.strip()))
        lon_valid = bool(re.match(dms_pattern, longitude.strip()))
        
        return lat_valid and lon_valid
        
    except Exception as e:
        logger.error(f"Error validating coordinate format: {e}")
        return False

# Helper functions untuk debugging
def debug_coordinate_extraction(image_path: str) -> None:
    """
    Debug function untuk melihat detail proses ekstraksi
    """
    logger.setLevel(logging.DEBUG)
    
    print(f"Debugging coordinate extraction for: {image_path}")
    print("=" * 60)
    
    # Test simple extraction
    lat, lon = extract_coordinates_with_validation(image_path)
    print(f"Simple extraction result: {lat}, {lon}")
    
    # Test advanced extraction
    result = extract_gps_coordinates_advanced(image_path)
    print(f"Advanced extraction result:")
    print(f"  Latitude: {result.latitude}")
    print(f"  Longitude: {result.longitude}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Method: {result.method}")
    print(f"  Valid: {result.is_valid}")
    print(f"  Processing time: {result.processing_time:.2f}s")
    print(f"  Error: {result.error}")
    print(f"  Context: {result.context}")
    
    if result.latitude and result.longitude:
        print(f"Indonesia check: {is_coordinate_in_indonesia(result.latitude, result.longitude)}")

# Example usage
if __name__ == "__main__":
    # Test dengan gambar contoh
    test_image = "test_coordinate_image.jpg"
    if Path(test_image).exists():
        debug_coordinate_extraction(test_image)
    else:
        print("Test image not found. Please provide a test image path.")