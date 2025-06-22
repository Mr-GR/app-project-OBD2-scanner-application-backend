# api/routers/diagnostics.py
import requests
from fastapi import APIRouter, HTTPException, status

from api.schemas.diagnostics import (
    DiagnosticsRequest,
    DiagnosticsResponse,
    CodeInfo,
)
from api.utils.dtc import get_code_description

router = APIRouter()

NHTSA_URL = (
    "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
)

@router.post("/diagnostics", response_model=DiagnosticsResponse)
def diagnose(payload: DiagnosticsRequest):
    # Decode VIN first
    try:
        r = requests.get(NHTSA_URL.format(vin=payload.vin), timeout=5)
        r.raise_for_status()
        vin_data = r.json()["Results"][0]
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"NHTSA VIN service failed: {exc}",
        )

    vin_info = {
        "make": vin_data.get("Make", "Unknown"),
        "model": vin_data.get("Model", "Unknown"),
        "year": vin_data.get("ModelYear", "Unknown"),
        "vehicle_type": vin_data.get("VehicleType", "Unknown"),
    }

    decoded = [
        CodeInfo(code=c, description=get_code_description(c)) for c in payload.codes
    ]
    return DiagnosticsResponse(vin_info=vin_info, codes=decoded)
