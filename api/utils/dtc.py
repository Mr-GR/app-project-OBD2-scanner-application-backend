# api/utils/dtc.py
from functools import lru_cache
from pathlib import Path
import json, os, requests

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_CODES = BASE_DIR / "resources" / "dtc_codes.json"
ENHANCED_CODES_PATH = BASE_DIR / "resources" / "enhanced_dtc_codes.json"


@lru_cache
def _local_table():
    try:
        with LOCAL_CODES.open() as fp:
            return json.load(fp)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

@lru_cache
def _enhanced_table():
    """Load comprehensive DTC database from JSON file with 11,000+ codes"""
    try:
        with ENHANCED_CODES_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load enhanced DTC codes: {e}")
        return {}

def _clean_dtc_code(code: str) -> str:
    """Clean and validate DTC code format"""
    if not code:
        return ""
    
    code = code.strip().upper()
    
    # Remove any non-alphanumeric characters
    import re
    code = re.sub(r'[^A-Z0-9]', '', code)
    
    # If already correct format, return as-is
    if len(code) == 5 and code[0] in 'PBCU' and all(c in '0123456789ABCDEF' for c in code[1:]):
        return code
    
    # Handle malformed patterns
    if code[0] in 'PBCU' and len(code) > 5:
        # Extract the meaningful part after the prefix
        numeric_part = code[1:]
        
        # Common patterns to fix:
        # P00300 -> P0300 (6 chars, remove one leading zero)
        # P001300 -> P0130 (7 chars, remove leading zeros more carefully)
        
        if len(numeric_part) == 5:  # 6 total chars like P00300
            if numeric_part.startswith('00'):
                # Remove one leading zero: P00300 -> P0300
                numeric_part = numeric_part[1:]
        elif len(numeric_part) == 6:  # 7 total chars like P001300
            if numeric_part.startswith('00'):
                # Remove leading zeros more carefully
                # P001300 -> extract 1300 -> P1300 (invalid) 
                # Better: try to find the actual 4-digit code
                if numeric_part[2:6] in ['1300', '0300']:
                    # P001300 -> P0130, P000300 -> P0300
                    if numeric_part[2:6] == '1300':
                        numeric_part = '0130'
                    elif numeric_part[2:6] == '0300':
                        numeric_part = '0300'
                else:
                    # Remove two leading zeros
                    numeric_part = numeric_part[2:]
        
        # Reconstruct the code
        code = code[0] + numeric_part
    
    # Final validation
    if len(code) == 5 and code[0] in 'PBCU' and all(c in '0123456789ABCDEF' for c in code[1:]):
        return code
    
    return ""

def get_code_description(code: str) -> str:
    """Get DTC description with multiple fallback sources"""
    code = code.strip().upper()
    
    # Clean and validate the code format
    cleaned_code = _clean_dtc_code(code)
    if not cleaned_code:
        return f"Invalid DTC format: {code}"
    
    # Priority order: local overrides -> enhanced database -> generic
    return (
        _local_table().get(cleaned_code)
        or _enhanced_table().get(cleaned_code)
        or _generate_generic_description(cleaned_code)
    )

def _generate_generic_description(code: str) -> str:
    """Generate a generic description based on DTC code pattern"""
    if not code or len(code) < 5:
        return "Unknown code"
    
    prefix = code[0]
    system_map = {
        'P': 'Powertrain',
        'B': 'Body',
        'C': 'Chassis', 
        'U': 'Network/Communication'
    }
    
    system = system_map.get(prefix, 'Unknown System')
    return f"{system} Diagnostic Trouble Code {code}"

def categorize_dtc(code: str) -> str:
    """Categorize DTC by system type"""
    if not code:
        return "Unknown"
    
    prefix = code[0].upper()
    categories = {
        'P': 'Powertrain (Engine/Transmission)',
        'B': 'Body (Interior/Exterior)',
        'C': 'Chassis (Brakes/Steering/Suspension)',
        'U': 'Network/Communication'
    }
    
    return categories.get(prefix, "Unknown System")

