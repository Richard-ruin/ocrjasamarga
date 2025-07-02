# ocr_config.py
from paddleocr import PaddleOCR
import logging
import os
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global OCR instance
_ocr_instance = None

def get_ocr_instance() -> PaddleOCR:
    """
    Initialize PaddleOCR instance dengan konfigurasi optimal untuk bahasa Indonesia
    Updated untuk kompatibilitas dengan versi terbaru PaddleOCR
    """
    global _ocr_instance
    
    if _ocr_instance is None:
        try:
            # Konfigurasi PaddleOCR yang kompatibel dengan versi terbaru
            logger.info("Initializing PaddleOCR...")
            
            # Primary configuration - recommended for coordinate detection
            ocr_config = {
                'use_angle_cls': True,  # Deteksi rotasi teks
                'lang': 'en',          # English untuk angka dan simbol koordinat
                'det_limit_side_len': 960,  # Optimal untuk akurasi dan speed
                'det_limit_type': 'max',
                'rec_batch_num': 6,
                'max_text_length': 25,
                'rec_algorithm': 'SVTR_LCNet',  # Better accuracy for small text
                'drop_score': 0.3,     # Lower threshold untuk menangkap lebih banyak teks
            }
            
            _ocr_instance = PaddleOCR(**ocr_config)
            logger.info("✅ PaddleOCR initialized successfully with optimized config")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize PaddleOCR with optimized config: {e}")
            
            # Fallback dengan konfigurasi minimal
            try:
                logger.info("Trying fallback configuration...")
                _ocr_instance = PaddleOCR(
                    use_angle_cls=True,
                    lang='en'
                )
                logger.info("✅ PaddleOCR initialized with fallback config")
                
            except Exception as fallback_error:
                logger.error(f"❌ Fallback PaddleOCR initialization failed: {fallback_error}")
                
                # Last resort - basic config
                try:
                    logger.info("Trying basic configuration...")
                    _ocr_instance = PaddleOCR(lang='en')
                    logger.info("✅ PaddleOCR initialized with basic config")
                except Exception as basic_error:
                    logger.error(f"❌ Basic PaddleOCR initialization failed: {basic_error}")
                    raise Exception("Cannot initialize PaddleOCR with any configuration")
    
    return _ocr_instance

