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

# Full Diagnostic Scan Schemas
class FullDiagnosticScanRequest(BaseModel):
    """Request for full diagnostic scan"""
    scan_type: str = Field(description="Type of scan: 'quick', 'comprehensive', 'emissions', 'custom'")
    vehicle_id: Optional[int] = Field(None, description="Vehicle ID for database storage")
    custom_systems: Optional[List[str]] = Field(None, description="Custom systems to scan for 'custom' type")
    include_vin: bool = Field(True, description="Include VIN retrieval")
    include_live_parameters: bool = Field(True, description="Include live parameter data")
    include_freeze_frame: bool = Field(True, description="Include freeze frame data")

class TroubleCodeInfo(BaseModel):
    """Enhanced trouble code information"""
    code: str
    description: str
    system: str  # "Powertrain", "Body", "Chassis", "Network"
    severity: str  # "Critical", "Moderate", "Low"
    status: str  # "Active", "Pending", "Permanent"

class ReadinessMonitor(BaseModel):
    """Readiness monitor status"""
    monitor_name: str
    status: str  # "Ready", "Not Ready", "Not Supported"
    
class LiveParameter(BaseModel):
    """Live parameter data"""
    name: str
    value: Optional[float]
    unit: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
class FreezeFrameData(BaseModel):
    """Freeze frame data snapshot"""
    dtc_code: str
    frame_data: Dict[str, Any]

class VehicleInformation(BaseModel):
    """Complete vehicle information"""
    vin: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[str] = None
    engine_type: Optional[str] = None
    calibration_ids: List[str] = []

class FullDiagnosticScanResponse(BaseModel):
    """Complete diagnostic scan results"""
    scan_id: str
    scan_type: str
    timestamp: datetime
    status: str  # "completed", "failed", "partial"
    
    # Vehicle Information
    vehicle_info: Optional[VehicleInformation] = None
    
    # Trouble Codes
    trouble_codes: List[TroubleCodeInfo] = []
    active_codes_count: int = 0
    pending_codes_count: int = 0
    permanent_codes_count: int = 0
    
    # Readiness Monitors
    readiness_monitors: List[ReadinessMonitor] = []
    monitors_ready: int = 0
    monitors_not_ready: int = 0
    
    # Live Parameters
    live_parameters: List[LiveParameter] = []
    
    # Freeze Frame Data
    freeze_frames: List[FreezeFrameData] = []
    
    # Summary
    overall_health: str = "unknown"  # "good", "warning", "critical"
    scan_duration: Optional[float] = None
    error_messages: List[str] = []

# Upload scan data schemas (for Flutter app)
class UploadScanTroubleCode(BaseModel):
    """Trouble code for upload"""
    code: str
    description: str
    system: str
    type: str = "active"

class UploadScanReadinessMonitor(BaseModel):
    """Readiness monitor for upload"""
    monitor_name: str
    status: str

class UploadScanLiveParameter(BaseModel):
    """Live parameter for upload"""
    parameter_name: str
    parameter_value: str
    unit: Optional[str] = None

class UploadFullScanRequest(BaseModel):
    """Request to upload full scan data from Flutter app"""
    vehicle_id: int
    scan_type: str  # 'quick', 'comprehensive', 'emissions', 'custom'
    vehicle_info: Optional[str] = ""
    trouble_codes: List[UploadScanTroubleCode] = []
    live_parameters: Dict[str, str] = {}
    readiness_monitors: Dict[str, str] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class UploadFullScanResponse(BaseModel):
    """Response for uploading full scan data"""
    success: bool
    scan_id: int
    message: str

 