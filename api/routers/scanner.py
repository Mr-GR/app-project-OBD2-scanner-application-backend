# api/routers/scanner.py
import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Query
from api.utils.elm327 import ELM327Scanner
from api.utils.dtc import get_code_description
from api.schemas.scanner import (
    ScannerConnectRequest,
    ScannerConnectResponse,
    SensorDataRequest,
    SensorDataResponse,
    DTCResponse,
    VehicleInfoResponse,
    ScannerStatusResponse,
    ManualDataRequest,
    ScanSessionRequest,
    ScanSessionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Global scanner instance
scanner = ELM327Scanner()
scan_sessions: Dict[str, Dict[str, Any]] = {}

@router.get("/scanner/ports", response_model=List[Dict[str, str]])
async def list_available_ports():
    """List available serial ports for OBD2 scanners"""
    try:
        ports = scanner.list_available_ports()
        return ports
    except Exception as e:
        logger.error(f"Error listing ports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list ports: {str(e)}"
        )

@router.post("/scanner/connect", response_model=ScannerConnectResponse)
async def connect_scanner(request: ScannerConnectRequest):
    """Connect to OBD2 scanner"""
    try:
        # Get available ports
        available_ports = scanner.list_available_ports()
        
        # Connect to scanner
        connected = scanner.connect(request.port)
        
        if connected:
            return ScannerConnectResponse(
                connected=True,
                port=scanner.port,
                message="Successfully connected to OBD2 scanner",
                available_ports=available_ports
            )
        else:
            return ScannerConnectResponse(
                connected=False,
                message="Failed to connect to OBD2 scanner",
                available_ports=available_ports
            )
            
    except Exception as e:
        logger.error(f"Error connecting to scanner: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection failed: {str(e)}"
        )

@router.post("/scanner/disconnect")
async def disconnect_scanner():
    """Disconnect from OBD2 scanner"""
    try:
        scanner.disconnect()
        return {"message": "Successfully disconnected from OBD2 scanner"}
    except Exception as e:
        logger.error(f"Error disconnecting from scanner: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Disconnection failed: {str(e)}"
        )

@router.get("/scanner/status", response_model=ScannerStatusResponse)
async def get_scanner_status():
    """Get current scanner status"""
    try:
        return ScannerStatusResponse(
            connected=scanner.connected,
            port=scanner.port,
            baudrate=scanner.baudrate if scanner.connected else None,
            last_activity=datetime.now() if scanner.connected else None
        )
    except Exception as e:
        logger.error(f"Error getting scanner status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )

@router.post("/scanner/sensors", response_model=SensorDataResponse)
async def get_sensor_data(request: SensorDataRequest):
    """Get sensor data from OBD2 scanner"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        sensor_data = []
        for pid in request.pids:
            data = scanner.get_sensor_data(pid)
            if data:
                sensor_data.append(data)
        
        return SensorDataResponse(
            timestamp=datetime.now(),
            data=sensor_data,
            success=True,
            message=f"Retrieved {len(sensor_data)} sensor readings"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sensor data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sensor data: {str(e)}"
        )

@router.get("/scanner/dtc", response_model=DTCResponse)
async def get_dtc_codes():
    """Get Diagnostic Trouble Codes from OBD2 scanner"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        codes = scanner.get_dtc_codes()
        descriptions = [get_code_description(code) for code in codes]
        
        return DTCResponse(
            timestamp=datetime.now(),
            codes=codes,
            descriptions=descriptions,
            count=len(codes),
            success=True,
            message=f"Found {len(codes)} DTC codes"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting DTC codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DTC codes: {str(e)}"
        )

@router.get("/scanner/vehicle-info", response_model=VehicleInfoResponse)
async def get_vehicle_info():
    """Get vehicle information from OBD2 scanner"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        info = scanner.get_vehicle_info()
        
        return VehicleInfoResponse(
            timestamp=datetime.now(),
            vin=info.get("vin"),
            calibration_ids=info.get("calibration_ids", []),
            success=True,
            message="Vehicle information retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vehicle info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vehicle info: {str(e)}"
        )

@router.post("/scanner/manual-data")
async def process_manual_data(request: ManualDataRequest):
    """Process manually entered OBD2 data"""
    try:
        # Process DTC codes
        dtc_descriptions = []
        for code in request.dtc_codes:
            description = get_code_description(code)
            dtc_descriptions.append(description)
        
        # Prepare response
        result = {
            "timestamp": datetime.now(),
            "vin": request.vin,
            "dtc_codes": request.dtc_codes,
            "dtc_descriptions": dtc_descriptions,
            "sensor_data": request.sensor_data or {},
            "notes": request.notes,
            "total_dtc": len(request.dtc_codes)
        }
        
        # If VIN provided, get vehicle info
        if request.vin:
            try:
                import requests
                url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{request.vin}?format=json"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    vin_data = r.json()["Results"][0]
                    result["vehicle_info"] = {
                        "make": vin_data.get("Make", "Unknown"),
                        "model": vin_data.get("Model", "Unknown"),
                        "year": vin_data.get("ModelYear", "Unknown"),
                        "vehicle_type": vin_data.get("VehicleType", "Unknown"),
                    }
            except Exception as e:
                logger.warning(f"Failed to get VIN info: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing manual data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process manual data: {str(e)}"
        )

@router.post("/scanner/scan-session", response_model=ScanSessionResponse)
async def start_scan_session(request: ScanSessionRequest, background_tasks: BackgroundTasks):
    """Start a new scan session"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        import uuid
        session_id = str(uuid.uuid4())
        
        # Create session
        scan_sessions[session_id] = {
            "session_name": request.session_name,
            "timestamp": datetime.now(),
            "status": "running",
            "data": {},
            "config": {
                "include_sensors": request.include_sensors,
                "include_dtc": request.include_dtc,
                "include_vehicle_info": request.include_vehicle_info
            }
        }
        
        # Start background scan
        background_tasks.add_task(
            perform_scan_session,
            session_id,
            request.include_sensors,
            request.include_dtc,
            request.include_vehicle_info
        )
        
        return ScanSessionResponse(
            session_id=session_id,
            session_name=request.session_name,
            timestamp=datetime.now(),
            status="running",
            data={},
            message="Scan session started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scan session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scan session: {str(e)}"
        )

@router.get("/scanner/scan-session/{session_id}", response_model=ScanSessionResponse)
async def get_scan_session(session_id: str):
    """Get scan session results"""
    try:
        if session_id not in scan_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scan session not found"
            )
        
        session = scan_sessions[session_id]
        return ScanSessionResponse(
            session_id=session_id,
            session_name=session["session_name"],
            timestamp=session["timestamp"],
            status=session["status"],
            data=session["data"],
            message="Scan session retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scan session: {str(e)}"
        )

@router.get("/scanner/dtc/lookup")
async def lookup_dtc_code(code: str = Query(..., description="DTC code to look up")):
    """
    Look up a single DTC code and return its description.
    """
    description = get_code_description(code)
    if description == "Unknown code":
        raise HTTPException(status_code=404, detail="Code not found")
    return {"code": code.upper(), "description": description}

async def perform_scan_session(session_id: str, include_sensors: bool, include_dtc: bool, include_vehicle_info: bool):
    """Background task to perform scan session"""
    try:
        session = scan_sessions[session_id]
        data = {}
        
        # Get sensor data
        if include_sensors:
            common_pids = ["0105", "010C", "010D", "010F", "0111"]  # Common sensor PIDs
            sensor_data = []
            for pid in common_pids:
                sensor = scanner.get_sensor_data(pid)
                if sensor:
                    sensor_data.append({
                        "pid": sensor.pid,
                        "value": sensor.value,
                        "unit": sensor.unit,
                        "description": sensor.description
                    })
            data["sensors"] = sensor_data
        
        # Get DTC codes
        if include_dtc:
            codes = scanner.get_dtc_codes()
            descriptions = [get_code_description(code) for code in codes]
            data["dtc_codes"] = codes
            data["dtc_descriptions"] = descriptions
            data["dtc_count"] = len(codes)
        
        # Get vehicle info
        if include_vehicle_info:
            vehicle_info = scanner.get_vehicle_info()
            data["vehicle_info"] = vehicle_info
        
        # Update session
        session["data"] = data
        session["status"] = "completed"
        
    except Exception as e:
        logger.error(f"Error in scan session {session_id}: {e}")
        session["status"] = "failed"
        session["error"] = str(e) 