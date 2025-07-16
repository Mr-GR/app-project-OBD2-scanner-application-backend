from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class ScannerConnectRequest(BaseModel):
    """Request to connect to OBD2 scanner"""
    port: Optional[str] = Field(None, description="Serial port for scanner connection")
    baudrate: int = Field(38400, description="Baud rate for serial communication")
    connection_type: Optional[str] = Field(None, description="Connection type: 'bluetooth' or 'usb'")
    bluetooth_pin: Optional[str] = Field("1234", description="Bluetooth pairing PIN if needed")
    fast_mode: bool = Field(False, description="Use fast connection mode (production)")

class ScannerConnectResponse(BaseModel):
    """Response for scanner connection"""
    connected: bool
    port: Optional[str] = None
    connection_type: Optional[str] = None
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

class BluetoothPairRequest(BaseModel):
    """Request to pair with Bluetooth OBD2 device"""
    device_name: str = Field(description="Name of the Bluetooth device to pair with")
    pin: str = Field("1234", description="Bluetooth pairing PIN")

class BluetoothPairResponse(BaseModel):
    """Response for Bluetooth pairing"""
    success: bool
    device_name: str
    message: str
    paired_port: Optional[str] = None

class LiveDataRequest(BaseModel):
    """Request to store live OBD2 data from Flutter app"""
    rpm: Optional[int] = None
    speed: Optional[int] = None
    engine_temp: Optional[int] = None
    fuel_level: Optional[int] = None
    throttle_position: Optional[int] = None
    vin: Optional[str] = Field(None, description="Vehicle Identification Number from OBD2")
    timestamp: Optional[datetime] = None

class LiveDataResponse(BaseModel):
    """Response with live OBD2 data for Flutter app"""
    rpm: Optional[int] = None
    speed: Optional[int] = None
    engine_temp: Optional[int] = None
    fuel_level: Optional[int] = None
    throttle_position: Optional[int] = None
    vin: Optional[str] = Field(None, description="Vehicle Identification Number from OBD2")
    timestamp: Optional[datetime] = None

class DTCRequest(BaseModel):
    """Request to clear DTC codes"""
    clear_codes: bool = Field(True, description="Clear all DTC codes")

class DTCCode(BaseModel):
    """Individual DTC code"""
    code: str
    description: str

class DTCListResponse(BaseModel):
    """Response with active and pending DTC codes"""
    active_codes: List[DTCCode] = []
    pending_codes: List[DTCCode] = []

class VehicleHealthResponse(BaseModel):
    """Response with vehicle health check"""
    engine: str = "unknown"
    transmission: str = "unknown"
    emissions: str = "unknown"
    fuel_system: str = "unknown"
    cooling_system: str = "unknown"
    electrical_system: str = "unknown"
    brake_system: str = "unknown"
    exhaust_system: str = "unknown"

class ScannerStatusFlutterResponse(BaseModel):
    """Response with scanner status for Flutter app"""
    connected: bool
    device_name: Optional[str] = None
    battery_voltage: Optional[float] = None

 