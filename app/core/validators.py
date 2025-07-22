# validators.py
import re
import phonenumbers
from typing import Optional
from phonenumbers import NumberParseException


def validate_phone(phone: str) -> tuple[bool, Optional[str]]:
    """Validate and format phone number"""
    try:
        parsed = phonenumbers.parse(phone, None)
        
        if not phonenumbers.is_valid_number(parsed):
            return False, None
        
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return True, formatted
        
    except NumberParseException:
        return False, None


def validate_filename(filename: str) -> bool:
    """Validate uploaded filename"""
    if not filename or len(filename.strip()) == 0:
        return False
    
    if len(filename) > 255:
        return False
    
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
    if any(char in filename for char in invalid_chars):
        return False
    
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
        'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
        'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    base_name = filename.split('.')[0].upper()
    if base_name in reserved_names:
        return False
    
    return True


def validate_ip_address(ip: str) -> bool:
    """Validate IP address (IPv4 or IPv6)"""
    if not ip:
        return False
    
    ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    ipv6_pattern = r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$|^::$'
    
    return bool(re.match(ipv4_pattern, ip) or re.match(ipv6_pattern, ip))


def validate_mime_type(mime_type: str) -> bool:
    """Validate MIME type format"""
    if not mime_type:
        return False
    
    mime_pattern = r'^[a-zA-Z][a-zA-Z0-9][a-zA-Z0-9\!\#\$\&\-\^\_]*\/[a-zA-Z0-9][a-zA-Z0-9\!\#\$\&\-\^\_\+]*$'
    return bool(re.match(mime_pattern, mime_type))


def sanitize_user_agent(user_agent: str) -> str:
    """Sanitize user agent string"""
    if not user_agent:
        return "Unknown"
    
    sanitized = re.sub(r'[<>"\']', '', user_agent)
    return sanitized[:500]  


def validate_exposure_minutes(minutes: int) -> bool:
    """Validate exposure duration for premium users"""
    if minutes <= 0:
        return False
    
    max_minutes = 24 * 60
    return minutes <= max_minutes