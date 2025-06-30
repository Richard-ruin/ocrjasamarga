from bson import ObjectId
from typing import Any
import uuid
import hashlib
import re
from datetime import datetime
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

class PyObjectId(ObjectId):
    """Custom ObjectId class for Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ])
        ])

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "format": "objectid"}

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def generate_session_id() -> str:
    """Generate unique session ID"""
    return f"session_{uuid.uuid4().hex[:12]}"

def generate_file_hash(file_content: bytes) -> str:
    """Generate MD5 hash for file content"""
    return hashlib.md5(file_content).hexdigest()

def validate_indonesia_coordinates(latitude: str, longitude: str) -> bool:
    """
    Validate if coordinates are within Indonesia bounds
    Indonesia bounds: Latitude 6°N to 11°S, Longitude 95°E to 141°E
    """
    try:
        # Parse DMS to decimal
        lat_decimal = dms_to_decimal(latitude)
        lng_decimal = dms_to_decimal(longitude)
        
        # Check Indonesia bounds
        # Latitude: -11 to 6 (South is negative)
        # Longitude: 95 to 141 (East is positive)
        if -11 <= lat_decimal <= 6 and 95 <= lng_decimal <= 141:
            return True
        return False
    except:
        return False

def dms_to_decimal(dms_string: str) -> float:
    """
    Convert DMS (Degrees Minutes Seconds) to decimal degrees
    Example: "6°52'35,698\"S" -> -6.876582777777778
    """
    # Remove spaces and normalize
    dms = dms_string.strip()
    
    # Regex to parse DMS format
    # Matches: degrees°minutes'seconds"direction
    pattern = r"(\d+)°(\d+)'([\d,\.]+)\"([NSEW])"
    match = re.match(pattern, dms)
    
    if not match:
        raise ValueError(f"Invalid DMS format: {dms_string}")
    
    degrees = float(match.group(1))
    minutes = float(match.group(2))
    seconds = float(match.group(3).replace(',', '.'))  # Handle comma decimal
    direction = match.group(4)
    
    # Convert to decimal
    decimal = degrees + (minutes / 60) + (seconds / 3600)
    
    # Apply direction (South and West are negative)
    if direction in ['S', 'W']:
        decimal = -decimal
    
    return decimal

def decimal_to_dms(decimal: float, coord_type: str = 'lat') -> str:
    """
    Convert decimal degrees to DMS format
    coord_type: 'lat' for latitude, 'lng' for longitude
    """
    is_negative = decimal < 0
    decimal = abs(decimal)
    
    degrees = int(decimal)
    minutes_float = (decimal - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    
    # Determine direction
    if coord_type == 'lat':
        direction = 'S' if is_negative else 'N'
    else:  # longitude
        direction = 'W' if is_negative else 'E'
    
    return f"{degrees}°{minutes}'{seconds:.3f}\"{direction}"

def extract_gps_from_text(text: str) -> tuple:
    """
    Extract GPS coordinates from OCR text
    Returns: (latitude, longitude) or (None, None)
    """
    # Pattern untuk koordinat Indonesia (S, E)
    coord_pattern = r"(\d+°\d+'\d+[,\.]\d+\"[NS])\s+(\d+°\d+'\d+[,\.]\d+\"[EW])"
    
    matches = re.findall(coord_pattern, text)
    
    if matches:
        lat, lng = matches[0]
        # Validate coordinates
        if validate_indonesia_coordinates(lat, lng):
            return lat, lng
    
    return None, None

def clean_filename(filename: str) -> str:
    """Clean filename for safe storage"""
    # Remove special characters
    cleaned = re.sub(r'[^\w\-_\.]', '_', filename)
    # Add timestamp to avoid conflicts
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = cleaned.rsplit('.', 1) if '.' in cleaned else (cleaned, '')
    return f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def parse_address_from_text(text: str) -> dict:
    """
    Parse address components from OCR text
    Expected format: Street/District/Subdistrict/City/Province
    """
    lines = text.split('\n')
    address_info = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for address components
        if any(keyword in line.lower() for keyword in ['jalan', 'jl.', 'street']):
            address_info['street'] = line
        elif any(keyword in line.lower() for keyword in ['kecamatan', 'district']):
            address_info['district'] = line
        elif any(keyword in line.lower() for keyword in ['kelurahan', 'desa']):
            address_info['subdistrict'] = line
        elif any(keyword in line.lower() for keyword in ['kota', 'kabupaten', 'city']):
            address_info['city'] = line
        elif any(keyword in line.lower() for keyword in ['provinsi', 'province']):
            address_info['province'] = line
    
    return address_info