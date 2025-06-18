import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/manual")
def get_manual_configuration(vin: str):
    if len(vin) != 17:
        raise HTTPException(status_code=400, detail="VIN must be 17 characters long")

    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error contacting NHTSA API: {str(e)}")
