from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import requests
from datetime import datetime

from db.database import get_db
from db.models import User, UserVehicle
from api.schemas.vehicles import (
    VehicleCreateRequest,
    VehicleResponse,
    VehicleListResponse,
    UserCreateRequest,
    UserResponse
)

router = APIRouter()

NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"

# Simple user management (for now, we'll use a default user)
def get_or_create_default_user(db: Session) -> User:
    """Get or create a default user for vehicle storage"""
    user = db.query(User).filter(User.email == "default@obd2scanner.com").first()
    if not user:
        user = User(
            email="default@obd2scanner.com",
            name="Default User"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.post("/vehicles", response_model=VehicleResponse)
async def add_vehicle(request: VehicleCreateRequest, db: Session = Depends(get_db)):
    """Add a new vehicle by VIN"""
    
    # Check if vehicle already exists
    existing_vehicle = db.query(UserVehicle).filter(UserVehicle.vin == request.vin).first()
    if existing_vehicle:
        raise HTTPException(status_code=400, detail="Vehicle with this VIN already exists")
    
    # Get or create default user
    user = get_or_create_default_user(db)
    
    try:
        # Decode VIN using NHTSA API
        response = requests.get(NHTSA_URL.format(vin=request.vin), timeout=10)
        response.raise_for_status()
        vin_data = response.json()["Results"][0]
        
        # Create vehicle record
        vehicle = UserVehicle(
            user_id=user.id,
            vin=request.vin,
            make=vin_data.get("Make", "Unknown"),
            model=vin_data.get("Model", "Unknown"),
            year=int(vin_data.get("ModelYear", 0)) if vin_data.get("ModelYear") else None,
            vehicle_type=vin_data.get("VehicleType", "Unknown"),
            is_primary=request.is_primary or False
        )
        
        # If this is set as primary, make all other vehicles non-primary
        if vehicle.is_primary:
            db.query(UserVehicle).filter(UserVehicle.user_id == user.id).update({"is_primary": False})
        
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        
        return VehicleResponse(
            id=vehicle.id,
            vin=vehicle.vin,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            vehicle_type=vehicle.vehicle_type,
            is_primary=vehicle.is_primary,
            created_at=vehicle.created_at,
            # Additional NHTSA data
            body_class=vin_data.get("BodyClass"),
            engine_model=vin_data.get("EngineModel"),
            fuel_type=vin_data.get("FuelTypePrimary"),
            transmission=vin_data.get("TransmissionStyle"),
            engine_cylinders=vin_data.get("EngineCylinders"),
            engine_displacement=vin_data.get("DisplacementL")
        )
        
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"VIN lookup failed: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add vehicle: {str(e)}")

@router.get("/vehicles", response_model=VehicleListResponse)
async def get_vehicles(db: Session = Depends(get_db)):
    """Get all vehicles for the default user"""
    
    user = get_or_create_default_user(db)
    vehicles = db.query(UserVehicle).filter(UserVehicle.user_id == user.id).order_by(UserVehicle.created_at.desc()).all()
    
    vehicle_responses = []
    for vehicle in vehicles:
        vehicle_responses.append(VehicleResponse(
            id=vehicle.id,
            vin=vehicle.vin,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            vehicle_type=vehicle.vehicle_type,
            is_primary=vehicle.is_primary,
            created_at=vehicle.created_at
        ))
    
    return VehicleListResponse(
        vehicles=vehicle_responses,
        total=len(vehicle_responses)
    )

