from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class ScannerConnectRequest(BaseModel):
    """Request to connect to OBD2 scanner"""
    port: Optional[str] = Field(None, description="Serial port for scanner connection")
    baudrate: int = Field(38400, description="Baud rate for serial communication")

class ScannerConnectResponse(BaseModel):
    """Response for scanner connection"""
    connected: bool
    port: Optional[str] = None
    message: str
    available_ports: List[Dict[str, str]] = []

class SensorDataRequest(BaseModel):
    """Request to get sensor data"""
    pids: List[str] = Field(description="List of PIDs to read")

class SensorData(BaseModel):
    """Individual sensor data"""
    pid: str
    value: float
    unit: str
    description: str

class SensorDataResponse(BaseModel):
    """Response with sensor data"""
    timestamp: datetime
    data: List[SensorData]
    success: bool
    message: str

class DTCResponse(BaseModel):
    """Response with DTC codes"""
    timestamp: datetime
    codes: List[str]
    descriptions: List[str]
    count: int
    success: bool
    message: str

class VehicleInfoResponse(BaseModel):
    """Response with vehicle information"""
    timestamp: datetime
    vin: Optional[str] = None
    calibration_ids: List[str] = []
    success: bool
    message: str

class ScannerStatusResponse(BaseModel):
    """Response with scanner status"""
    connected: bool
    port: Optional[str] = None
    baudrate: Optional[int] = None
    last_activity: Optional[datetime] = None

class ManualDataRequest(BaseModel):
    """Request for manual data input"""
    vin: Optional[str] = Field(None, description="Vehicle Identification Number")
    dtc_codes: List[str] = Field(description="List of DTC codes")
    sensor_data: Optional[Dict[str, float]] = Field(None, description="Manual sensor readings")
    notes: Optional[str] = Field(None, description="Additional notes")

class ScanSessionRequest(BaseModel):
    """Request to start a new scan session"""
    session_name: str = Field(description="Name for the scan session")
    include_sensors: bool = Field(True, description="Include sensor data in scan")
    include_dtc: bool = Field(True, description="Include DTC codes in scan")
    include_vehicle_info: bool = Field(True, description="Include vehicle information")

class ScanSessionResponse(BaseModel):
    """Response for scan session"""
    session_id: str
    session_name: str
    timestamp: datetime
    status: str  # "running", "completed", "failed"
    data: Dict[str, Any] = {}
    message: str 