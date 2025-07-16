# api/utils/elm327.py
import logging
import time
import platform
import subprocess
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
            port_info = {
                "port": port.device,
                "description": port.description,
                "manufacturer": port.manufacturer or "Unknown",
                "connection_type": "unknown"
            }
            
            # Detect connection type
            desc_lower = port.description.lower()
            if ("bluetooth" in desc_lower or "bt" in desc_lower or "rfcomm" in desc_lower or 
                "obdii" in port.device.lower() or "obd" in port.device.lower()):
                port_info["connection_type"] = "bluetooth"
                port_info["is_obd2_compatible"] = str(self._is_obd2_bluetooth_device(port))
            elif "usb" in desc_lower or "serial" in desc_lower:
                port_info["connection_type"] = "usb"
                port_info["is_obd2_compatible"] = str(self._is_obd2_usb_device(port))
            else:
                port_info["is_obd2_compatible"] = "false"
            
            # Include all ports but mark OBD2 compatibility
            ports.append(port_info)
        
        # Add platform-specific Bluetooth scanning
        bluetooth_ports = self._scan_bluetooth_obd2_devices()
        ports.extend(bluetooth_ports)
        
        return ports
    
    def connect(self, port: Optional[str] = None) -> bool:
        """Connect to ELM327 scanner"""
        try:
            if port:
                self.port = port
                
            if not self.port:
                available_ports = self.list_available_ports()
                # Prefer OBD2-compatible ports
                obd2_ports = [p for p in available_ports if p.get("is_obd2_compatible", "false") == "true"]
                if obd2_ports:
                    self.port = obd2_ports[0]["port"]
                elif available_ports:
                    self.port = available_ports[0]["port"]
                else:
                    logger.error("No OBD2 scanner ports found")
                    return False
            
            # Check if this is a Bluetooth port
            is_bluetooth = self._is_bluetooth_port(self.port)
            
            # Set appropriate timeout for Bluetooth connections
            timeout = 3 if is_bluetooth else 1
            write_timeout = 3 if is_bluetooth else 1
            
            logger.info(f"Attempting to connect to {self.port} with baudrate {self.baudrate}")
            
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=timeout,
                write_timeout=write_timeout
            )
            
            logger.info(f"Serial connection established to {self.port}")
            
            # Set connected to True before initialization so commands work
            self.connected = True
            
            # Initialize ELM327 with Bluetooth-specific handling
            if is_bluetooth:
                # Check if fast_mode was passed (for production)
                fast_mode = getattr(self, '_fast_mode', False)
                self._initialize_bluetooth_connection(fast_mode)
            else:
                self._initialize_usb_connection()
            
            logger.info(f"Connected to ELM327 scanner on {self.port} ({'Bluetooth' if is_bluetooth else 'USB'})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to ELM327: {e}")
            self.connected = False
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
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
        
        logger.debug(f"Sending command: {command}")
        
        # Clear buffer
        self.serial_conn.reset_input_buffer()
        
        # Send command
        cmd = f"{command}\r".encode()
        self.serial_conn.write(cmd)
        self.serial_conn.flush()  # Ensure data is sent
        
        # Read response with improved timeout handling
        response = ""
        start_time = time.time()
        max_timeout = 10  # 10 second maximum timeout
        
        while (time.time() - start_time) < max_timeout:
            if self.serial_conn.in_waiting > 0:
                try:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response += line + "\n"
                        logger.debug(f"Received line: {repr(line)}")
                        if ">" in line:  # ELM327 prompt indicates end
                            break
                        if line.endswith(">"):  # Sometimes prompt is at end of data
                            break
                except Exception as read_error:
                    logger.warning(f"Error reading response: {read_error}")
                    break
            else:
                time.sleep(0.1)
        
        final_response = response.strip()
        logger.debug(f"Final response for {command}: {repr(final_response)}")
        return final_response
    
    def get_dtc_codes(self) -> List[str]:
        """Get Diagnostic Trouble Codes"""
        try:
            response = self._send_command("03")  # Get DTCs
            codes = []
            
            # Parse CAN format response like in the log
            lines = response.split('\n')
            for line in lines:
                # Look for CAN responses containing DTC data
                if "43" in line and len(line) > 10:  # Mode 3 response
                    # Handle CAN format: 7E8100E4306D1200013
                    # Extract the data portion after header
                    line_clean = line.strip()
                    
                    # Find the "43" (Mode 3 response) and extract data after it
                    mode3_pos = line_clean.find("43")
                    if mode3_pos >= 0:
                        # Extract data after "43"
                        dtc_data = line_clean[mode3_pos + 2:]
                        
                        # Parse DTC codes from the hex data
                        # DTCs are encoded as 2-byte pairs
                        for i in range(0, len(dtc_data) - 3, 4):
                            if i + 4 <= len(dtc_data):
                                try:
                                    first_byte = dtc_data[i:i+2]
                                    second_byte = dtc_data[i+2:i+4]
                                    
                                    # Skip if all zeros (no more DTCs)
                                    if first_byte == "00" and second_byte == "00":
                                        break
                                        
                                    code = self._parse_dtc(first_byte, second_byte)
                                    if code and code not in codes:
                                        codes.append(code)
                                except Exception as parse_error:
                                    logger.debug(f"Error parsing DTC bytes: {parse_error}")
                                    continue
            
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
            # Extract data bytes from response - handle CAN format
            lines = response.split('\n')
            for line in lines:
                # Handle CAN format like "7E8064100BFBEB993"
                if "41" in line:  # Response to Mode 01 request
                    # Find the PID in the response
                    if pid[2:4] in line:  # Look for PID (e.g., "05" for 0105)
                        # Extract the data portion after the PID
                        can_data = line.strip()
                        
                        # For CAN format: 7E8 06 41 05 XX (where XX is the data)
                        # Find position of PID and extract data after it
                        pid_pos = can_data.find("41" + pid[2:4])
                        if pid_pos >= 0:
                            data_start = pid_pos + 4  # Skip "41" + PID
                            if data_start + 2 <= len(can_data):
                                # Extract the data bytes
                                data_hex = can_data[data_start:data_start + 2]
                                value = int(data_hex, 16)
                                
                                # Apply formula based on PID
                                return self._apply_pid_formula(pid, value)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing sensor value: {e}")
            return None
    
    def _apply_pid_formula(self, pid: str, raw_value: int, data_bytes: List[int] = None) -> float:
        """Apply formula to convert raw value to actual reading"""
        # Enhanced formulas based on PyOBD implementation
        formulas = {
            "0105": lambda x: x - 40,      # Engine coolant temperature (°C)
            "010C": lambda x: ((x >> 8) * 256 + (x & 0xFF)) / 4,  # Engine RPM (2 bytes)
            "010D": lambda x: x,           # Vehicle speed (km/h)
            "010F": lambda x: x - 40,      # Intake air temperature (°C)
            "0111": lambda x: x * 100 / 255,  # Throttle position (%)
            "0104": lambda x: x * 100 / 255,  # Calculated engine load (%)
            "0106": lambda x: (x - 128) * 100 / 128,  # Short term fuel trim (%)
            "0107": lambda x: (x - 128) * 100 / 128,  # Long term fuel trim (%)
            "010B": lambda x: x,           # Intake manifold absolute pressure (kPa)
            "010E": lambda x: (x - 128) / 2,  # Timing advance (degrees)
            "010F": lambda x: x - 40,      # Intake air temperature (°C)
            "0110": lambda x: ((x >> 8) * 256 + (x & 0xFF)) / 100,  # MAF air flow rate (g/s)
            "0133": lambda x: x / 200,     # Absolute Barometric Pressure (kPa)
            "0142": lambda x: ((x >> 8) * 256 + (x & 0xFF)) / 1000,  # Control module voltage (V)
            "0143": lambda x: ((x >> 8) * 256 + (x & 0xFF)) * 100 / 255,  # Absolute load value (%)
            "0144": lambda x: ((x >> 8) * 256 + (x & 0xFF)) / 32768,  # Fuel/Air commanded ratio
            "0145": lambda x: x * 100 / 255,  # Relative throttle position (%)
            "0146": lambda x: x - 40,      # Ambient air temperature (°C)
            "0147": lambda x: x * 100 / 255,  # Absolute throttle position B (%)
            "0149": lambda x: x * 100 / 255,  # Accelerator pedal position D (%)
            "014A": lambda x: x * 100 / 255,  # Accelerator pedal position E (%)
            "015C": lambda x: x - 40,      # Engine oil temperature (°C)
        }
        
        formula = formulas.get(pid, lambda x: x)
        return formula(raw_value)
    
    def _get_pid_unit(self, pid: str) -> str:
        """Get unit for PID"""
        units = {
            "0104": "%",         # Calculated engine load
            "0105": "°C",        # Engine coolant temperature
            "0106": "%",         # Short term fuel trim
            "0107": "%",         # Long term fuel trim
            "010B": "kPa",       # Intake manifold absolute pressure
            "010C": "RPM",       # Engine RPM
            "010D": "km/h",      # Vehicle speed
            "010E": "degrees",   # Timing advance
            "010F": "°C",        # Intake air temperature
            "0110": "g/s",       # MAF air flow rate
            "0111": "%",         # Throttle position
            "0133": "kPa",       # Absolute Barometric Pressure
            "0142": "V",         # Control module voltage
            "0143": "%",         # Absolute load value
            "0144": "ratio",     # Fuel/Air commanded ratio
            "0145": "%",         # Relative throttle position
            "0146": "°C",        # Ambient air temperature
            "0147": "%",         # Absolute throttle position B
            "0149": "%",         # Accelerator pedal position D
            "014A": "%",         # Accelerator pedal position E
            "015C": "°C",        # Engine oil temperature
        }
        return units.get(pid, "")
    
    def _get_pid_description(self, pid: str) -> str:
        """Get description for PID"""
        descriptions = {
            "0104": "Calculated Engine Load",
            "0105": "Engine Coolant Temperature",
            "0106": "Short Term Fuel Trim Bank 1",
            "0107": "Long Term Fuel Trim Bank 1",
            "010B": "Intake Manifold Absolute Pressure",
            "010C": "Engine RPM",
            "010D": "Vehicle Speed",
            "010E": "Timing Advance",
            "010F": "Intake Air Temperature",
            "0110": "MAF Air Flow Rate",
            "0111": "Throttle Position",
            "0133": "Absolute Barometric Pressure",
            "0142": "Control Module Voltage",
            "0143": "Absolute Load Value",
            "0144": "Fuel/Air Commanded Equivalence Ratio",
            "0145": "Relative Throttle Position",
            "0146": "Ambient Air Temperature",
            "0147": "Absolute Throttle Position B",
            "0149": "Accelerator Pedal Position D",
            "014A": "Accelerator Pedal Position E",
            "015C": "Engine Oil Temperature",
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
    
    def _is_obd2_bluetooth_device(self, port) -> bool:
        """Check if Bluetooth device is likely an OBD2 scanner"""
        # Check description
        desc_lower = port.description.lower() if port.description else ""
        
        # Check device name/port
        port_lower = port.device.lower() if port.device else ""
        
        obd2_keywords = ["obd", "elm327", "elm", "obdii", "diagnostic", "scanner"]
        
        # Check both description and port name
        desc_match = any(keyword in desc_lower for keyword in obd2_keywords)
        port_match = any(keyword in port_lower for keyword in obd2_keywords)
        
        # Special case: if port is "/dev/cu.OBDII", it's definitely OBD2
        if "obdii" in port_lower or "obd2" in port_lower:
            return True
            
        return desc_match or port_match
    
    def _is_obd2_usb_device(self, port) -> bool:
        """Check if USB device is likely an OBD2 scanner"""
        desc_lower = port.description.lower()
        obd2_keywords = ["obd", "elm327", "elm", "obdii", "diagnostic", "scanner", "ch340", "ftdi"]
        return any(keyword in desc_lower for keyword in obd2_keywords)
    
    def _scan_bluetooth_obd2_devices(self) -> List[Dict[str, str]]:
        """Scan for paired Bluetooth OBD2 devices"""
        bluetooth_devices = []
        
        try:
            system = platform.system()
            
            if system == "Darwin":  # macOS
                bluetooth_devices = self._scan_bluetooth_macos()
            elif system == "Linux":
                bluetooth_devices = self._scan_bluetooth_linux()
            elif system == "Windows":
                bluetooth_devices = self._scan_bluetooth_windows()
            
        except Exception as e:
            logger.warning(f"Error scanning Bluetooth devices: {e}")
        
        return bluetooth_devices
    
    def _scan_bluetooth_macos(self) -> List[Dict[str, str]]:
        """Scan for Bluetooth devices on macOS"""
        devices = []
        try:
            # Use system_profiler to get Bluetooth info
            result = subprocess.run(
                ["system_profiler", "SPBluetoothDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                # Parse Bluetooth devices
                for item in data.get("SPBluetoothDataType", []):
                    for device_key, device_info in item.items():
                        if isinstance(device_info, dict):
                            name = device_info.get("device_name", "Unknown")
                            if self._is_likely_obd2_device(name):
                                devices.append({
                                    "port": f"/dev/tty.{name.replace(' ', '-')}",
                                    "description": f"Bluetooth OBD2 - {name}",
                                    "manufacturer": "Bluetooth",
                                    "connection_type": "bluetooth",
                                    "is_obd2_compatible": "true",
                                    "device_name": name
                                })
                                
        except Exception as e:
            logger.warning(f"Error scanning macOS Bluetooth: {e}")
        
        return devices
    
    def _scan_bluetooth_linux(self) -> List[Dict[str, str]]:
        """Scan for Bluetooth devices on Linux"""
        devices = []
        try:
            # Use bluetoothctl to scan for devices
            result = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Device'):
                        parts = line.split()
                        if len(parts) >= 3:
                            mac_address = parts[1]
                            device_name = ' '.join(parts[2:])
                            
                            if self._is_likely_obd2_device(device_name):
                                devices.append({
                                    "port": f"/dev/rfcomm0",  # Common Linux Bluetooth serial port
                                    "description": f"Bluetooth OBD2 - {device_name}",
                                    "manufacturer": "Bluetooth",
                                    "connection_type": "bluetooth",
                                    "is_obd2_compatible": "true",
                                    "device_name": device_name,
                                    "mac_address": mac_address
                                })
                                
        except Exception as e:
            logger.warning(f"Error scanning Linux Bluetooth: {e}")
        
        return devices
    
    def _scan_bluetooth_windows(self) -> List[Dict[str, str]]:
        """Scan for Bluetooth devices on Windows"""
        devices = []
        try:
            # Use PowerShell to get Bluetooth devices
            result = subprocess.run([
                "powershell",
                "-Command",
                "Get-PnpDevice | Where-Object {$_.Class -eq 'Bluetooth' -and $_.Status -eq 'OK'} | Select-Object FriendlyName, InstanceId"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:  # Skip header lines
                    if line.strip():
                        parts = line.split()
                        if parts:
                            device_name = ' '.join(parts[:-1])
                            if self._is_likely_obd2_device(device_name):
                                devices.append({
                                    "port": f"COM{len(devices) + 10}",  # Approximate COM port
                                    "description": f"Bluetooth OBD2 - {device_name}",
                                    "manufacturer": "Bluetooth",
                                    "connection_type": "bluetooth",
                                    "is_obd2_compatible": "true",
                                    "device_name": device_name
                                })
                                
        except Exception as e:
            logger.warning(f"Error scanning Windows Bluetooth: {e}")
        
        return devices
    
    def _is_likely_obd2_device(self, device_name: str) -> bool:
        """Check if device name suggests it's an OBD2 scanner"""
        name_lower = device_name.lower()
        obd2_keywords = [
            "obd", "elm327", "elm", "obdii", "diagnostic", "scanner",
            "torque", "car", "auto", "vehicle", "ecu", "canbus"
        ]
        return any(keyword in name_lower for keyword in obd2_keywords)
    
    def pair_bluetooth_device(self, device_name: str, pin: str = "1234") -> bool:
        """Pair with a Bluetooth OBD2 device"""
        try:
            system = platform.system()
            
            if system == "Darwin":  # macOS
                return self._pair_bluetooth_macos(device_name, pin)
            elif system == "Linux":
                return self._pair_bluetooth_linux(device_name, pin)
            elif system == "Windows":
                return self._pair_bluetooth_windows(device_name, pin)
            
            return False
            
        except Exception as e:
            logger.error(f"Error pairing Bluetooth device: {e}")
            return False
    
    def _pair_bluetooth_macos(self, device_name: str, pin: str) -> bool:
        """Pair Bluetooth device on macOS"""
        try:
            # macOS Bluetooth pairing typically requires user interaction
            logger.info(f"Bluetooth pairing on macOS requires manual pairing through System Preferences")
            return False
        except Exception as e:
            logger.error(f"macOS Bluetooth pairing error: {e}")
            return False
    
    def _pair_bluetooth_linux(self, device_name: str, pin: str) -> bool:
        """Pair Bluetooth device on Linux"""
        try:
            # Use bluetoothctl for pairing
            commands = [
                f"pair {device_name}",
                f"connect {device_name}"
            ]
            
            for cmd in commands:
                result = subprocess.run(
                    ["bluetoothctl", cmd],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    logger.error(f"Bluetooth command failed: {cmd}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Linux Bluetooth pairing error: {e}")
            return False
    
    def _pair_bluetooth_windows(self, device_name: str, pin: str) -> bool:
        """Pair Bluetooth device on Windows"""
        try:
            # Windows Bluetooth pairing typically requires user interaction
            logger.info(f"Bluetooth pairing on Windows requires manual pairing through Settings")
            return False
        except Exception as e:
            logger.error(f"Windows Bluetooth pairing error: {e}")
            return False
    
    def _is_bluetooth_port(self, port: str) -> bool:
        """Check if port is a Bluetooth serial port"""
        if not port:
            return False
        
        port_lower = port.lower()
        bluetooth_indicators = [
            "bluetooth", "bt", "rfcomm", "/dev/cu.bluetooth", 
            "/dev/tty.bluetooth", "com", "tty.", "obdii", "obd"
        ]
        
        return any(indicator in port_lower for indicator in bluetooth_indicators)
    
    def _initialize_bluetooth_connection(self, fast_mode: bool = False):
        """Initialize ELM327 connection over Bluetooth"""
        try:
            if fast_mode:
                self._fast_bluetooth_init()
            else:
                self._standard_bluetooth_init()
                
        except Exception as e:
            logger.error(f"Bluetooth initialization error: {e}")
            raise
    
    def _fast_bluetooth_init(self):
        """Fast production initialization for Bluetooth"""
        # Minimal delay and logging for production speed
        time.sleep(0.5)  # Reduced from 2 seconds
        
        self.serial_conn.reset_input_buffer()
        self.serial_conn.reset_output_buffer()
        
        # Essential commands only with minimal delays
        self._send_command_fast("ATZ")     # Reset
        time.sleep(1)  # Only wait after reset
        self._send_command_fast("ATE0")    # Echo off
        self._send_command_fast("ATH1")    # Headers on
        self._send_command_fast("ATSP0")   # Protocol auto
        self._send_command_fast("ATAT1")   # Adaptive timing
        self._send_command_fast("0100")    # Test connection
        
        logger.info("Fast Bluetooth ELM327 initialization complete")
    
    def _standard_bluetooth_init(self):
        """Standard initialization with full logging (development)"""
        logger.info("Starting Bluetooth ELM327 initialization")
        time.sleep(2)
        
        self.serial_conn.reset_input_buffer()
        self.serial_conn.reset_output_buffer()
        
        # Send initial commands following the successful pattern
        logger.info("Sending ATZ (reset)")
        reset_response = self._send_command_with_delay("ATZ", 3)
        logger.info(f"ATZ response: {repr(reset_response)}")
        
        logger.info("Sending ATE0 (echo off)")
        echo_response = self._send_command_with_delay("ATE0", 1)
        logger.info(f"ATE0 response: {repr(echo_response)}")
        
        # Follow the successful initialization pattern from the log
        logger.info("Sending ATH1 (headers on)")
        self._send_command_with_delay("ATH1", 1)
        
        logger.info("Sending ATSP0 (protocol auto)")
        self._send_command_with_delay("ATSP0", 1)
        
        logger.info("Sending ATS0 (spaces off)")
        self._send_command_with_delay("ATS0", 1)
        
        logger.info("Sending ATM0 (memory off)")
        self._send_command_with_delay("ATM0", 1)
        
        logger.info("Sending ATAT1 (adaptive timing on)")
        self._send_command_with_delay("ATAT1", 1)
        
        logger.info("Sending ATAL (allow long messages)")
        self._send_command_with_delay("ATAL", 1)
        
        logger.info("Sending ATST64 (timeout 4 seconds)")
        self._send_command_with_delay("ATST64", 1)
        
        # Test connection with supported PIDs
        logger.info("Testing with 0100 command")
        response = self._send_command_with_delay("0100", 3)
        logger.info(f"0100 response: {repr(response)}")
        
        if not response or "NO DATA" in response or "ERROR" in response:
            logger.warning("ELM327 initialization may have failed - check vehicle connection")
        else:
            logger.info("ELM327 initialization successful")
    
    def _send_command_fast(self, command: str) -> str:
        """Fast command sending for production (minimal logging)"""
        if not self.connected or not self.serial_conn:
            raise ConnectionError("Not connected to ELM327 scanner")
        
        self.serial_conn.reset_input_buffer()
        cmd = f"{command}\r".encode()
        self.serial_conn.write(cmd)
        self.serial_conn.flush()
        
        # Fast response reading with shorter timeout
        response = ""
        start_time = time.time()
        max_timeout = 3  # Reduced from 10 seconds
        
        while (time.time() - start_time) < max_timeout:
            if self.serial_conn.in_waiting > 0:
                try:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response += line + "\n"
                        if ">" in line or line.endswith(">"):
                            break
                except Exception:
                    break
            else:
                time.sleep(0.05)  # Shorter sleep intervals
        
        return response.strip()
    
    def _initialize_usb_connection(self):
        """Initialize ELM327 connection over USB"""
        try:
            # USB connections are faster
            time.sleep(0.5)
            
            # Standard initialization
            self._send_command("ATZ")  # Reset
            self._send_command("ATE0")  # Echo off
            self._send_command("ATL0")  # Linefeeds off
            self._send_command("0100")  # Get supported PIDs
            
        except Exception as e:
            logger.error(f"USB initialization error: {e}")
            raise
    
    def _send_command_with_delay(self, command: str, delay: float = 1.0) -> str:
        """Send command with specified delay (for Bluetooth connections)"""
        response = self._send_command(command)
        time.sleep(delay)
        return response 