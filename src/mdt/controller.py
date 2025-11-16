#!/usr/bin/env python
"""
MDT Controller Classes following the existing motor controller architecture

This module provides low-level and high-level control interfaces for MDT piezo devices,
following the same patterns as the existing motor controller system.
"""

import serial
import time
import json
import re
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

class MDTController:
    """
    Low-level MDT piezo controller class - direct serial communication
    
    Follows the same interface pattern as the existing motor controller.
    Handles the basic serial communication and command parsing.
    """
    
    def __init__(self, port: str, model: str = None, serial_no: str = None, 
                 baud_rate: int = 115200, timeout: float = 2.0):
        """
        Initialize MDT controller
        
        Args:
            port: COM port (e.g., "COM9")
            model: Device model (MDT693A/693B/694B)
            serial_no: Device serial number
            baud_rate: Communication baud rate
            timeout: Communication timeout
        """
        self.port = port
        self.model = model or "Unknown"
        self.serial_no = serial_no or ""
        self.baud_rate = baud_rate
        self.timeout = timeout
        
        self.connection = None
        self.is_connected = False
        
        # Device capabilities based on model
        if "694" in self.model:  # 1-channel
            self.axes = ["X"]
        else:  # 693A/693B - 3-channel
            self.axes = ["X", "Y", "Z"]
        
        # Voltage range (all models)
        self.voltage_min = 0.0
        # Enforce software maximum of 150.0V (device may report 150.50)
        self.voltage_max = 150.0
        
        # Protocol differences
        self.is_legacy_protocol = "693A" in self.model
        
    def connect(self) -> bool:
        """
        Connect to the MDT device
        
        Returns:
            bool: True if connection successful
        """
        if self.is_connected:
            return True
            
        try:
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            # Allow device to initialize
            time.sleep(0.5)
            self.connection.reset_input_buffer()
            self.connection.reset_output_buffer()
            
            # Test connection with ID command
            response = self.send_command("ID?")
            if response and "MDT" in response:
                self.is_connected = True
                
                # Set default voltage limits to 0V min and 150V max for all axes
                for axis in self.axes:
                    self.send_command(f"{axis}L0")  # Set lower limit to 0V
                    time.sleep(0.05)
                    self.send_command(f"{axis}H150")  # Set upper limit to 150V
                    time.sleep(0.05)
                
                # Disable echo mode on legacy devices (MDT693A)
                # They echo commands by default, preventing us from reading voltage values
                if self.is_legacy_protocol:
                    echo_status = self.send_command("ECHO?")
                    if echo_status and "1" in echo_status:
                        # Echo is ON, turn it OFF
                        self.send_command("ECHO=0")
                        time.sleep(0.2)
                        # Verify it's off
                        verify = self.send_command("ECHO?")
                        if verify and "0" in verify:
                            print(f"Echo mode disabled on {self.model}")
                
                return True
            else:
                self.disconnect()
                return False
                
        except Exception as e:
            print(f"MDT connection failed: {e}")
            return False
    
    
    def set_safe_max(self, safe_max: float):
        """Set custom safe maximum voltage for all axes
        
        Args:
            safe_max: New safe maximum voltage (must be <= device max)
        """
        if not self.controller:
            return
        
        for axis in self.controller.axes:
            device_max = self.voltage_limits[axis]['max']
            self.voltage_limits[axis]['safe_max'] = min(safe_max, device_max)
        
        print(f"Safe maximum set to {safe_max}V")
    
    def get_safe_max(self) -> float:
        """Get current safe maximum voltage
        
        Returns:
            float: Safe maximum voltage (returns first axis value)
        """
        if self.voltage_limits and self.controller.axes:
            return self.voltage_limits[self.controller.axes[0]]['safe_max']
        return 100.0
    def disconnect(self):
        """Disconnect from device"""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
        self.is_connected = False
    
    def send_command(self, command: str, timeout: float = None) -> Optional[str]:
        """
        Send command to device and return response
        
        Args:
            command: Command string to send
            timeout: Override default timeout
            
        Returns:
            str: Device response, or None if failed
        """
        if not self.connection:
            return None
            
        # Use longer timeout for legacy devices
        cmd_timeout = timeout if timeout is not None else (self.timeout * 2 if self.is_legacy_protocol else self.timeout)
        
        try:
            # Clear buffers
            self.connection.reset_input_buffer()
            
            # Send command with proper termination
            cmd_bytes = command.encode('ascii') + b'\r\n'
            self.connection.write(cmd_bytes)
            self.connection.flush()
            
            # Wait for response - longer for legacy devices
            pause_time = 0.15 if self.is_legacy_protocol else 0.05
            time.sleep(pause_time)  # Brief pause for device processing
            
            response = b""
            start_time = time.time()
            
            while time.time() - start_time < cmd_timeout:
                if self.connection.in_waiting > 0:
                    chunk = self.connection.read(self.connection.in_waiting)
                    response += chunk

                    # Check for common completion markers used by MDT devices
                    # legacy units sometimes use '*' as a terminator in our probes,
                    # and most responses include CR/LF. Stop early when we see any
                    # of these so we don't wait the full timeout unnecessarily.
                    if any(term in response for term in (b'>', b'!', b'*', b'\n', b'\r')):
                        break

                # Small sleep so loop isn't busy-waiting
                time.sleep(0.02)
            
            if response:
                decoded = response.decode('ascii', errors='ignore').strip()
                # Remove control characters
                cleaned = decoded.replace('\r', '').replace('\n', '').replace('>', '').replace('!', '')
                return cleaned.strip()
                
        except Exception as e:
            print(f"Command '{command}' failed: {e}")
            
        return None
    
    def get_device_info(self) -> Dict[str, str]:
        """
        Get device identification information
        
        Returns:
            dict: Device info including model, firmware, serial, etc.
        """
        info = {}
        
        # Get full device info
        id_response = self.send_command("ID?")
        if id_response:
            info["full_info"] = id_response
            
            # Parse model
            model_match = re.search(r'Model\s+(\w+)', id_response)
            if model_match:
                info["model"] = model_match.group(1)
            
            # Parse firmware version
            fw_match = re.search(r'Firmware Version:\s*([0-9.]+)', id_response)
            if fw_match:
                info["firmware"] = fw_match.group(1)
            
            # Parse voltage range
            voltage_match = re.search(r'Voltage Range:\s*([0-9V\s\w]+)', id_response)
            if voltage_match:
                info["voltage_range"] = voltage_match.group(1)
        
        # Get serial number
        serial_response = self.send_command("serial?")
        if serial_response and serial_response.strip():
            info["serial_number"] = serial_response.strip()
        
        return info
    
    def get_voltage(self, axis: str) -> Optional[float]:
        """
        Get voltage for specified axis using short-form query (XR?, YR?, ZR?)
        
        Args:
            axis: Axis name ("X", "Y", "Z")
            
        Returns:
            float: Current voltage in volts, or None if failed
        """
        if axis.upper() not in self.axes:
            return None
            
        # Use short-form read command: XR?, YR?, ZR?
        command = f"{axis.upper()}R?"
        response = self.send_command(command)
        
        if response:
            num = self._extract_number(response)
            if num is not None:
                return num
        
        # Fallback to long-form for compatibility
        command = f"{axis.upper()}VOLTAGE?"
        response = self.send_command(command)
        if response:
            return self._extract_number(response)
        
        return None
    
    def set_voltage(self, axis: str, voltage: float, verify: bool = True) -> bool:
        """
        Set voltage for specified axis using short-form command (XV1, ZV50, etc.)
        
        Args:
            axis: Axis name ("X", "Y", "Z")
            voltage: Target voltage in volts
            verify: Whether to verify by reading back (default True, ±1V tolerance)
            
        Returns:
            bool: True if successful
        """
        if axis.upper() not in self.axes:
            return False
            
        # Validate voltage range
        if not (self.voltage_min <= voltage <= self.voltage_max):
            print(f"Voltage {voltage}V out of range [{self.voltage_min}, {self.voltage_max}]")
            return False
        
        # Build short-form command: XV1 or XV1.25 (no space, no equals)
        if abs(voltage - round(voltage)) < 1e-9:
            value_str = f"{int(round(voltage))}"
        else:
            value_str = f"{voltage:.2f}"
        
        command = f"{axis.upper()}V{value_str}"
        response = self.send_command(command, timeout=3.0)
        
        if not verify:
            return True
        
        # Verification with ±1.0V tolerance
        tolerance = 1.0
        max_retries = 3
        
        # Check if device echoed command (common on MDT693A)
        if response:
            lowresp = response.lower()
            if lowresp.startswith(f"{axis.lower()}v"):
                # Device acknowledged with echo
                actual_voltage = self.get_voltage(axis)
                if actual_voltage is None:
                    # No numeric readback - accept echo as acknowledgement
                    return True
                elif abs(actual_voltage - voltage) <= tolerance:
                    return True
        
        # Try reading back with retries
        last_actual = None
        for attempt in range(max_retries):
            time.sleep(0.15)
            actual_voltage = self.get_voltage(axis)
            last_actual = actual_voltage
            
            if actual_voltage is not None:
                diff = abs(actual_voltage - voltage)
                if diff <= tolerance:
                    return True
                elif attempt < max_retries - 1:
                    print(f"Retry {attempt+1}: set={voltage:.2f}V, actual={actual_voltage:.2f}V, diff={diff:.2f}V")
        
        # Accept if within tolerance, otherwise warn
        if last_actual is not None:
            within_tolerance = abs(last_actual - voltage) <= tolerance
            if not within_tolerance:
                print(f"Warning: {axis}={voltage:.2f}V, readback={last_actual:.2f}V (diff={abs(last_actual-voltage):.2f}V)")
            return within_tolerance
        
        # No readback available - accept write
        return True
    
    def get_all_voltages(self) -> Dict[str, float]:
        """
        Get voltages for all axes
        
        Returns:
            dict: Mapping of axis name to voltage
        """
        voltages = {}
        
        # For 693B, try the combined command first
        if "693B" in self.model:
            response = self.send_command("XYZVOLTAGE?")
            if response:
                # Parse response like "[  0.24,  0.21,  0.22]"
                numbers = re.findall(r'[-+]?\d*\.?\d+', response)
                if len(numbers) >= 3:
                    voltages = {
                        "X": float(numbers[0]),
                        "Y": float(numbers[1]),
                        "Z": float(numbers[2])
                    }
                    return voltages
        
        # Fallback: query each axis individually
        for axis in self.axes:
            voltage = self.get_voltage(axis)
            if voltage is not None:
                voltages[axis] = voltage
                
        return voltages
    
    def set_all_voltages(self, voltages: Dict[str, float]) -> bool:
        """
        Set voltages for multiple axes
        
        Args:
            voltages: Dict mapping axis names to target voltages
            
        Returns:
            bool: True if all successful
        """
        success = True
        
        # For 693B with 3 axes, try combined command
        if "693B" in self.model and len(voltages) == 3:
            if all(axis in voltages for axis in ["X", "Y", "Z"]):
                x_val = voltages["X"]
                y_val = voltages["Y"] 
                z_val = voltages["Z"]
                
                command = f"XYZVOLTAGE=[{x_val:.2f},{y_val:.2f},{z_val:.2f}]"
                response = self.send_command(command, timeout=3.0)
                
                # Verify by reading back
                time.sleep(0.2)
                actual = self.get_all_voltages()
                
                tolerance = 0.5
                for axis, target in voltages.items():
                    if axis in actual:
                        if abs(actual[axis] - target) > tolerance:
                            success = False
                    else:
                        success = False
                        
                if success:
                    return True
        
        # Fallback: set each axis individually
        for axis, voltage in voltages.items():
            if not self.set_voltage(axis, voltage):
                success = False
                
        return success
    
    def get_voltage_limits(self, axis: str) -> Tuple[float, float]:
        """
        Get voltage limits for specified axis using short-form queries (XL?, XH?)
        
        Args:
            axis: Axis name ("X", "Y", "Z")
            
        Returns:
            tuple: (min_voltage, max_voltage)
        """
        if axis.upper() not in self.axes:
            return (0.0, 0.0)
        
        min_voltage = self.voltage_min
        max_voltage = self.voltage_max
        
        # Use short-form limit queries: XL?, XH?
        min_response = self.send_command(f"{axis.upper()}L?")
        if min_response:
            device_min = self._extract_number(min_response)
            if device_min is not None:
                min_voltage = device_min
        
        max_response = self.send_command(f"{axis.upper()}H?")
        if max_response:
            device_max = self._extract_number(max_response)
            if device_max is not None:
                max_voltage = device_max
        
        return (min_voltage, max_voltage)
    
    def _extract_number(self, response: str) -> Optional[float]:
        """
        Extract numeric value from device response
        
        Args:
            response: Raw device response
            
        Returns:
            float: Extracted number, or None if not found
        """
        if not response:
            return None
            
        # Find all numbers in the response
        numbers = re.findall(r'[-+]?\d*\.?\d+', response)
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                pass
        return None
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