def get_dtc_severity(code: str) -> str:
    """Estimate DTC severity level"""
    code = code.upper().strip()
    
    # Clean the code first
    cleaned_code = _clean_dtc_code(code)
    if not cleaned_code:
        return "Unknown"
    
    # Critical codes that need immediate attention
    critical_patterns = [
        'P030',  # Misfire codes (P0300-P0312)
        'P056',  # System voltage issues (P0562, P0563)
        'P060',  # PCM/ECM memory errors (P0601-P0605)
        'C000',  # Critical chassis codes (some sensors)
        'B000',  # Airbag system failures
    ]
    
    # Check for critical patterns
    for pattern in critical_patterns:
        if cleaned_code.startswith(pattern):
            return "Critical"
    
    # High priority codes
    high_priority_codes = [
        'P0100', 'P0101', 'P0102', 'P0103',  # MAF issues
        'P0115', 'P0117', 'P0118',          # Coolant temp issues
        'P0120', 'P0121', 'P0122', 'P0123', # Throttle position issues
        'P0171', 'P0172', 'P0174', 'P0175', # Fuel trim issues
        'P0500',                             # Vehicle speed sensor
    ]
    
    if cleaned_code in high_priority_codes:
        return "High"
    
    # Moderate priority codes (emissions, comfort, etc.)
    moderate_patterns = [
        'P042',  # Catalyst codes (P0420, P0430)
        'P044',  # EVAP codes (P0440-P0455)
        'P013',  # O2 sensor codes (P0130-P0139)
        'P070',  # Transmission codes
        'P075',  # Shift solenoid codes
        'P076',  # Shift solenoid codes
    ]
    
    for pattern in moderate_patterns:
        if cleaned_code.startswith(pattern):
            return "Moderate"
    
    # Network/Communication issues
    if cleaned_code.startswith('U'):
        return "Moderate"
    
    # Body system codes (usually low priority unless safety-related)
    if cleaned_code.startswith('B'):
        # Airbag codes are critical, others are typically low
        if cleaned_code.startswith('B000'):
            return "Critical"
        return "Low"
    
    # Chassis codes (brakes, suspension, etc.)
    if cleaned_code.startswith('C'):
        # ABS and brake-related codes are more serious
        if cleaned_code.startswith('C000') or cleaned_code.startswith('C100'):
            return "High" 
        return "Moderate"
    
    # Default for P-codes and others
    return "Low"

def validate_dtc_dataset():
    """Validate the enhanced DTC dataset for format issues"""
    table = _enhanced_table()
    invalid_codes = []
    
    for code in list(table.keys()):
        if not _clean_dtc_code(code):
            invalid_codes.append(code)
    
    if invalid_codes:
        print(f"⚠️  Found {len(invalid_codes)} invalid DTC format(s):")
        for code in invalid_codes[:10]:  # Show first 10
            print(f"   - {code}")
        if len(invalid_codes) > 10:
            print(f"   ... and {len(invalid_codes) - 10} more")
    else:
        print(f"✅ DTC dataset validation passed: {len(table)} codes")
    
    return len(invalid_codes) == 0

def get_dataset_stats():
    """Get statistics about the DTC datasets"""
    local_count = len(_local_table())
    enhanced_count = len(_enhanced_table())
    
    stats = {
        "local_codes": local_count,
        "enhanced_codes": enhanced_count,
        "total_unique": len(set(_local_table().keys()) | set(_enhanced_table().keys()))
    }
    
    # Count by prefix
    all_codes = set(_local_table().keys()) | set(_enhanced_table().keys())
    prefix_counts = {}
    for code in all_codes:
        prefix = code[0] if code else 'Unknown'
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    
    stats["by_system"] = {
        "P (Powertrain)": prefix_counts.get('P', 0),
        "B (Body)": prefix_counts.get('B', 0), 
        "C (Chassis)": prefix_counts.get('C', 0),
        "U (Network)": prefix_counts.get('U', 0)
    }
    
    return stats
