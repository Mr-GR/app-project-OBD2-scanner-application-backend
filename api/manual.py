import requests
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter()

@router.get("/manual", tags=["VIN Decoder"])
def get_manual_configuration(vin: str):
    """
    Decode comprehensive vehicle data from a 17-character VIN.
    Returns detailed vehicle information for card display.
    """
    if len(vin) != 17:
        raise HTTPException(status_code=400, detail="VIN must be 17 characters long")

    url = (
        f"https://vpic.nhtsa.dot.gov/api/vehicles/"
        f"DecodeVinValuesExtended/{vin}?format=json"
    )

    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        result = data["Results"][0]
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"NHTSA request failed: {exc}")

    # Enhanced vehicle information for card display
    vehicle_info = {
        "basic_info": {
            "make": result.get("Make", "Unknown"),
            "model": result.get("Model", "Unknown"),
            "year": result.get("ModelYear", "Unknown"),
            "vehicle_type": result.get("VehicleType", "Unknown"),
        },
        "detailed_info": {
            "body_class": result.get("BodyClass", "Unknown"),
            "engine_model": result.get("EngineModel", "Unknown"),
            "fuel_type": result.get("FuelTypePrimary", "Unknown"),
            "transmission": result.get("TransmissionStyle", "Unknown"),
            "drive_type": result.get("DriveType", "Unknown"),
            "engine_cylinders": result.get("EngineCylinders", "Unknown"),
            "engine_displacement": result.get("DisplacementL", "Unknown"),
        },
        "manufacturer_info": {
            "manufacturer": result.get("ManufacturerName", "Unknown"),
            "plant_city": result.get("PlantCity", "Unknown"),
            "plant_state": result.get("PlantState", "Unknown"),
            "plant_country": result.get("PlantCountry", "Unknown"),
        },
        "vin_details": {
            "vin": vin,
            "check_digit": vin[8] if len(vin) > 8 else "Unknown",
            "model_year": vin[9] if len(vin) > 9 else "Unknown",
            "plant_code": vin[10] if len(vin) > 10 else "Unknown",
        }
    }

    return vehicle_info