class HighLevelMDTController:
    """
    High-level MDT controller with advanced features
    
    Provides user-friendly interface, safety checks, and advanced functionality
    following the same pattern as the existing high-level motor controller.
    """
    
    def __init__(self, port: str = None, model: str = None, auto_discover: bool = True):
        """
        Initialize high-level MDT controller
        
        Args:
            port: COM port, or None for auto-discovery
            model: Device model, or None for auto-detection
            auto_discover: Whether to auto-discover devices
        """
        self.controller = None
        self.device_info = {}
        self.safety_enabled = True
        self.voltage_limits = {}
        
        if auto_discover and not port:
            self._auto_discover()
        elif port:
            # If model not provided, look it up from device list
            if not model:
                devices = self._load_device_list()
                if port in devices:
                    model = devices[port].get("Model", "Unknown")
            self._initialize_device(port, model)
    
    def _auto_discover(self):
        """Auto-discover MDT devices"""
        try:
            devices = self._load_device_list()
            if devices:
                # Use first available device
                device_info = next(iter(devices.values()))
                port = device_info["Device"]
                model = device_info.get("Model", "Unknown")
                self._initialize_device(port, model)
        except Exception as e:
            print(f"Auto-discovery failed: {e}")
    
    def _load_device_list(self) -> Dict:
        """Load device list from JSON file"""
        try:
            with open("mdt_devices.json", "r") as f:
                devices = json.load(f)
            return {d["Device"]: d for d in devices if "MDT" in d.get("Model", "")}
        except:
            return {}
    
    def _initialize_device(self, port: str, model: str = None):
        """Initialize device connection"""
        self.controller = MDTController(port=port, model=model)
        
        if self.controller.connect():
            self.device_info = self.controller.get_device_info()
            self._initialize_safety_limits()
            print(f"✓ Connected to {self.controller.model} on {port}")
        else:
            print(f"✗ Failed to connect to {port}")
            self.controller = None
    
    def _initialize_safety_limits(self, custom_safe_max: float = None):
        """Initialize safety voltage limits
        
        Args:
            custom_safe_max: Override default safe maximum (default: 100V)
        """
        if not self.controller:
            return
        
        default_safe_max = custom_safe_max if custom_safe_max is not None else 100.0
            
        for axis in self.controller.axes:
            min_v, max_v = self.controller.get_voltage_limits(axis)
            self.voltage_limits[axis] = {
                "min": min_v,
                "max": max_v,
                "safe_max": min(max_v, default_safe_max)
            }
    
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return self.controller is not None and self.controller.is_connected
    
    def get_device_status(self) -> Dict:
        """Get comprehensive device status"""
        if not self.is_connected():
            return {"status": "disconnected"}
        
        status = {
            "status": "connected",
            "port": self.controller.port,
            "model": self.controller.model,
            "axes": self.controller.axes,
            "device_info": self.device_info,
            "voltage_limits": self.voltage_limits,
            "current_voltages": self.controller.get_all_voltages()
        }
        
        return status
    
    def set_voltage_safe(self, axis: str, voltage: float, force: bool = False) -> bool:
        """
        Set voltage with safety checks
        
        Args:
            axis: Target axis ("X", "Y", "Z")
            voltage: Target voltage
            force: Bypass safety limits
            
        Returns:
            bool: True if successful
        """
        if not self.is_connected():
            print("Device not connected")
            return False
        
        axis = axis.upper()
        if axis not in self.controller.axes:
            print(f"Invalid axis '{axis}' for this device")
            return False
        
        # Safety checks
        if self.safety_enabled and not force:
            limits = self.voltage_limits.get(axis, {})
            safe_max = limits.get("safe_max", 100.0)
            
            if voltage > safe_max:
                print(f"Voltage {voltage}V exceeds safe limit {safe_max}V")
                print("Use force=True to override safety limits")
                return False
        
        # Get current voltage for comparison
        current = self.controller.get_voltage(axis)
        if current is not None:
            print(f"Setting {axis}-axis: {current:.2f}V → {voltage:.2f}V")
        else:
            print(f"Setting {axis}-axis to {voltage:.2f}V")
        
        success = self.controller.set_voltage(axis, voltage)
        
        if success:
            # Verify final voltage
            final = self.controller.get_voltage(axis)
            print(f"✓ {axis}-axis set to {final:.2f}V")
        else:
            print(f"✗ Failed to set {axis}-axis voltage")
            
        return success

    def set_voltage(self, axis: str, voltage: float, verify: bool = True) -> bool:
        """Compatibility wrapper for GUI and external callers.

        Delegates to `set_voltage_safe` and preserves the high-level safety
        behavior. The `verify` flag is accepted for API compatibility but
        verification is performed by the underlying low-level controller.
        """
        # Use set_voltage_safe which enforces safety when `self.safety_enabled` is True.
        return self.set_voltage_safe(axis, voltage, force=False)
    
    def move_relative(self, axis: str, delta_voltage: float) -> bool:
        """
        Move axis by relative voltage amount
        
        Args:
            axis: Target axis
            delta_voltage: Voltage change (can be negative)
            
        Returns:
            bool: True if successful
        """
        if not self.is_connected():
            return False
        
        current = self.controller.get_voltage(axis)
        if current is None:
            return False
        
        target = current + delta_voltage
        return self.set_voltage_safe(axis, target)
    
    def set_all_voltages_safe(self, voltages: Dict[str, float], force: bool = False) -> bool:
        """
        Set multiple voltages with safety checks
        
        Args:
            voltages: Dict of axis:voltage pairs
            force: Bypass safety limits
            
        Returns:
            bool: True if all successful
        """
        if not self.is_connected():
            return False
        
        # Validate all voltages first
        for axis, voltage in voltages.items():
            if axis.upper() not in self.controller.axes:
                print(f"Invalid axis '{axis}'")
                return False
                
            if self.safety_enabled and not force:
                limits = self.voltage_limits.get(axis.upper(), {})
                safe_max = limits.get("safe_max", 100.0)
                
                if voltage > safe_max:
                    print(f"Voltage {voltage}V exceeds safe limit for {axis}")
                    return False
        
        print(f"Setting voltages: {voltages}")
        success = self.controller.set_all_voltages(voltages)
        
        if success:
            print("✓ All voltages set successfully")
        else:
            print("✗ Some voltages failed to set")
            
        return success
    
    def zero_all_axes(self) -> bool:
        """Set all axes to 0V"""
        voltages = {axis: 0.0 for axis in self.controller.axes}
        return self.set_all_voltages_safe(voltages, force=True)  # Allow zero even if safety enabled
    
    def scan_axis(self, axis: str, start_v: float, end_v: float, steps: int, 
                  step_time: float = 0.1) -> List[Tuple[float, float]]:
        """
        Scan axis voltage and record positions
        
        Args:
            axis: Target axis
            start_v: Start voltage
            end_v: End voltage  
            steps: Number of steps
            step_time: Time between steps
            
        Returns:
            list: List of (voltage, actual_voltage) tuples
        """
        if not self.is_connected():
            return []
        
        results = []
        voltages = [start_v + i * (end_v - start_v) / (steps - 1) for i in range(steps)]
        
        print(f"Scanning {axis}-axis from {start_v}V to {end_v}V in {steps} steps")
        
        for i, voltage in enumerate(voltages):
            if self.set_voltage_safe(axis, voltage):
                time.sleep(step_time)
                actual = self.controller.get_voltage(axis)
                results.append((voltage, actual))
                print(f"  Step {i+1}/{steps}: {voltage:.2f}V → {actual:.2f}V")
            else:
                print(f"  Step {i+1}/{steps}: Failed at {voltage:.2f}V")
                break
        
        return results
    
    def enable_safety(self, enabled: bool = True):
        """Enable/disable safety limits"""
        self.safety_enabled = enabled
        print(f"Safety limits {'enabled' if enabled else 'disabled'}")
    
    def disable_safety(self):
        """Disable safety limits"""
        self.enable_safety(False)
    
    
    def set_safe_max(self, safe_max: float):
        """Set custom safe maximum voltage for all axes
        
        Args:
            safe_max: New safe maximum voltage (must be <= device max)
        """
        if not self.controller:
            return
        
        for axis in self.controller.axes:
            device_max = self.voltage_limits[axis]['max']
            self.voltage_limits[axis]['safe_max'] = min(safe_max, device_max)
        
        print(f"Safe maximum set to {safe_max}V")
    
    def get_safe_max(self) -> float:
        """Get current safe maximum voltage
        
        Returns:
            float: Safe maximum voltage (returns first axis value)
        """
        if self.voltage_limits and self.controller.axes:
            return self.voltage_limits[self.controller.axes[0]]['safe_max']
        return 100.0
    def disconnect(self):
        """Disconnect from device"""
        if self.controller:
            self.controller.disconnect()
            self.controller = None
        print("Disconnected from MDT device")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Device discovery and factory functions