@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Get a specific vehicle by ID"""
    
    user = get_or_create_default_user(db)
    vehicle = db.query(UserVehicle).filter(
        UserVehicle.id == vehicle_id,
        UserVehicle.user_id == user.id
    ).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    return VehicleResponse(
        id=vehicle.id,
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        vehicle_type=vehicle.vehicle_type,
        is_primary=vehicle.is_primary,
        created_at=vehicle.created_at
    )

@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Delete a vehicle"""
    
    user = get_or_create_default_user(db)
    vehicle = db.query(UserVehicle).filter(
        UserVehicle.id == vehicle_id,
        UserVehicle.user_id == user.id
    ).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    was_primary = vehicle.is_primary
    
    # Delete the vehicle
    db.delete(vehicle)
    
    # If we deleted the primary vehicle, optionally set another one as primary
    # But this is optional - users can have no primary vehicle
    if was_primary:
        # Check if there are other vehicles
        remaining_vehicles = db.query(UserVehicle).filter(UserVehicle.user_id == user.id).all()
        if remaining_vehicles:
            # Optionally make the first remaining vehicle primary
            # Comment this out if you want users to manually select primary
            # remaining_vehicles[0].is_primary = True
            pass
    
    db.commit()
    
    return {
        "message": "Vehicle deleted successfully",
        "was_primary": was_primary,
        "remaining_vehicles": db.query(UserVehicle).filter(UserVehicle.user_id == user.id).count()
    }

@router.put("/vehicles/{vehicle_id}/primary", response_model=VehicleResponse)
async def set_primary_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Set a vehicle as primary"""
    
    user = get_or_create_default_user(db)
    vehicle = db.query(UserVehicle).filter(
        UserVehicle.id == vehicle_id,
        UserVehicle.user_id == user.id
    ).first()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Make all other vehicles non-primary
    db.query(UserVehicle).filter(UserVehicle.user_id == user.id).update({"is_primary": False})
    
    # Set this vehicle as primary
    vehicle.is_primary = True
    db.commit()
    db.refresh(vehicle)
    
    return VehicleResponse(
        id=vehicle.id,
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        vehicle_type=vehicle.vehicle_type,
        is_primary=vehicle.is_primary,
        created_at=vehicle.created_at
    )

@router.get("/vehicles/primary/info")
async def get_primary_vehicle_info(db: Session = Depends(get_db)):
    """Get primary vehicle info for chat context"""
    
    user = get_or_create_default_user(db)
    
    # Get primary vehicle
    primary_vehicle = db.query(UserVehicle).filter(
        UserVehicle.user_id == user.id,
        UserVehicle.is_primary == True
    ).first()
    
    # Get total vehicle count
    total_vehicles = db.query(UserVehicle).filter(UserVehicle.user_id == user.id).count()
    
    if not primary_vehicle:
        return {
            "has_primary_vehicle": False,
            "total_vehicles": total_vehicles,
            "message": "No primary vehicle set" if total_vehicles > 0 else "No vehicles registered"
        }
    
    return {
        "has_primary_vehicle": True,
        "total_vehicles": total_vehicles,
        "vehicle": {
            "id": primary_vehicle.id,
            "vin": primary_vehicle.vin,
            "make": primary_vehicle.make,
            "model": primary_vehicle.model,
            "year": primary_vehicle.year,
            "vehicle_type": primary_vehicle.vehicle_type
        }
    }

@router.delete("/vehicles/primary")
async def remove_primary_vehicle(db: Session = Depends(get_db)):
    """Remove primary status from all vehicles (no primary vehicle)"""
    
    user = get_or_create_default_user(db)
    
    # Set all vehicles to non-primary
    updated_count = db.query(UserVehicle).filter(UserVehicle.user_id == user.id).update({"is_primary": False})
    db.commit()
    
    return {
        "message": "Primary vehicle status removed from all vehicles",
        "vehicles_updated": updated_count
    }

@router.delete("/vehicles/all")
async def delete_all_vehicles(db: Session = Depends(get_db)):
    """Delete all vehicles for the user"""
    
    user = get_or_create_default_user(db)
    
    # Count vehicles before deletion
    vehicle_count = db.query(UserVehicle).filter(UserVehicle.user_id == user.id).count()
    
    # Delete all vehicles
    db.query(UserVehicle).filter(UserVehicle.user_id == user.id).delete()
    db.commit()
    
    return {
        "message": f"All {vehicle_count} vehicles deleted successfully",
        "deleted_count": vehicle_count
    }