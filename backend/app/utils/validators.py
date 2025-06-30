import re
from typing import Optional, List, Dict, Any
from datetime import datetime
import validators as external_validators
from email_validator import validate_email, EmailNotValidError

from app.utils.constants import (
    ALLOWED_IMAGE_EXTENSIONS, 
    ALLOWED_MIME_TYPES,
    INDONESIA_BOUNDS,
    USER_ROLES,
    JADWAL_STATUS,
    INSPEKSI_STATUS,
    KONDISI_JALAN
)

def validate_email_address(email: str) -> Dict[str, Any]:
    """Validate email address format"""
    try:
        valid = validate_email(email)
        return {
            "valid": True,
            "email": valid.email,
            "message": "Valid email address"
        }
    except EmailNotValidError as e:
        return {
            "valid": False,
            "email": email,
            "error": str(e),
            "message": "Invalid email address"
        }

def validate_username(username: str) -> Dict[str, Any]:
    """Validate username format and requirements"""
    errors = []
    
    if len(username) < 3:
        errors.append("Username must be at least 3 characters long")
    
    if len(username) > 50:
        errors.append("Username must not exceed 50 characters")
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors.append("Username can only contain letters, numbers, and underscores")
    
    if username.startswith('_') or username.endswith('_'):
        errors.append("Username cannot start or end with underscore")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "message": "Valid username" if len(errors) == 0 else "Invalid username"
    }

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    errors = []
    score = 0
    
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long")
    else:
        score += 1
    
    if len(password) >= 8:
        score += 1
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    else:
        score += 1
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    else:
        score += 1
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    else:
        score += 1
    
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        score += 1
    
    # Calculate strength
    if score <= 2:
        strength = "weak"
    elif score <= 4:
        strength = "medium"
    else:
        strength = "strong"
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "strength": strength,
        "score": score,
        "message": f"Password strength: {strength}"
    }

def validate_file_upload(filename: str, content_type: str, file_size: int, max_size: int = 10485760) -> Dict[str, Any]:
    """Validate uploaded file"""
    errors = []
    
    # Check file size
    if file_size > max_size:
        errors.append(f"File size ({file_size} bytes) exceeds maximum limit ({max_size} bytes)")
    
    # Check file extension
    file_ext = None
    if filename and '.' in filename:
        file_ext = '.' + filename.rsplit('.', 1)[1].lower()
        if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
            errors.append(f"File extension {file_ext} not allowed. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
    else:
        errors.append("File must have a valid extension")
    
    # Check MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        errors.append(f"Content type {content_type} not allowed. Allowed: {', '.join(ALLOWED_MIME_TYPES)}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "file_extension": file_ext,
        "content_type": content_type,
        "file_size": file_size,
        "message": "Valid file" if len(errors) == 0 else "Invalid file"
    }

def validate_dms_coordinates(latitude: str, longitude: str) -> Dict[str, Any]:
    """Validate DMS (Degrees Minutes Seconds) coordinates"""
    errors = []
    
    # DMS pattern: digits°digits'digits.digits"[NSEW]
    dms_pattern = r'^(\d+)°(\d+)\'([\d,\.]+)"([NSEW])$'
    
    # Validate latitude
    lat_match = re.match(dms_pattern, latitude.strip())
    if not lat_match:
        errors.append("Latitude must be in DMS format: e.g., 6°52'35,698\"S")
    else:
        lat_deg, lat_min, lat_sec, lat_dir = lat_match.groups()
        if int(lat_deg) > 90:
            errors.append("Latitude degrees cannot exceed 90")
        if int(lat_min) >= 60:
            errors.append("Latitude minutes cannot exceed 59")
        if float(lat_sec.replace(',', '.')) >= 60:
            errors.append("Latitude seconds cannot exceed 59.999")
        if lat_dir not in ['N', 'S']:
            errors.append("Latitude direction must be N or S")
    
    # Validate longitude
    lng_match = re.match(dms_pattern, longitude.strip())
    if not lng_match:
        errors.append("Longitude must be in DMS format: e.g., 107°34'37,321\"E")
    else:
        lng_deg, lng_min, lng_sec, lng_dir = lng_match.groups()
        if int(lng_deg) > 180:
            errors.append("Longitude degrees cannot exceed 180")
        if int(lng_min) >= 60:
            errors.append("Longitude minutes cannot exceed 59")
        if float(lng_sec.replace(',', '.')) >= 60:
            errors.append("Longitude seconds cannot exceed 59.999")
        if lng_dir not in ['E', 'W']:
            errors.append("Longitude direction must be E or W")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "latitude": latitude,
        "longitude": longitude,
        "message": "Valid DMS coordinates" if len(errors) == 0 else "Invalid DMS coordinates"
    }

