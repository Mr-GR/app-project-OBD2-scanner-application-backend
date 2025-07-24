# api/routers/scanner.py
import logging
import time
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Query
from api.utils.elm327 import ELM327Scanner
from api.utils.dtc import get_code_description, categorize_dtc, get_dtc_severity
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
    BluetoothPairRequest,
    BluetoothPairResponse,
    LiveDataRequest,
    LiveDataResponse,
    DTCRequest,
    DTCCode,
    DTCListResponse,
    VehicleHealthResponse,
    ScannerStatusFlutterResponse,
    FullDiagnosticScanRequest,
    FullDiagnosticScanResponse,
    UploadFullScanRequest,
    UploadFullScanResponse,
    TroubleCodeInfo,
    ReadinessMonitor,
    LiveParameter,
    VehicleInformation,
    FreezeFrameData,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Global scanner instance
scanner = ELM327Scanner()
scan_sessions: Dict[str, Dict[str, Any]] = {}

# Live data storage (in-memory cache)
live_data_cache: Dict[str, Any] = {
    "rpm": None,
    "speed": None,
    "engine_temp": None,
    "fuel_level": None,
    "throttle_position": None,
    "vin": None,
    "timestamp": None
}


@router.get("/scanner/ports")
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
        
        # Set fast mode if requested
        if request.fast_mode:
            scanner._fast_mode = True
        
        # Connect to scanner
        connected = scanner.connect(request.port)
        
        if connected:
            # Determine connection type
            connection_type = "bluetooth" if scanner._is_bluetooth_port(scanner.port) else "usb"
            
            return ScannerConnectResponse(
                connected=True,
                port=scanner.port,
                connection_type=connection_type,
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

@router.get("/scanner/status", response_model=ScannerStatusFlutterResponse)
async def get_scanner_status():
    """Get scanner status formatted for Flutter app"""
    try:
        battery_voltage = None
        device_name = None
        
        # Try to get battery voltage if connected
        if scanner.connected:
            try:
                # Get battery voltage (PID 0142)
                voltage_data = scanner.get_sensor_data("0142")
                if voltage_data:
                    battery_voltage = voltage_data.value
                    
                # Get device name from port info
                if scanner.port:
                    device_name = scanner.port.split('/')[-1] if '/' in scanner.port else scanner.port
            except Exception:
                pass  # Ignore errors getting additional info
        
        return ScannerStatusFlutterResponse(
            connected=scanner.connected,
            device_name=device_name or "ELM327 OBD2",
            battery_voltage=battery_voltage
        )
    except Exception as e:
        logger.error(f"Error getting scanner status for Flutter: {e}")
        return ScannerStatusFlutterResponse(
            connected=False,
            device_name=None,
            battery_voltage=None
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
        
        # Enhanced DTC information
        enhanced_dtcs = []
        for code in codes:
            enhanced_dtcs.append({
                "code": code,
                "description": get_code_description(code),
                "category": categorize_dtc(code),
                "severity": get_dtc_severity(code)
            })
        
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

@router.post("/scanner/bluetooth/pair", response_model=BluetoothPairResponse)
async def pair_bluetooth_device(request: BluetoothPairRequest):
    """Pair with a Bluetooth OBD2 device"""
    try:
        success = scanner.pair_bluetooth_device(request.device_name, request.pin)
        
        if success:
            # Try to find the paired port
            ports = scanner.list_available_ports()
            paired_port = None
            for port in ports:
                if (port.get("connection_type") == "bluetooth" and 
                    request.device_name.lower() in port.get("description", "").lower()):
                    paired_port = port["port"]
                    break
            
            return BluetoothPairResponse(
                success=True,
                device_name=request.device_name,
                message="Successfully paired with Bluetooth device",
                paired_port=paired_port
            )
        else:
            return BluetoothPairResponse(
                success=False,
                device_name=request.device_name,
                message="Failed to pair with Bluetooth device. Manual pairing may be required."
            )
            
    except Exception as e:
        logger.error(f"Error pairing Bluetooth device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bluetooth pairing failed: {str(e)}"
        )

@router.post("/scanner/test-connection")
async def test_connection(request: dict):
    """Test basic serial connection to a port"""
    try:
        import serial
        port = request.get("port", "/dev/cu.OBDII")
        
        logger.info(f"Testing connection to {port}")
        
        # Try to open the serial port
        try:
            test_conn = serial.Serial(
                port=port,
                baudrate=38400,
                timeout=5,
                write_timeout=5
            )
            
            if test_conn.is_open:
                # Try a simple AT command
                test_conn.write(b"ATZ\r")
                response = test_conn.read(100)
                test_conn.close()
                
                return {
                    "success": True,
                    "port": port,
                    "message": f"Connection successful",
                    "response": response.decode('utf-8', errors='ignore')
                }
            else:
                return {
                    "success": False,
                    "port": port,
                    "message": "Failed to open serial port"
                }
                
        except Exception as serial_error:
            return {
                "success": False,
                "port": port,
                "message": f"Serial connection error: {str(serial_error)}"
            }
            
    except Exception as e:
        logger.error(f"Test connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test failed: {str(e)}"
        )

@router.post("/scanner/debug-command")
async def debug_command(request: dict):
    """Debug serial command sending with detailed logging"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        command = request.get("command", "ATZ")
        
        # Debug the serial communication step by step
        debug_info = {
            "command_sent": command,
            "serial_port": scanner.port,
            "connected": scanner.connected,
            "serial_open": scanner.serial_conn.is_open if scanner.serial_conn else False,
        }
        
        try:
            # Clear buffers
            scanner.serial_conn.reset_input_buffer()
            scanner.serial_conn.reset_output_buffer()
            debug_info["buffers_cleared"] = True
            
            # Send command
            cmd = f"{command}\r".encode()
            bytes_written = scanner.serial_conn.write(cmd)
            scanner.serial_conn.flush()
            debug_info["bytes_written"] = bytes_written
            debug_info["command_bytes"] = repr(cmd)
            
            # Wait a moment
            time.sleep(0.5)
            
            # Check for data
            bytes_waiting = scanner.serial_conn.in_waiting
            debug_info["bytes_waiting"] = bytes_waiting
            
            # Try to read raw bytes
            if bytes_waiting > 0:
                raw_data = scanner.serial_conn.read(bytes_waiting)
                debug_info["raw_response"] = repr(raw_data)
                debug_info["decoded_response"] = raw_data.decode('utf-8', errors='ignore')
            else:
                debug_info["raw_response"] = "No data received"
                debug_info["decoded_response"] = ""
            
            # Try the normal command method
            normal_response = scanner._send_command(command)
            debug_info["normal_response"] = repr(normal_response)
            
        except Exception as serial_error:
            debug_info["serial_error"] = str(serial_error)
        
        return {
            "success": True,
            "debug_info": debug_info
        }
        
    except Exception as e:
        logger.error(f"Debug command error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug failed: {str(e)}"
        )

@router.post("/scanner/try-line-endings")
async def try_different_line_endings():
    """Try different line endings to communicate with ELM327"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        results = {}
        
        # Try different line endings that ELM327 clones might need
        endings = {
            "carriage_return": "\r",
            "newline": "\n", 
            "both": "\r\n",
            "just_command": ""
        }
        
        for ending_name, ending in endings.items():
            try:
                # Clear buffers
                scanner.serial_conn.reset_input_buffer()
                scanner.serial_conn.reset_output_buffer()
                
                # Send ATZ with this ending
                cmd = f"ATZ{ending}".encode()
                bytes_written = scanner.serial_conn.write(cmd)
                scanner.serial_conn.flush()
                
                # Wait and check for response
                time.sleep(1)
                bytes_waiting = scanner.serial_conn.in_waiting
                
                response = ""
                if bytes_waiting > 0:
                    raw_data = scanner.serial_conn.read(bytes_waiting)
                    response = raw_data.decode('utf-8', errors='ignore')
                
                results[ending_name] = {
                    "command_sent": repr(cmd),
                    "bytes_written": bytes_written,
                    "bytes_waiting": bytes_waiting,
                    "response": repr(response),
                    "success": bytes_waiting > 0 and len(response) > 0
                }
                
            except Exception as e:
                results[ending_name] = {
                    "error": str(e),
                    "success": False
                }
        
        # Find successful endings
        successful = [name for name, result in results.items() if result.get("success", False)]
        
        return {
            "results": results,
            "successful_endings": successful,
            "recommendation": f"Use {successful[0]} ending" if successful else "Try different baud rate or check hardware"
        }
        
    except Exception as e:
        logger.error(f"Line endings test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Line endings test failed: {str(e)}"
        )

@router.post("/scanner/simple-test")
async def simple_test():
    """Simple test that won't crash"""
    try:
        if not scanner.connected:
            return {
                "connected": False,
                "error": "Scanner not connected"
            }
        
        # Check basic serial connection properties
        result = {
            "connected": scanner.connected,
            "port": scanner.port,
            "serial_open": False,
            "serial_readable": False,
            "serial_writable": False
        }
        
        if scanner.serial_conn:
            result["serial_open"] = scanner.serial_conn.is_open
            result["serial_readable"] = scanner.serial_conn.readable()
            result["serial_writable"] = scanner.serial_conn.writable()
            result["baudrate"] = scanner.serial_conn.baudrate
            result["timeout"] = scanner.serial_conn.timeout
        
        return result
        
    except Exception as e:
        return {
            "error": f"Simple test failed: {str(e)}",
            "connected": False
        }

@router.post("/scanner/test-ecu")
async def test_ecu_connection():
    """Test ECU connection and protocol detection"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        # Try different protocols and commands with error handling
        test_results = {}
        
        try:
            # Test basic connection
            test_results["atz_reset"] = scanner._send_command("ATZ")
        except Exception as e:
            test_results["atz_reset"] = f"Error: {str(e)}"
        
        try:
            test_results["ate0_echo"] = scanner._send_command("ATE0") 
        except Exception as e:
            test_results["ate0_echo"] = f"Error: {str(e)}"
        
        try:
            test_results["atsp0_auto"] = scanner._send_command("ATSP0")
        except Exception as e:
            test_results["atsp0_auto"] = f"Error: {str(e)}"
        
        try:
            # Test protocol detection
            test_results["protocol_query"] = scanner._send_command("ATDP")
        except Exception as e:
            test_results["protocol_query"] = f"Error: {str(e)}"
        
        try:
            # Test supported PIDs
            test_results["supported_pids"] = scanner._send_command("0100")
        except Exception as e:
            test_results["supported_pids"] = f"Error: {str(e)}"
        
        try:
            # Test simple sensor
            test_results["engine_rpm"] = scanner._send_command("010C")
        except Exception as e:
            test_results["engine_rpm"] = f"Error: {str(e)}"
        
        # Better ECU connection detection
        supported_pids = test_results.get("supported_pids", "")
        engine_rpm = test_results.get("engine_rpm", "")
        atz_reset = test_results.get("atz_reset", "")
        
        # ECU is connected if we get actual hex data (not empty or error responses)
        ecu_connected = (
            supported_pids and 
            supported_pids != "" and 
            "NO DATA" not in supported_pids and
            "ERROR" not in supported_pids and
            "?" not in supported_pids and
            len(supported_pids) > 5  # Should have actual hex data
        )
        
        # Also check if we get ANY response from ELM327 scanner itself
        elm_responding = (
            atz_reset and 
            atz_reset != "" and
            "Error:" not in atz_reset and
            len(atz_reset) > 0
        )
        
        return {
            "scanner_connected": True,
            "ecu_connected": ecu_connected,
            "elm_responding": elm_responding,
            "test_results": test_results,
            "debug_info": {
                "supported_pids_length": len(supported_pids),
                "supported_pids_content": repr(supported_pids),
                "engine_rpm_content": repr(engine_rpm),
                "atz_content": repr(atz_reset),
                "issue": "ELM327 not responding at all" if not elm_responding else ("ECU responding normally" if ecu_connected else "ELM327 responds but no ECU data"),
                "recommendation": "Try different line endings or baud rates" if not elm_responding else "Check car ignition and OBD2 connection"
            }
        }
        
    except Exception as e:
        logger.error(f"ECU test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ECU test failed: {str(e)}"
        )

@router.post("/scanner/protocol-scan")
async def scan_protocols():
    """Try all OBD2 protocols to find the right one"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        protocols = {
            "0": "Auto",
            "1": "SAE J1850 PWM (41.6 kbaud)",
            "2": "SAE J1850 VPW (10.4 kbaud)",
            "3": "ISO 9141-2 (5 baud init)",
            "4": "ISO 14230-4 KWP (5 baud init)",
            "5": "ISO 14230-4 KWP (fast init)",
            "6": "ISO 15765-4 CAN (11 bit ID, 500 kbaud)",
            "7": "ISO 15765-4 CAN (29 bit ID, 500 kbaud)",
            "8": "ISO 15765-4 CAN (11 bit ID, 250 kbaud)",
            "9": "ISO 15765-4 CAN (29 bit ID, 250 kbaud)",
            "A": "SAE J1939 CAN (29 bit ID, 250 kbaud)"
        }
        
        results = {}
        
        for protocol_num, protocol_name in protocols.items():
            try:
                # Set protocol
                set_response = scanner._send_command(f"ATSP{protocol_num}")
                
                # Test with supported PIDs
                test_response = scanner._send_command("0100")
                
                # Check if we got valid data
                valid = ("41 00" in test_response and "NO DATA" not in test_response and 
                        "ERROR" not in test_response and "?" not in test_response)
                
                results[protocol_num] = {
                    "name": protocol_name,
                    "set_response": set_response,
                    "test_response": test_response,
                    "working": valid
                }
                
                if valid:
                    logger.info(f"Protocol {protocol_num} ({protocol_name}) is working!")
                    break  # Found working protocol
                    
            except Exception as e:
                results[protocol_num] = {
                    "name": protocol_name,
                    "error": str(e),
                    "working": False
                }
        
        # Find working protocols
        working_protocols = [p for p, data in results.items() if data.get("working", False)]
        
        return {
            "working_protocols": working_protocols,
            "all_results": results,
            "recommendation": "Try starting the engine if no protocols work" if not working_protocols else f"Use protocol {working_protocols[0]}"
        }
        
    except Exception as e:
        logger.error(f"Protocol scan error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Protocol scan failed: {str(e)}"
        )

@router.get("/scanner/dtc/enhanced")
async def get_enhanced_dtc_analysis():
    """Get enhanced DTC analysis with categorization and severity"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        codes = scanner.get_dtc_codes()
        
        # Enhanced DTC analysis
        enhanced_analysis = {
            "total_codes": len(codes),
            "codes": [],
            "summary": {
                "critical": 0,
                "moderate": 0,
                "low": 0,
                "by_category": {}
            }
        }
        
        for code in codes:
            description = get_code_description(code)
            category = categorize_dtc(code)
            severity = get_dtc_severity(code)
            
            dtc_info = {
                "code": code,
                "description": description,
                "category": category,
                "severity": severity,
                "recommendations": _get_dtc_recommendations(code, severity)
            }
            
            enhanced_analysis["codes"].append(dtc_info)
            
            # Update summary
            enhanced_analysis["summary"][severity.lower()] += 1
            
            if category not in enhanced_analysis["summary"]["by_category"]:
                enhanced_analysis["summary"]["by_category"][category] = 0
            enhanced_analysis["summary"]["by_category"][category] += 1
        
        return {
            "timestamp": datetime.now(),
            "analysis": enhanced_analysis,
            "success": True,
            "message": f"Enhanced analysis of {len(codes)} DTC codes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced DTC analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get enhanced DTC analysis: {str(e)}"
        )

def _get_dtc_recommendations(code: str, severity: str) -> List[str]:
    """Get recommendations based on DTC code and severity"""
    recommendations = []
    
    if severity == "Critical":
        recommendations.append("Stop driving immediately and seek professional diagnosis")
        recommendations.append("Do not operate vehicle until issue is resolved")
    
    if code.startswith("P030"):  # Misfire codes
        recommendations.extend([
            "Check spark plugs and ignition coils",
            "Inspect fuel injectors",
            "Verify compression in affected cylinder(s)"
        ])
    elif code in ["P0171", "P0174"]:  # Lean codes
        recommendations.extend([
            "Check for vacuum leaks",
            "Inspect MAF sensor",
            "Check fuel pressure"
        ])
    elif code in ["P0420", "P0430"]:  # Catalyst codes
        recommendations.extend([
            "Check oxygen sensors",
            "Inspect catalytic converter",
            "May require catalyst replacement"
        ])
    elif code.startswith("U0"):  # Communication codes
        recommendations.extend([
            "Check CAN bus wiring",
            "Inspect module connections",
            "May require module programming"
        ])
    else:
        recommendations.append("Consult professional technician for diagnosis")
    
    if severity in ["Moderate", "Low"]:
        recommendations.append("Safe to drive, but schedule service soon")
    
    return recommendations

# ═══════════════════════════════════════════════════════════════════════════════
# Flutter App Specific Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/scanner/live-data")
async def receive_live_data(request: LiveDataRequest):
    """Receive live data from Flutter app and store in cache"""
    try:
        # Update cache with provided data
        if request.rpm is not None:
            live_data_cache["rpm"] = request.rpm
        if request.speed is not None:
            live_data_cache["speed"] = request.speed
        if request.engine_temp is not None:
            live_data_cache["engine_temp"] = request.engine_temp
        if request.fuel_level is not None:
            live_data_cache["fuel_level"] = request.fuel_level
        if request.throttle_position is not None:
            live_data_cache["throttle_position"] = request.throttle_position
        if request.vin is not None:
            live_data_cache["vin"] = request.vin
            logger.info(f"VIN received and cached: {request.vin}")
        
        live_data_cache["timestamp"] = request.timestamp or datetime.now()
        
        return {"message": "Live data received successfully", "timestamp": live_data_cache["timestamp"]}
    
    except Exception as e:
        logger.error(f"Error receiving live data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to receive live data: {str(e)}"
        )

@router.get("/scanner/live-data", response_model=LiveDataResponse)
async def get_live_data():
    """Get live data for Flutter app"""
    try:
        return LiveDataResponse(
            rpm=live_data_cache.get("rpm"),
            speed=live_data_cache.get("speed"),
            engine_temp=live_data_cache.get("engine_temp"),
            fuel_level=live_data_cache.get("fuel_level"),
            throttle_position=live_data_cache.get("throttle_position"),
            vin=live_data_cache.get("vin"),
            timestamp=live_data_cache.get("timestamp")
        )
    except Exception as e:
        logger.error(f"Error getting live data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get live data: {str(e)}"
        )

@router.get("/scanner/dtc/scan", response_model=DTCListResponse)
async def scan_dtc_codes():
    """Scan for DTC codes formatted for Flutter app"""
    try:
        if not scanner.connected:
            return DTCListResponse(
                active_codes=[],
                pending_codes=[]
            )
        
        # Get active codes
        active_codes = scanner.get_dtc_codes()
        active_dtc_list = []
        
        for code in active_codes:
            description = get_code_description(code)
            active_dtc_list.append(DTCCode(code=code, description=description))
        
        # For now, return empty pending codes - would need scanner implementation
        pending_dtc_list = []
        
        return DTCListResponse(
            active_codes=active_dtc_list,
            pending_codes=pending_dtc_list
        )
        
    except Exception as e:
        logger.error(f"Error scanning DTC codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan DTC codes: {str(e)}"
        )

@router.post("/scanner/dtc/clear")
async def clear_dtc_codes(request: DTCRequest):
    """Clear DTC codes"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        if request.clear_codes:
            # Send clear codes command
            response = scanner._send_command("04")  # Clear DTC codes command
            
            return {
                "message": "DTC codes cleared successfully",
                "response": response,
                "timestamp": datetime.now()
            }
        else:
            return {
                "message": "Clear codes not requested",
                "timestamp": datetime.now()
            }
            
    except Exception as e:
        logger.error(f"Error clearing DTC codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear DTC codes: {str(e)}"
        )

@router.get("/scanner/health-check", response_model=VehicleHealthResponse)
async def get_vehicle_health_check():
    """Get vehicle health check status using real OBD2 scanner data"""
    try:
        health_status = VehicleHealthResponse()
        
        if not scanner.connected:
            logger.warning("Scanner not connected - returning unknown health status")
            return health_status
        
        try:
            # Get DTC codes to assess health
            dtc_codes = scanner.get_dtc_codes()
            logger.info(f"Found {len(dtc_codes)} DTC codes for health analysis: {dtc_codes}")
            
            # Initialize all systems as good only if no DTC codes
            if not dtc_codes:
                health_status.engine = "good"
                health_status.transmission = "good"
                health_status.emissions = "good"
                health_status.fuel_system = "good"
                health_status.cooling_system = "good"
                health_status.electrical_system = "good"
                health_status.brake_system = "good"
                health_status.exhaust_system = "good"
            else:
                # Start with warning status if we have ANY DTC codes
                health_status.engine = "warning"
                health_status.transmission = "warning"
                health_status.emissions = "warning"
                health_status.fuel_system = "warning"
                health_status.cooling_system = "warning"
                health_status.electrical_system = "warning"
                health_status.brake_system = "warning"
                health_status.exhaust_system = "warning"
            
            # Check DTC codes and update system status based on actual codes
            for code in dtc_codes:
                severity = get_dtc_severity(code)
                status_level = "critical" if severity == "Critical" else "warning"
                
                logger.info(f"Processing DTC {code} with severity {severity} -> {status_level}")
                
                # Categorize by code prefix - be more specific about system affected
                if code.startswith("P00") or code.startswith("P01"):  # Fuel/Air system
                    health_status.fuel_system = status_level
                elif code.startswith("P02"):  # Fuel system
                    health_status.fuel_system = status_level
                elif code.startswith("P03"):  # Ignition system / Misfires
                    health_status.engine = status_level
                elif code.startswith("P04"):  # Emission control / Catalytic converter
                    health_status.emissions = status_level
                    health_status.exhaust_system = status_level
                elif code.startswith("P05"):  # Speed control / Idle
                    health_status.engine = status_level
                elif code.startswith("P06"):  # PCM/ECM
                    health_status.electrical_system = status_level
                elif code.startswith("P07") or code.startswith("P08") or code.startswith("P09"):  # Transmission
                    health_status.transmission = status_level
                elif code.startswith("P0A"):  # Hybrid system
                    health_status.electrical_system = status_level
                elif code.startswith("B"):  # Body systems
                    health_status.electrical_system = status_level
                elif code.startswith("C"):  # Chassis (ABS, etc.)
                    health_status.brake_system = status_level
                elif code.startswith("U"):  # Network/Communication
                    health_status.electrical_system = status_level
                    
            # Check cooling system with engine temp
            try:
                temp_data = scanner.get_sensor_data("0105")  # Engine coolant temp
                if temp_data and temp_data.value:
                    logger.info(f"Engine coolant temp: {temp_data.value}°C")
                    if temp_data.value > 110:  # Over 110°C - critical
                        health_status.cooling_system = "critical"
                    elif temp_data.value > 100:  # Over 100°C - warning
                        health_status.cooling_system = "warning"
                    else:
                        # Only mark as good if no DTC codes and temp is normal
                        if not dtc_codes:
                            health_status.cooling_system = "good"
                else:
                    logger.warning("Could not read engine coolant temperature")
            except Exception as temp_error:
                logger.warning(f"Error reading engine temperature: {temp_error}")
                
        except Exception as e:
            logger.error(f"Error getting detailed health check: {e}")
            # Return warning status if we can't get detailed check
            health_status.engine = "warning"
            health_status.transmission = "warning"
            health_status.emissions = "warning"
            health_status.fuel_system = "warning"
            health_status.cooling_system = "warning"
            health_status.electrical_system = "warning"
            health_status.brake_system = "warning"
            health_status.exhaust_system = "warning"
            
        logger.info(f"Final health status: {health_status.dict()}")
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting vehicle health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vehicle health check: {str(e)}"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# Full Diagnostic Scan Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/scanner/full-diagnostic-scan", response_model=FullDiagnosticScanResponse)
async def perform_full_diagnostic_scan(request: FullDiagnosticScanRequest):
    """Perform comprehensive diagnostic scan with all features"""
    try:
        if not scanner.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scanner not connected"
            )
        
        import uuid
        import time as time_module
        
        scan_start_time = time_module.time()
        scan_id = str(uuid.uuid4())
        
        logger.info(f"Starting {request.scan_type} diagnostic scan {scan_id}")
        
        # Initialize response
        response = FullDiagnosticScanResponse(
            scan_id=scan_id,
            scan_type=request.scan_type,
            timestamp=datetime.now(),
            status="partial"
        )
        
        error_messages = []
        
        # 1. Get VIN if requested
        if request.include_vin:
            try:
                vin = scanner.get_vin_from_obd2()
                if vin:
                    response.vehicle_info = VehicleInformation(vin=vin)
                    logger.info(f"Retrieved VIN: {vin}")
                else:
                    error_messages.append("Could not retrieve VIN via OBD2")
            except Exception as e:
                error_messages.append(f"VIN retrieval failed: {str(e)}")
        
        # 2. Get all types of trouble codes
        try:
            # Active codes
            active_codes = scanner.get_dtc_codes()
            response.active_codes_count = len(active_codes)
            
            # Pending codes
            pending_codes = scanner.get_pending_dtc_codes()
            response.pending_codes_count = len(pending_codes)
            
            # Permanent codes
            permanent_codes = scanner.get_permanent_dtc_codes()
            response.permanent_codes_count = len(permanent_codes)
            
            # Process all codes
            all_codes = []
            for code in active_codes:
                all_codes.append(TroubleCodeInfo(
                    code=code,
                    description=get_code_description(code),
                    system=categorize_dtc(code),
                    severity=get_dtc_severity(code),
                    status="Active"
                ))
            
            for code in pending_codes:
                if code not in active_codes:  # Avoid duplicates
                    all_codes.append(TroubleCodeInfo(
                        code=code,
                        description=get_code_description(code),
                        system=categorize_dtc(code),
                        severity=get_dtc_severity(code),
                        status="Pending"
                    ))
            
            for code in permanent_codes:
                if code not in active_codes and code not in pending_codes:  # Avoid duplicates
                    all_codes.append(TroubleCodeInfo(
                        code=code,
                        description=get_code_description(code),
                        system=categorize_dtc(code),
                        severity=get_dtc_severity(code),
                        status="Permanent"
                    ))
            
            response.trouble_codes = all_codes
            logger.info(f"Found {len(all_codes)} total trouble codes")
            
        except Exception as e:
            error_messages.append(f"Trouble code retrieval failed: {str(e)}")
        
        # 3. Get readiness monitors
        try:
            monitors_data = scanner.get_readiness_monitors()
            readiness_monitors = []
            ready_count = 0
            not_ready_count = 0
            
            for monitor_name, status in monitors_data.items():
                if monitor_name not in ["MIL", "DTC_Count"]:  # Skip non-monitor fields
                    readiness_monitors.append(ReadinessMonitor(
                        monitor_name=monitor_name,
                        status=status
                    ))
                    if status == "Ready":
                        ready_count += 1
                    elif status == "Not Ready":
                        not_ready_count += 1
            
            response.readiness_monitors = readiness_monitors
            response.monitors_ready = ready_count
            response.monitors_not_ready = not_ready_count
            logger.info(f"Readiness monitors: {ready_count} ready, {not_ready_count} not ready")
            
        except Exception as e:
            error_messages.append(f"Readiness monitor check failed: {str(e)}")
        
        # 4. Get live parameters if requested
        if request.include_live_parameters:
            try:
                live_params = scanner.get_live_parameters(request.scan_type)
                live_parameters = []
                
                for param_name, param_data in live_params.items():
                    live_parameters.append(LiveParameter(
                        name=param_name,
                        value=param_data["value"],
                        unit=param_data["unit"]
                    ))
                
                response.live_parameters = live_parameters
                logger.info(f"Retrieved {len(live_parameters)} live parameters")
                
            except Exception as e:
                error_messages.append(f"Live parameters retrieval failed: {str(e)}")
        
        # 5. Get freeze frame data if requested
        if request.include_freeze_frame and response.trouble_codes:
            try:
                freeze_frames = []
                for trouble_code in response.trouble_codes[:3]:  # Limit to first 3 codes
                    frame_data = scanner.get_freeze_frame_data(trouble_code.code)
                    for frame in frame_data:
                        freeze_frames.append(FreezeFrameData(
                            dtc_code=frame["dtc_code"],
                            frame_data={"raw_data": frame["data"]}
                        ))
                
                response.freeze_frames = freeze_frames
                logger.info(f"Retrieved {len(freeze_frames)} freeze frames")
                
            except Exception as e:
                error_messages.append(f"Freeze frame retrieval failed: {str(e)}")
        
        # 6. Determine overall health
        if response.trouble_codes:
            critical_codes = [tc for tc in response.trouble_codes if tc.severity == "Critical"]
            if critical_codes:
                response.overall_health = "critical"
            else:
                response.overall_health = "warning"
        else:
            response.overall_health = "good"
        
        # 7. Finalize response
        scan_duration = time_module.time() - scan_start_time
        response.scan_duration = round(scan_duration, 2)
        response.error_messages = error_messages
        
        if error_messages:
            response.status = "partial"
            logger.warning(f"Scan completed with errors: {error_messages}")
        else:
            response.status = "completed"
            logger.info(f"Scan completed successfully in {scan_duration:.2f}s")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing full diagnostic scan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full diagnostic scan failed: {str(e)}"
        )

