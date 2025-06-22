# api/manual.py

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/manual", tags=["VIN Decoder"])
def get_manual_configuration(vin: str):
    """
    Decode basic vehicle data (make, model, year, type) from a 17-character VIN.
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

    return {
        "make": result.get("Make", "Unknown"),
        "model": result.get("Model", "Unknown"),
        "year": result.get("ModelYear", "Unknown"),
        "vehicle_type": result.get("VehicleType", "Unknown"),
    }