def discover_mdt_devices() -> List[Dict]:
    """Discover all available MDT devices"""
    try:
        with open("mdt_devices.json", "r") as f:
            devices = json.load(f)
        return [d for d in devices if "MDT" in d.get("Model", "")]
    except:
        return []

def create_mdt_controller(port: str = None, high_level: bool = True) -> Union[MDTController, HighLevelMDTController]:
    """
    Factory function to create MDT controller
    
    Args:
        port: Specific port, or None for auto-discovery
        high_level: Whether to create high-level controller
        
    Returns:
        MDT controller instance
    """
    if high_level:
        return HighLevelMDTController(port=port)
    else:
        devices = discover_mdt_devices()
        if devices and not port:
            device_info = devices[0]
            port = device_info["Device"]
            model = device_info.get("Model")
        
        return MDTController(port=port, model=model)


if __name__ == "__main__":
    # Demo usage
    print("MDT Controller Demo")
    print("=" * 20)
    
    # High-level controller (recommended)
    with HighLevelMDTController() as mdt:
        if mdt.is_connected():
            status = mdt.get_device_status()
            print(f"Connected to: {status['model']} on {status['port']}")
            print(f"Axes: {status['axes']}")
            print(f"Current voltages: {status['current_voltages']}")
            
            # Safe voltage setting example
            # mdt.set_voltage_safe("X", 5.0)
            
            # Zero all axes
            # mdt.zero_all_axes()
        else:
            print("No MDT devices found")