@router.post("/scanner/upload-scan", response_model=UploadFullScanResponse)
async def upload_full_scan(scan_data: UploadFullScanRequest):
    """Upload full scan data from Flutter app to database"""
    try:
        from db.database import get_db
        from db.models import ScanSession, ScanTroubleCode, ScanLiveParameter, ScanReadinessMonitor
        from sqlalchemy.orm import Session
        
        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            # Validate vehicle_id exists or use None
            from db.models import UserVehicle
            if scan_data.vehicle_id:
                existing_vehicle = db.query(UserVehicle).filter(UserVehicle.id == scan_data.vehicle_id).first()
                if not existing_vehicle:
                    # Use the first available vehicle or None
                    first_vehicle = db.query(UserVehicle).first()
                    vehicle_id = first_vehicle.id if first_vehicle else None
                    logger.warning(f"Vehicle ID {scan_data.vehicle_id} not found, using {vehicle_id}")
                else:
                    vehicle_id = scan_data.vehicle_id
            else:
                vehicle_id = None
            
            # Create main scan session
            scan_session = ScanSession(
                vehicle_id=vehicle_id,
                scan_type=scan_data.scan_type,
                vehicle_info=scan_data.vehicle_info,
                started_at=scan_data.started_at or datetime.now(),
                completed_at=scan_data.completed_at or datetime.now()
            )
            db.add(scan_session)
            db.flush()  # Get the ID
            
            # Add trouble codes
            for code_data in scan_data.trouble_codes:
                trouble_code = ScanTroubleCode(
                    session_id=scan_session.id,
                    code=code_data.code,
                    description=code_data.description,
                    system=code_data.system,
                    code_type=code_data.type,
                    severity=get_dtc_severity(code_data.code)
                )
                db.add(trouble_code)
            
            # Add live parameters
            for param_name, param_value in scan_data.live_parameters.items():
                live_param = ScanLiveParameter(
                    session_id=scan_session.id,
                    parameter_name=param_name,
                    parameter_value=param_value
                )
                db.add(live_param)
            
            # Add readiness monitors
            for monitor_name, status in scan_data.readiness_monitors.items():
                readiness = ScanReadinessMonitor(
                    session_id=scan_session.id,
                    monitor_name=monitor_name,
                    status=status
                )
                db.add(readiness)
            
            db.commit()
            
            logger.info(f"Uploaded scan data for vehicle {scan_data.vehicle_id}, session {scan_session.id}")
            
            return UploadFullScanResponse(
                success=True,
                scan_id=scan_session.id,
                message="Full scan data uploaded successfully"
            )
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error uploading scan data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload scan data: {str(e)}"
        )

@router.get("/scanner/vehicles")
async def get_available_vehicles():
    """Get available vehicles for scan association"""
    try:
        from db.database import get_db
        from db.models import UserVehicle
        from sqlalchemy.orm import Session
        
        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            vehicles = db.query(UserVehicle).limit(10).all()
            vehicle_list = []
            
            for vehicle in vehicles:
                vehicle_list.append({
                    "id": vehicle.id,
                    "make": vehicle.make,
                    "model": vehicle.model,
                    "year": vehicle.year,
                    "vin": vehicle.vin,
                    "is_primary": vehicle.is_primary
                })
            
            return {
                "vehicles": vehicle_list,
                "count": len(vehicle_list)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting vehicles: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get vehicles: {str(e)}"
        )

