# api/utils/elm327.py
import logging
import time
from typing import Optional, List, Dict, Any
import serial
import serial.tools.list_ports
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OBD2Data:
    """Data structure for OBD2 sensor readings"""
    pid: str
    value: float
    unit: str
    description: str

class ELM327Scanner:
    """ELM327 OBD2 Scanner communication handler"""
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 38400):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.connected = False
        
    def list_available_ports(self) -> List[Dict[str, str]]:
        """List available serial ports for OBD2 scanners"""
        ports = []
        for port in serial.tools.list_ports.comports():
            if "bluetooth" in port.description.lower() or "usb" in port.description.lower():
                ports.append({
                    "port": port.device,
                    "description": port.description,
                    "manufacturer": port.manufacturer or "Unknown"
                })
        return ports
    
    def connect(self, port: Optional[str] = None) -> bool:
        """Connect to ELM327 scanner"""
        try:
            if port:
                self.port = port
                
            if not self.port:
                available_ports = self.list_available_ports()
                if available_ports:
                    self.port = available_ports[0]["port"]
                else:
                    logger.error("No OBD2 scanner ports found")
                    return False
            
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                write_timeout=1
            )
            
            # Initialize ELM327
            self._send_command("ATZ")  # Reset
            self._send_command("ATE0")  # Echo off
            self._send_command("ATL0")  # Linefeeds off
            self._send_command("0100")  # Get supported PIDs
            
            self.connected = True
            logger.info(f"Connected to ELM327 scanner on {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to ELM327: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from ELM327 scanner"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.connected = False
        logger.info("Disconnected from ELM327 scanner")
    
    def _send_command(self, command: str) -> str:
        """Send command to ELM327 and get response"""
        if not self.connected or not self.serial_conn:
            raise ConnectionError("Not connected to ELM327 scanner")
        
        # Clear buffer
        self.serial_conn.reset_input_buffer()
        
        # Send command
        cmd = f"{command}\r".encode()
        self.serial_conn.write(cmd)
        
        # Read response
        response = ""
        timeout = 0
        while timeout < 10:  # 10 second timeout
            if self.serial_conn.in_waiting:
                line = self.serial_conn.readline().decode().strip()
                if line:
                    response += line + "\n"
                    if ">" in line:  # ELM327 prompt
                        break
            else:
                timeout += 0.1
                time.sleep(0.1)
        
        return response.strip()
    
    def get_dtc_codes(self) -> List[str]:
        """Get Diagnostic Trouble Codes"""
        try:
            response = self._send_command("03")  # Get DTCs
            codes = []
            
            # Parse response (format: 43 01 33 00 00 00)
            lines = response.split('\n')
            for line in lines:
                if line.startswith('43'):
                    # Extract DTC codes from response
                    data = line.split()[1:]  # Skip '43'
                    for i in range(0, len(data), 2):
                        if i + 1 < len(data):
                            code = self._parse_dtc(data[i], data[i+1])
                            if code:
                                codes.append(code)
            
            return codes
            
        except Exception as e:
            logger.error(f"Error getting DTC codes: {e}")
            return []
    
    def _parse_dtc(self, first_byte: str, second_byte: str) -> Optional[str]:
        """Parse DTC from two bytes"""
        try:
            # Convert hex to binary
            first = int(first_byte, 16)
            second = int(second_byte, 16)
            
            # Extract DTC type and code
            dtc_type = (first & 0xC0) >> 6
            code = ((first & 0x3F) << 8) | second
            
            # Map DTC type to prefix
            type_map = {0: "P", 1: "C", 2: "B", 3: "U"}
            prefix = type_map.get(dtc_type, "P")
            
            return f"{prefix}{code:04X}"
            
        except Exception as e:
            logger.error(f"Error parsing DTC: {e}")
            return None
    
    def get_sensor_data(self, pid: str) -> Optional[OBD2Data]:
        """Get sensor data for specific PID"""
        try:
            response = self._send_command(pid)
            
            # Parse response based on PID
            if response and not response.startswith("NO DATA"):
                value = self._parse_sensor_value(pid, response)
                if value is not None:
                    return OBD2Data(
                        pid=pid,
                        value=value,
                        unit=self._get_pid_unit(pid),
                        description=self._get_pid_description(pid)
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting sensor data for PID {pid}: {e}")
            return None
    
    def _parse_sensor_value(self, pid: str, response: str) -> Optional[float]:
        """Parse sensor value from response"""
        try:
            # Extract data bytes from response
            lines = response.split('\n')
            for line in lines:
                if line.startswith(pid[:2]):  # Match PID response
                    data = line.split()[1:]  # Skip PID
                    if len(data) >= 2:
                        # Convert hex to decimal
                        value = int(data[0] + data[1], 16)
                        
                        # Apply formula based on PID
                        return self._apply_pid_formula(pid, value)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing sensor value: {e}")
            return None
    
    def _apply_pid_formula(self, pid: str, raw_value: int) -> float:
        """Apply formula to convert raw value to actual reading"""
        formulas = {
            "0105": lambda x: x - 40,  # Engine coolant temperature (°C)
            "010C": lambda x: x / 4,   # Engine RPM
            "010D": lambda x: x,       # Vehicle speed (km/h)
            "010F": lambda x: x - 40,  # Intake air temperature (°C)
            "0111": lambda x: x / 100, # Throttle position (%)
        }
        
        formula = formulas.get(pid, lambda x: x)
        return formula(raw_value)
    
    def _get_pid_unit(self, pid: str) -> str:
        """Get unit for PID"""
        units = {
            "0105": "°C",
            "010C": "RPM",
            "010D": "km/h",
            "010F": "°C",
            "0111": "%",
        }
        return units.get(pid, "")
    
    def _get_pid_description(self, pid: str) -> str:
        """Get description for PID"""
        descriptions = {
            "0105": "Engine Coolant Temperature",
            "010C": "Engine RPM",
            "010D": "Vehicle Speed",
            "010F": "Intake Air Temperature",
            "0111": "Throttle Position",
        }
        return descriptions.get(pid, f"PID {pid}")
    
    def get_vehicle_info(self) -> Dict[str, Any]:
        """Get basic vehicle information"""
        try:
            info = {}
            
            # Get VIN
            vin_response = self._send_command("0902")
            if vin_response and not vin_response.startswith("NO DATA"):
                info["vin"] = self._parse_vin(vin_response)
            
            # Get calibration IDs
            cal_response = self._send_command("0904")
            if cal_response and not cal_response.startswith("NO DATA"):
                info["calibration_ids"] = self._parse_calibration_ids(cal_response)
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting vehicle info: {e}")
            return {}
    
    def _parse_vin(self, response: str) -> str:
        """Parse VIN from response"""
        try:
            # Extract VIN data from response
            lines = response.split('\n')
            for line in lines:
                if line.startswith('49'):
                    data = line.split()[1:]  # Skip '49'
                    vin_hex = ''.join(data)
                    # Convert hex to ASCII
                    vin = bytes.fromhex(vin_hex).decode('ascii')
                    return vin.strip()
            return ""
        except Exception as e:
            logger.error(f"Error parsing VIN: {e}")
            return ""
    
    def _parse_calibration_ids(self, response: str) -> List[str]:
        """Parse calibration IDs from response"""
        try:
            ids = []
            lines = response.split('\n')
            for line in lines:
                if line.startswith('49'):
                    data = line.split()[1:]
                    # Convert hex to ASCII
                    cal_id = bytes.fromhex(''.join(data)).decode('ascii')
                    ids.append(cal_id.strip())
            return ids
        except Exception as e:
            logger.error(f"Error parsing calibration IDs: {e}")
            return [] 