# Enhanced pattern untuk koordinat Indonesia dengan variasi format yang lebih fleksibel
COORDINATE_PATTERNS = {
    # Pattern utama untuk format standar: 6°52'35,698"S atau 6°52'35.698"S
    'latitude_primary': r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*[\"″]?\s*S",
    'longitude_primary': r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*[\"″]?\s*E",
    
    # Pattern alternatif untuk handling OCR errors dan variasi format
    'latitude_alternatives': [
        r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*[\"″]\s*S",  # Dengan tanda kutip
        r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*′\s*S",      # Dengan prime symbol
        r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*'\s*S",      # OCR salah baca " jadi '
        r"(\d+)[o°]\s*(\d+)'\s*([\d,\.]+)\s*[\"″]?\s*S",  # OCR salah baca ° jadi o
        r"(\d+)°\s*(\d+)[`']\s*([\d,\.]+)\s*[\"″]?\s*S", # OCR salah baca ' jadi `
        r"(\d+)\s*°\s*(\d+)\s*'\s*([\d,\.]+)\s*[\"″]?\s*S", # Dengan spasi ekstra
        r"(\d+)°(\d+)'([\d,\.]+)\"?S",                 # Tanpa spasi (format compact)
    ],
    'longitude_alternatives': [
        r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*[\"″]\s*E",
        r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*′\s*E",
        r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\s*'\s*E",
        r"(\d+)[o°]\s*(\d+)'\s*([\d,\.]+)\s*[\"″]?\s*E",
        r"(\d+)°\s*(\d+)[`']\s*([\d,\.]+)\s*[\"″]?\s*E",
        r"(\d+)\s*°\s*(\d+)\s*'\s*([\d,\.]+)\s*[\"″]?\s*E",
        r"(\d+)°(\d+)'([\d,\.]+)\"?E",
    ]
}

# Validasi range koordinat Indonesia (diperluas untuk handling margin error)
INDONESIA_BOUNDS = {
    'lat_min': -12.0,  # Diperluas dari -11.0 untuk margin error
    'lat_max': 7.0,    # Diperluas dari 6.0 untuk margin error
    'lon_min': 94.0,   # Diperluas dari 95.0 untuk margin error
    'lon_max': 142.0   # Diperluas dari 141.0 untuk margin error
}

# Validasi range koordinat Bandung dan sekitarnya (diperluas dengan margin)
BANDUNG_BOUNDS = {
    'lat_min': -7.8,   # Diperluas untuk area Bandung Raya
    'lat_max': -5.8,   # Diperluas untuk area Bandung Utara
    'lon_min': 106.5,  # Diperluas untuk area Bandung Barat
    'lon_max': 108.5   # Diperluas untuk area Bandung Timur
}

# Validasi tambahan untuk Jawa Barat
WEST_JAVA_BOUNDS = {
    'lat_min': -8.0,
    'lat_max': -5.5,
    'lon_min': 106.0,
    'lon_max': 109.0
}

# Konfigurasi OCR yang dioptimasi
OCR_CONFIG = {
    'confidence_threshold': 0.25,  # Threshold lebih rendah untuk menangkap lebih banyak teks
    'min_confidence_for_validation': 0.4,  # Threshold lebih tinggi untuk validasi akhir
    'max_image_size': (1920, 1080),
    'min_image_size': (800, 600),
    
    # Area crop yang dioptimasi untuk watermark koordinat
    'crop_areas': {
        'bottom_right': {
            'x_start': 0.35,  # Mulai dari 35% lebar gambar
            'y_start': 0.65,  # Mulai dari 65% tinggi gambar
            'width': 0.65,    # 65% lebar gambar
            'height': 0.35    # 35% tinggi gambar
        },
        'bottom_center': {
            'x_start': 0.25,
            'y_start': 0.75,
            'width': 0.5,
            'height': 0.25      
        },
        'full_bottom': {
            'x_start': 0.0,
            'y_start': 0.7,
            'width': 1.0,
            'height': 0.3
        }
    },
    
    # Preprocessing parameters
    'preprocessing': {
        'resize_factor': 2.0,         # Perbesar gambar untuk OCR yang lebih baik
        'gamma_correction': 1.2,      # Gamma untuk enhance contrast
        'clahe_clip_limit': 3.0,      # CLAHE untuk adaptive histogram
        'bilateral_d': 9,             # Bilateral filter parameter
        'bilateral_sigma_color': 75,
        'bilateral_sigma_space': 75,
        'gaussian_blur_kernel': (3, 3),
        'sharpen_kernel': [[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]
    }
}

# Enhanced OCR error corrections
OCR_CORRECTIONS = {
    # Character substitutions
    'o': '°',     # o -> degree symbol
    'O': '°',     # O -> degree symbol  
    '0': '°',     # 0 -> degree symbol (dalam konteks koordinat)
    '`': "'",     # backtick -> apostrophe
    ''': "'",     # right single quotation -> apostrophe
    ''': "'",     # left single quotation -> apostrophe
    '″': '"',     # double prime -> quotation mark
    '′': "'",     # prime -> apostrophe
    '"': '"',     # left double quote -> standard quote
    '"': '"',     # right double quote -> standard quote
    
    # Decimal separators (Indonesia uses comma)
    '.': ',',     # dot -> comma untuk desimal Indonesia
    
    # Direction indicators
    'S ': 'S',    # Remove extra space after S
    'E ': 'E',    # Remove extra space after E
    ' S': 'S',    # Remove space before S
    ' E': 'E',    # Remove space before E
    
    # Common OCR mistakes for numbers in coordinates
    'l': '1',     # lowercase L -> 1
    'I': '1',     # uppercase i -> 1
    'O': '0',     # O -> 0 (dalam konteks angka)
    'S': '5',     # S -> 5 (dalam konteks angka, hati-hati dengan direction)
}

# Whitelist karakter yang valid untuk koordinat
VALID_COORDINATE_CHARS = set('0123456789°\'",SE ')

def validate_coordinate_bounds(lat: float, lon: float) -> dict:
    """
    Validasi koordinat dengan berbagai tingkatan
    Returns dict dengan informasi validasi
    """
    result = {
        'valid': False,
        'region': 'unknown',
        'confidence': 0.0,
        'warnings': []
    }
    
    try:
        # Level 1: Indonesia bounds
        if (INDONESIA_BOUNDS['lat_min'] <= lat <= INDONESIA_BOUNDS['lat_max'] and
            INDONESIA_BOUNDS['lon_min'] <= lon <= INDONESIA_BOUNDS['lon_max']):
            
            result['valid'] = True
            result['region'] = 'Indonesia'
            result['confidence'] = 0.6
            
            # Level 2: West Java bounds (higher confidence)
            if (WEST_JAVA_BOUNDS['lat_min'] <= lat <= WEST_JAVA_BOUNDS['lat_max'] and
                WEST_JAVA_BOUNDS['lon_min'] <= lon <= WEST_JAVA_BOUNDS['lon_max']):
                
                result['region'] = 'West Java'
                result['confidence'] = 0.8
                
                # Level 3: Bandung bounds (highest confidence)
                if (BANDUNG_BOUNDS['lat_min'] <= lat <= BANDUNG_BOUNDS['lat_max'] and
                    BANDUNG_BOUNDS['lon_min'] <= lon <= BANDUNG_BOUNDS['lon_max']):
                    
                    result['region'] = 'Bandung Area'
                    result['confidence'] = 0.95
            
        else:
            result['warnings'].append(f"Coordinates outside Indonesia bounds: {lat}, {lon}")
            
        return result
        
    except Exception as e:
        result['warnings'].append(f"Validation error: {str(e)}")
        return result

# Retry configuration untuk different OCR strategies
RETRY_STRATEGIES = [
    {
        'name': 'high_accuracy',
        'params': {
            'det_limit_side_len': 1280,
            'drop_score': 0.2,
            'rec_batch_num': 1
        }
    },
    {
        'name': 'high_recall', 
        'params': {
            'det_limit_side_len': 640,
            'drop_score': 0.4,
            'rec_batch_num': 10
        }
    },
    {
        'name': 'balanced',
        'params': {
            'det_limit_side_len': 960,
            'drop_score': 0.3,
            'rec_batch_num': 6
        }
    }
]