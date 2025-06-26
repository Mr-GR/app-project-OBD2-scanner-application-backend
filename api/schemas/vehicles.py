from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class VehicleCreateRequest(BaseModel):
    vin: str = Field(..., min_length=17, max_length=17, description="17-character VIN")
    is_primary: Optional[bool] = False

class VehicleResponse(BaseModel):
    id: int
    vin: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    vehicle_type: Optional[str] = None
    is_primary: bool
    created_at: datetime
    
    # Additional NHTSA fields (optional)
    body_class: Optional[str] = None
    engine_model: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    engine_cylinders: Optional[str] = None
    engine_displacement: Optional[str] = None

    class Config:
        from_attributes = True

class VehicleListResponse(BaseModel):
    vehicles: List[VehicleResponse]
    total: int

class UserCreateRequest(BaseModel):
    email: str
    name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True