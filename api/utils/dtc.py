# api/utils/dtc.py
from functools import lru_cache
from pathlib import Path
import json, os, requests

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_CODES = BASE_DIR / "resources" / "dtc_codes.json"

# Enhanced DTC database based on PyOBD
ENHANCED_DTCS = {
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0303": "Cylinder 3 Misfire Detected",
    "P0304": "Cylinder 4 Misfire Detected",
    "P0305": "Cylinder 5 Misfire Detected",
    "P0306": "Cylinder 6 Misfire Detected",
    "P0307": "Cylinder 7 Misfire Detected",
    "P0308": "Cylinder 8 Misfire Detected",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0174": "System Too Lean (Bank 2)",
    "P0175": "System Too Rich (Bank 2)",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0430": "Catalyst System Efficiency Below Threshold (Bank 2)",
    "P0441": "Evaporative Emission Control System Incorrect Purge Flow",
    "P0442": "Evaporative Emission Control System Leak Detected (small leak)",
    "P0443": "Evaporative Emission Control System Purge Control Valve Circuit Malfunction",
    "P0446": "Evaporative Emission Control System Vent Control Circuit Malfunction",
    "P0455": "Evaporative Emission Control System Leak Detected (large leak)",
    "P0500": "Vehicle Speed Sensor Malfunction",
    "P0506": "Idle Control System RPM Lower Than Expected",
    "P0507": "Idle Control System RPM Higher Than Expected",
    "P0562": "System Voltage Low",
    "P0563": "System Voltage High",
    "P0601": "Internal Control Module Memory Check Sum Error",
    "P0700": "Transmission Control System Malfunction",
    "P0750": "Shift Solenoid A Malfunction",
    "P0751": "Shift Solenoid A Performance or Stuck Off",
    "P0752": "Shift Solenoid A Stuck On",
    "P0753": "Shift Solenoid A Electrical",
    "P0755": "Shift Solenoid B Malfunction",
    "P0756": "Shift Solenoid B Performance or Stuck Off",
    "P0757": "Shift Solenoid B Stuck On",
    "P0758": "Shift Solenoid B Electrical",
    "P0760": "Shift Solenoid C Malfunction",
    "P0761": "Shift Solenoid C Performance or Stuck Off",
    "P0762": "Shift Solenoid C Stuck On",
    "P0763": "Shift Solenoid C Electrical",
    "P1000": "OBD System Readiness Test Not Complete",
    "U0001": "High Speed CAN Communication Bus",
    "U0100": "Lost Communication With ECM/PCM 'A'",
    "U0101": "Lost Communication With TCM",
    "U0155": "Lost Communication With Instrument Panel Control Module",
}

@lru_cache
def _local_table():
    try:
        with LOCAL_CODES.open() as fp:
            return json.load(fp)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def get_code_description(code: str) -> str:
    """Get DTC description with fallback to enhanced database"""
    code = code.strip().upper()
    
    # Try local file first
    local_desc = _local_table().get(code)
    if local_desc:
        return local_desc
    
    # Fallback to enhanced database
    enhanced_desc = ENHANCED_DTCS.get(code)
    if enhanced_desc:
        return enhanced_desc
    
    # Generate generic description based on code pattern
    return _generate_generic_description(code)

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
    code = code.upper()
    
    # Critical codes that need immediate attention
    critical_codes = ['P0300', 'P0301', 'P0302', 'P0303', 'P0304', 'P0562', 'P0563']
    if code in critical_codes:
        return "Critical"
    
    # Emissions-related codes
    emissions_codes = ['P0420', 'P0430', 'P0441', 'P0442', 'P0455']
    if code in emissions_codes:
        return "Moderate"
    
    # Network/Communication issues
    if code.startswith('U'):
        return "Moderate"
    
    # Default
    return "Low"