def validate_indonesia_coordinates(latitude: str, longitude: str) -> Dict[str, Any]:
    """Validate if coordinates are within Indonesia bounds"""
    # First validate DMS format
    dms_validation = validate_dms_coordinates(latitude, longitude)
    if not dms_validation["valid"]:
        return dms_validation
    
    try:
        from app.utils.helpers import dms_to_decimal
        
        # Convert to decimal
        lat_decimal = dms_to_decimal(latitude)
        lng_decimal = dms_to_decimal(longitude)
        
        # Check Indonesia bounds
        errors = []
        if lat_decimal < INDONESIA_BOUNDS["LAT_MIN"] or lat_decimal > INDONESIA_BOUNDS["LAT_MAX"]:
            errors.append(f"Latitude {lat_decimal}° is outside Indonesia bounds ({INDONESIA_BOUNDS['LAT_MIN']}° to {INDONESIA_BOUNDS['LAT_MAX']}°)")
        
        if lng_decimal < INDONESIA_BOUNDS["LNG_MIN"] or lng_decimal > INDONESIA_BOUNDS["LNG_MAX"]:
            errors.append(f"Longitude {lng_decimal}° is outside Indonesia bounds ({INDONESIA_BOUNDS['LNG_MIN']}° to {INDONESIA_BOUNDS['LNG_MAX']}°)")
        
        # Additional check for Indonesia-specific patterns
        if lat_decimal > 0:
            errors.append("Indonesia coordinates should have South latitude (negative)")
        
        if lng_decimal < 0:
            errors.append("Indonesia coordinates should have East longitude (positive)")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "decimal_coordinates": {
                "latitude": lat_decimal,
                "longitude": lng_decimal
            },
            "within_indonesia": len(errors) == 0,
            "message": "Valid Indonesia coordinates" if len(errors) == 0 else "Coordinates outside Indonesia"
        }
        
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Failed to convert coordinates: {str(e)}"],
            "message": "Invalid coordinate format"
        }

def validate_user_role(role: str) -> Dict[str, Any]:
    """Validate user role"""
    valid_roles = list(USER_ROLES.values())
    
    if role not in valid_roles:
        return {
            "valid": False,
            "error": f"Invalid role. Must be one of: {', '.join(valid_roles)}",
            "allowed_roles": valid_roles
        }
    
    return {
        "valid": True,
        "role": role,
        "message": "Valid user role"
    }

def validate_jadwal_status(status: str) -> Dict[str, Any]:
    """Validate jadwal status"""
    valid_statuses = list(JADWAL_STATUS.values())
    
    if status not in valid_statuses:
        return {
            "valid": False,
            "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            "allowed_statuses": valid_statuses
        }
    
    return {
        "valid": True,
        "status": status,
        "message": "Valid jadwal status"
    }

def validate_kondisi_jalan(kondisi: str) -> Dict[str, Any]:
    """Validate kondisi jalan"""
    valid_kondisi = list(KONDISI_JALAN.values())
    kondisi_lower = kondisi.lower()
    
    if kondisi_lower not in valid_kondisi:
        return {
            "valid": False,
            "error": f"Invalid kondisi. Must be one of: {', '.join(valid_kondisi)}",
            "allowed_kondisi": valid_kondisi
        }
    
    return {
        "valid": True,
        "kondisi": kondisi_lower,
        "message": "Valid kondisi jalan"
    }

def validate_pagination(limit: int, skip: int) -> Dict[str, Any]:
    """Validate pagination parameters"""
    errors = []
    
    if limit < 1:
        errors.append("Limit must be at least 1")
    elif limit > 100:
        errors.append("Limit cannot exceed 100")
    
    if skip < 0:
        errors.append("Skip cannot be negative")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "limit": limit,
        "skip": skip,
        "message": "Valid pagination" if len(errors) == 0 else "Invalid pagination"
    }

def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
    """Validate date range"""
    errors = []
    
    if start_date and end_date:
        if start_date > end_date:
            errors.append("Start date cannot be after end date")
        
        # Check if date range is too large (more than 1 year)
        if (end_date - start_date).days > 365:
            errors.append("Date range cannot exceed 1 year")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "start_date": start_date,
        "end_date": end_date,
        "message": "Valid date range" if len(errors) == 0 else "Invalid date range"
    }

def validate_session_id(session_id: str) -> Dict[str, Any]:
    """Validate session ID format"""
    # Session ID should start with 'session_' followed by 12 hex characters
    pattern = r'^session_[a-f0-9]{12}$'
    
    if not re.match(pattern, session_id):
        return {
            "valid": False,
            "error": "Invalid session ID format. Expected: session_[12 hex chars]",
            "session_id": session_id
        }
    
    return {
        "valid": True,
        "session_id": session_id,
        "message": "Valid session ID"
    }