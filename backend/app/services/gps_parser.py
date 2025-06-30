import re
from typing import Tuple, Optional, Dict, Any, List
import logging
from datetime import datetime

from app.utils.helpers import dms_to_decimal, decimal_to_dms, validate_indonesia_coordinates

logger = logging.getLogger(__name__)

class GPSParser:
    """Parser untuk ekstraksi dan validasi koordinat GPS dari text OCR"""
    
    def __init__(self):
        # Pattern untuk berbagai format koordinat
        self.dms_patterns = [
            # Standard DMS dengan koma: 6°52'35,698"S 107°34'37,321"E
            r"(\d+)°(\d+)'([\d,\.]+)\"([NS])\s+(\d+)°(\d+)'([\d,\.]+)\"([EW])",
            
            # DMS tanpa spasi: 6°52'35.698"S107°34'37.321"E
            r"(\d+)°(\d+)'([\d,\.]+)\"([NS])(\d+)°(\d+)'([\d,\.]+)\"([EW])",
            
            # DMS dengan spasi berbeda: 6° 52' 35.698" S 107° 34' 37.321" E
            r"(\d+)°\s*(\d+)'\s*([\d,\.]+)\"\s*([NS])\s+(\d+)°\s*(\d+)'\s*([\d,\.]+)\"\s*([EW])",
            
            # Format dengan pemisah lain
            r"(\d+)°(\d+)'([\d,\.]+)\"([NS])\s*[/,;]\s*(\d+)°(\d+)'([\d,\.]+)\"([EW])"
        ]
        
        # Pattern untuk timestamp
        self.timestamp_patterns = [
            r"\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}\.\d{2}\.\d{2}",  # 13 Jun 2025 12.59.06
            r"\d{1,2}/\d{1,2}/\d{4}\s+\d{2}:\d{2}:\d{2}",      # 13/06/2025 12:59:06
            r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}",          # 2025-06-13 12:59:06
        ]
        
        # Pattern untuk arah kompas
        self.compass_pattern = r"\d+°\s*[NSEW]{1,2}"
        
        # Keywords untuk identifikasi alamat Indonesia
        self.address_keywords = {
            'street': ['jalan', 'jl.', 'jl', 'street', 'st.'],
            'district': ['kecamatan', 'kec.', 'kec', 'district'],
            'subdistrict': ['kelurahan', 'kel.', 'desa', 'subdistrict'],
            'city': ['kota', 'kabupaten', 'kab.', 'city'],
            'province': ['provinsi', 'prov.', 'province']
        }
    
    def extract_coordinates_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract koordinat GPS dari text OCR
        
        Args:
            text: Raw text dari OCR
            
        Returns:
            Dict dengan hasil ekstraksi koordinat
        """
        try:
            result = {
                "success": False,
                "latitude": None,
                "longitude": None,
                "coordinates_found": False,
                "format_detected": None,
                "decimal_coordinates": None,
                "validation": None,
                "raw_matches": [],
                "errors": []
            }
            
            # Normalize text
            normalized_text = self._normalize_text(text)
            
            # Try each pattern
            for i, pattern in enumerate(self.dms_patterns):
                matches = re.findall(pattern, normalized_text, re.IGNORECASE)
                
                if matches:
                    for match in matches:
                        lat_dms, lng_dms = self._parse_dms_match(match)
                        
                        if lat_dms and lng_dms:
                            # Validate coordinates
                            validation = self._validate_extracted_coordinates(lat_dms, lng_dms)
                            
                            if validation["valid"]:
                                result.update({
                                    "success": True,
                                    "latitude": lat_dms,
                                    "longitude": lng_dms,
                                    "coordinates_found": True,
                                    "format_detected": f"DMS_PATTERN_{i+1}",
                                    "decimal_coordinates": validation["decimal_coordinates"],
                                    "validation": validation,
                                    "raw_matches": [match]
                                })
                                
                                logger.info(f"Coordinates extracted: {lat_dms}, {lng_dms}")
                                return result
                            else:
                                result["errors"].extend(validation["errors"])
            
            # If no valid coordinates found
            if not result["coordinates_found"]:
                result["errors"].append("No valid Indonesia coordinates found in text")
                logger.warning("No valid coordinates found in OCR text")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract coordinates: {e}")
            return {
                "success": False,
                "error": str(e),
                "latitude": None,
                "longitude": None,
                "coordinates_found": False
            }
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text untuk parsing yang lebih baik"""
        # Replace common OCR errors
        normalized = text.replace('°', '°')  # Ensure proper degree symbol
        normalized = normalized.replace('"', '"')  # Ensure proper quote
        normalized = normalized.replace("'", "'")  # Ensure proper apostrophe
        
        # Fix common number recognition errors
        normalized = re.sub(r'[oO]', '0', normalized)  # O to 0
        normalized = re.sub(r'[lI]', '1', normalized)  # l/I to 1
        
        return normalized
    
    def _parse_dms_match(self, match: tuple) -> Tuple[Optional[str], Optional[str]]:
        """Parse DMS match tuple ke latitude dan longitude strings"""
        try:
            if len(match) == 8:
                # Standard format: (lat_deg, lat_min, lat_sec, lat_dir, lng_deg, lng_min, lng_sec, lng_dir)
                lat_deg, lat_min, lat_sec, lat_dir, lng_deg, lng_min, lng_sec, lng_dir = match
                
                # Construct DMS strings
                lat_dms = f"{lat_deg}°{lat_min}'{lat_sec}\"{lat_dir}"
                lng_dms = f"{lng_deg}°{lng_min}'{lng_sec}\"{lng_dir}"
                
                return lat_dms, lng_dms
            
            return None, None
            
        except Exception as e:
            logger.error(f"Failed to parse DMS match: {e}")
            return None, None
    
    def _validate_extracted_coordinates(self, latitude: str, longitude: str) -> Dict[str, Any]:
        """Validate extracted coordinates untuk Indonesia"""
        return validate_indonesia_coordinates(latitude, longitude)
    
    def extract_additional_info(self, text: str) -> Dict[str, Any]:
        """
        Extract informasi tambahan dari text OCR
        
        Args:
            text: Raw text dari OCR
            
        Returns:
            Dict dengan informasi tambahan
        """
        try:
            info = {
                "timestamp": None,
                "compass_direction": None,
                "address_components": {},
                "full_address": None,
                "raw_lines": text.split('\n')
            }
            
            # Extract timestamp
            info["timestamp"] = self._extract_timestamp(text)
            
            # Extract compass direction
            info["compass_direction"] = self._extract_compass_direction(text)
            
            # Extract address components
            info["address_components"] = self._extract_address_components(text)
            
            # Try to construct full address
            info["full_address"] = self._construct_full_address(info["address_components"], text)
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to extract additional info: {e}")
            return {"error": str(e)}
    
    def _extract_timestamp(self, text: str) -> Optional[str]:
        """Extract timestamp dari text"""
        for pattern in self.timestamp_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
    
    def _extract_compass_direction(self, text: str) -> Optional[str]:
        """Extract arah kompas dari text"""
        match = re.search(self.compass_pattern, text)
        if match:
            return match.group(0)
        return None
    
    def _extract_address_components(self, text: str) -> Dict[str, str]:
        """Extract komponen alamat dari text"""
        components = {}
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip().lower()
            if not line:
                continue
            
            # Check for each address component type
            for component_type, keywords in self.address_keywords.items():
                for keyword in keywords:
                    if keyword in line:
                        # Clean up the line
                        cleaned_line = line.replace(keyword, '').strip()
                        if cleaned_line:
                            components[component_type] = cleaned_line
                        break
        
        return components
    
    def _construct_full_address(self, components: Dict[str, str], original_text: str) -> Optional[str]:
        """Construct alamat lengkap dari komponen"""
        try:
            # Try to find lines that look like address parts
            lines = original_text.split('\n')
            address_lines = []
            
            for line in lines:
                line = line.strip()
                
                # Skip lines with coordinates or timestamps
                if re.search(r'\d+°\d+\'\d+', line) or re.search(r'\d{2}:\d{2}:\d{2}', line):
                    continue
                
                # Look for address-like lines
                if any(keyword in line.lower() for keywords in self.address_keywords.values() for keyword in keywords):
                    address_lines.append(line)
                elif len(line) > 10 and not line.isdigit():  # Generic address line
                    address_lines.append(line)
            
            if address_lines:
                return ', '.join(address_lines[:5])  # Limit to 5 components
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to construct full address: {e}")
            return None
    
    def parse_gps_data_comprehensive(self, text: str) -> Dict[str, Any]:
        """
        Comprehensive parsing untuk semua data GPS dari text
        
        Args:
            text: Raw text dari OCR
            
        Returns:
            Dict dengan semua informasi yang diekstrak
        """
        try:
            result = {
                "coordinates": self.extract_coordinates_from_text(text),
                "additional_info": self.extract_additional_info(text),
                "raw_text": text,
                "processed_at": datetime.utcnow().isoformat(),
                "parsing_success": False
            }
            
            # Determine overall success
            result["parsing_success"] = result["coordinates"]["success"]
            
            return result
            
        except Exception as e:
            logger.error(f"Comprehensive GPS parsing failed: {e}")
            return {
                "error": str(e),
                "raw_text": text,
                "parsing_success": False,
                "processed_at": datetime.utcnow().isoformat()
            }

# Global GPS parser instance
gps_parser = GPSParser()