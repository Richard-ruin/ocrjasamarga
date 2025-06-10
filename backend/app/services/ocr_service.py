import easyocr
import re
import cv2
import numpy as np
from typing import Tuple, Optional
from PIL import Image, ImageEnhance, ImageFilter
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

reader = easyocr.Reader(['en'], gpu=False)

def preprocess_image_for_coordinates(image_path: str) -> str:
    """
    Preprocessing gambar untuk meningkatkan akurasi OCR pada koordinat
    """
    try:
        # Baca gambar dengan OpenCV
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Tidak dapat membaca gambar: {image_path}")
            return image_path
        
        # Convert ke grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive threshold untuk meningkatkan kontras teks
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        denoised = cv2.medianBlur(thresh, 3)
        
        # Dilate untuk memperjelas karakter
        kernel = np.ones((1,1), np.uint8)
        processed = cv2.dilate(denoised, kernel, iterations=1)
        
        # Simpan gambar yang sudah diproses
        processed_path = image_path.replace('.', '_processed.')
        cv2.imwrite(processed_path, processed)
        
        logger.debug(f"Gambar berhasil diproses: {processed_path}")
        return processed_path
        
    except Exception as e:
        logger.error(f"Error dalam preprocessing: {e}")
        return image_path

def extract_coordinates_with_regex(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Ekstrak koordinat menggunakan regex pattern yang lebih presisi
    """
    # Pattern untuk koordinat DMS (Degrees Minutes Seconds)
    # Format: 6°52'35.622"S 107°34'37.722"E
    coordinate_pattern = r"(\d{1,3})[°*]\s*(\d{1,2})['\s]*(\d{1,2}(?:\.\d+)?)[\"]\s*([NS])\s+(\d{1,3})[°*]\s*(\d{1,2})['\s]*(\d{1,2}(?:\.\d+)?)[\"]\s*([EW])"
    
    matches = re.findall(coordinate_pattern, text)
    
    if matches:
        match = matches[0]  # Ambil match pertama
        lat_deg, lat_min, lat_sec, lat_dir = match[0], match[1], match[2], match[3]
        lon_deg, lon_min, lon_sec, lon_dir = match[4], match[5], match[6], match[7]
        
        latitude = f"{lat_deg}° {lat_min}' {lat_sec}\" {lat_dir}"
        longitude = f"{lon_deg}° {lon_min}' {lon_sec}\" {lon_dir}"
        
        return latitude, longitude
    
    return None, None

def extract_coordinates_manual_parsing(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Manual parsing sebagai fallback jika regex gagal
    """
    # Bersihkan teks
    cleaned = clean_ocr_text(text)
    logger.debug(f"Cleaned text for manual parsing: {cleaned}")
    
    # Cari koordinat dengan mencari pattern angka + direction
    # Pattern: angka°angka'angka"Direction
    coords = re.findall(r'(\d{1,3}[°*]\d{1,2}[\']\d{1,2}(?:\.\d+)?[\"]\s*[NSEW])', cleaned)
    
    if len(coords) >= 2:
        lat_candidate = coords[0]
        lon_candidate = coords[1]
        
        # Normalisasi format
        latitude = normalize_coordinate(lat_candidate)
        longitude = normalize_coordinate(lon_candidate)
        
        return latitude, longitude
    
    return None, None

def clean_ocr_text(text: str) -> str:
    """
    Bersihkan hasil OCR dengan mapping karakter yang lebih comprehensive
    """
    # Mapping karakter yang sering salah dibaca OCR
    char_mapping = {
        'o': '°', 'O': '°', '*': '°', '0': '°',  # degree symbol
        '/': "'", '\\': "'", '|': "'", 'I': "'",  # minute symbol
        ',': '.', # decimal separator
        '"': '"', '"': '"', "'": "'", "'": "'",  # quote normalization
    }
    
    cleaned = text
    for old_char, new_char in char_mapping.items():
        cleaned = cleaned.replace(old_char, new_char)
    
    # Hapus karakter yang tidak diperlukan untuk koordinat
    cleaned = re.sub(r'[^\d°\'\"NSEW\s\.]', ' ', cleaned)
    
    # Normalisasi spasi
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def normalize_coordinate(coord_str: str) -> str:
    """
    Normalisasi format koordinat
    """
    # Extract numbers and direction
    numbers = re.findall(r'\d+(?:\.\d+)?', coord_str)
    direction = re.findall(r'[NSEW]', coord_str.upper())
    
    if len(numbers) >= 3 and direction:
        deg, minute, sec = numbers[0], numbers[1], numbers[2]
        dir_char = direction[0]
        return f"{deg}° {minute}' {sec}\" {dir_char}"
    elif len(numbers) >= 2 and direction:
        deg, minute = numbers[0], numbers[1]
        dir_char = direction[0]
        return f"{deg}° {minute}' 0\" {dir_char}"
    
    return coord_str

def extract_coordinates_from_image(image_path: str) -> Tuple[str, str]:
    """
    Fungsi utama untuk ekstrak koordinat dengan multiple strategies
    """
    try:
        # Step 1: Preprocess gambar
        processed_image_path = preprocess_image_for_coordinates(image_path)
        
        # Step 2: OCR pada gambar asli
        result_original = reader.readtext(image_path, detail=0)
        logger.debug(f"OCR Result (Original): {result_original}")
        
        # Step 3: OCR pada gambar yang sudah diproses
        if processed_image_path != image_path:
            result_processed = reader.readtext(processed_image_path, detail=0)
            logger.debug(f"OCR Result (Processed): {result_processed}")
        else:
            result_processed = result_original
        
        # Step 4: Gabungkan hasil OCR
        all_text = " ".join(result_original + result_processed)
        
        # Step 5: Strategi 1 - Regex extraction
        lat_regex, lon_regex = extract_coordinates_with_regex(all_text)
        if lat_regex and lon_regex:
            logger.debug(f"Regex extraction successful: {lat_regex}, {lon_regex}")
            return lat_regex, lon_regex
        
        # Step 6: Strategi 2 - Manual parsing
        lat_manual, lon_manual = extract_coordinates_manual_parsing(all_text)
        if lat_manual and lon_manual:
            logger.debug(f"Manual parsing successful: {lat_manual}, {lon_manual}")
            return lat_manual, lon_manual
        
        # Step 7: Strategi 3 - Fallback ke metode lama dengan perbaikan
        lat_fallback, lon_fallback = extract_coordinates_fallback(all_text)
        if lat_fallback and lon_fallback:
            logger.debug(f"Fallback method successful: {lat_fallback}, {lon_fallback}")
            return lat_fallback, lon_fallback
        
        logger.warning("Tidak berhasil mengekstrak koordinat dengan semua metode")
        return "", ""
        
    except Exception as e:
        logger.error(f"Error dalam extract_coordinates_from_image: {e}")
        return "", ""

def extract_coordinates_fallback(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fallback method - perbaikan dari metode lama
    """
    cleaned = clean_ocr_text(text)
    logger.debug(f"Fallback - Cleaned text: {cleaned}")
    
    # Cari posisi direction letters
    directions = re.finditer(r'[NSEW]', cleaned.upper())
    direction_positions = [(m.start(), m.group()) for m in directions]
    
    if len(direction_positions) >= 2:
        # Ambil 2 direction pertama (biasanya N/S untuk lintang, E/W untuk bujur)
        first_dir_pos, first_dir = direction_positions[0]
        second_dir_pos, second_dir = direction_positions[1]
        
        # Extract text sebelum masing-masing direction
        lat_text = cleaned[:first_dir_pos + 1].strip()
        lon_text = cleaned[first_dir_pos + 1:second_dir_pos + 1].strip()
        
        # Normalisasi
        latitude = normalize_coordinate_fallback(lat_text)
        longitude = normalize_coordinate_fallback(lon_text)
        
        # Validasi hasil
        if is_valid_coordinate(latitude, longitude):
            return latitude, longitude
    
    return None, None

def normalize_coordinate_fallback(text: str) -> str:
    """
    Normalisasi koordinat untuk fallback method
    """
    # Extract semua angka
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    direction = re.findall(r'[NSEW]', text.upper())
    
    if len(numbers) >= 3 and direction:
        # Filter angka yang masuk akal untuk koordinat
        valid_numbers = []
        for num in numbers:
            num_float = float(num)
            if num_float <= 180:  # Koordinat tidak mungkin > 180
                valid_numbers.append(num)
        
        if len(valid_numbers) >= 3:
            deg, minute, sec = valid_numbers[0], valid_numbers[1], valid_numbers[2]
            dir_char = direction[0]
            return f"{deg}° {minute}' {sec}\" {dir_char}"
    
    return text.strip()

def is_valid_coordinate(latitude: str, longitude: str) -> bool:
    """
    Validasi apakah koordinat masuk akal
    """
    try:
        # Extract degree values untuk validasi
        lat_deg = re.search(r'(\d+)°', latitude)
        lon_deg = re.search(r'(\d+)°', longitude)
        
        if lat_deg and lon_deg:
            lat_val = int(lat_deg.group(1))
            lon_val = int(lon_deg.group(1))
            
            # Validasi range koordinat
            if 0 <= lat_val <= 90 and 0 <= lon_val <= 180:
                return True
        
        return False
    except:
        return False