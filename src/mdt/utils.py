#!/usr/bin/env python
"""
connect_mdt.py - connect to a device from `mdt_devices.json` by COM port,
send commands and receive responses.

Features:
- Lookup device info from `mdt_devices.json` by COM port
- Connect over raw serial (pyserial)
- Optional placeholder to use MDT SDK if available
- Send a single command or run an interactive REPL

Usage examples:
  python connect_mdt.py --com COM9 --cmd "ID?"
  python connect_mdt.py --com COM10 --interactive
  python connect_mdt.py --com COM10 --baud 115200 --terminator "\\r\\n"

"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Optional

try:
    import serial
except Exception:
    print("pyserial is required. Install it with: pip install --user pyserial")
    raise


class DeviceConnection:
    """Abstract connection interface."""

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def send_command(self, cmd: str, timeout: Optional[float] = None) -> str:
        """Send a command and return the response as a string."""
        raise NotImplementedError()


class SerialDeviceConnection(DeviceConnection):
    def __init__(self, port: str, baud: int = 115200, timeout: float = 1.0, terminator: bytes = b"\r\n"):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.terminator = terminator
        self._ser: Optional[serial.Serial] = None

    def open(self):
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def close(self):
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def send_command(self, cmd: str, timeout: Optional[float] = None) -> str:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Serial port not open")
        if timeout is None:
            timeout = self.timeout
        # Write command (ensure bytes)
        if isinstance(cmd, str):
            data = cmd.encode("utf-8")
        else:
            data = bytes(cmd)
        # Ensure terminator
        if not data.endswith(self.terminator):
            data = data + self.terminator
        self._ser.reset_input_buffer()
        self._ser.write(data)
        # Read until terminator or timeout
        end_time = time.time() + timeout
        chunks = []
        while True:
            chunk = self._ser.read_until(self.terminator)
            if chunk:
                chunks.append(chunk)
                # If the last read ended with terminator, stop
                if chunk.endswith(self.terminator):
                    break
            if time.time() > end_time:
                break
        resp = b"".join(chunks)
        try:
            return resp.decode("utf-8", errors="replace").strip()
        except Exception:
            return repr(resp)


class MDTSDKConnection(DeviceConnection):
    """Placeholder for MDT SDK-based connection. Implement SDK methods if available.

    If you have the Thorlabs MDT SDK available and prefer to use it (recommended
    for device-specific features), you can implement this class to call into the
    SDK functions instead of raw serial.
    """

    def __init__(self, serial_number: Optional[str] = None):
        self.serial_number = serial_number

    def open(self):
        raise NotImplementedError("MDT SDK support not implemented in this helper")

    def close(self):
        pass

    def send_command(self, cmd: str, timeout: Optional[float] = None) -> str:
        raise NotImplementedError("MDT SDK support not implemented in this helper")


def load_device_list(path: str = "mdt_devices.json") -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_device_by_com(devices: list, com: str) -> Optional[dict]:
    com = com.upper()
    for d in devices:
        if str(d.get("Device", "")).upper() == com:
            return d
    return None


def interactive_loop(conn: DeviceConnection):
    print("Entering interactive mode. Type commands to send; Ctrl-C or 'exit' to quit.")
    try:
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            if not line:
                continue
            if line.strip().lower() in ("exit", "quit"):
                break
            try:
                resp = conn.send_command(line)
                print(resp)
            except Exception as e:
                print(f"Error sending command: {e}")
    except KeyboardInterrupt:
        print("\nExiting interactive mode")


def main():
    parser = argparse.ArgumentParser(description="Connect to MDT device over serial and send commands.")
    parser.add_argument("--com", required=True, help="COM port to connect to (e.g. COM9)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate for serial connection")
    parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout (s)")
    parser.add_argument("--terminator", default="\\r\\n", help="Command terminator (escape sequences allowed)")
    parser.add_argument("--cmd", help="Single command to send and print response")
    parser.add_argument("--interactive", action="store_true", help="Run interactive REPL")
    parser.add_argument("--sdk", action="store_true", help="(Placeholder) use MDT SDK instead of raw serial if implemented")
    parser.add_argument("--list-file", default="mdt_devices.json", help="Path to device list JSON (generated by find_MDT_devices.py)")
    args = parser.parse_args()

    devices = load_device_list(args.list_file)
    dev = find_device_by_com(devices, args.com)
    if dev is None:
        print(f"Warning: COM {args.com} not found in {args.list_file}. Proceeding to open serial anyway.")
    else:
        print(f"Found device entry: Device={dev.get('Device')} Manufacturer={dev.get('Manufacturer')} Model={dev.get('Model')}")

    term = args.terminator.encode("utf-8").decode("unicode_escape").encode("utf-8")

    conn: DeviceConnection
    if args.sdk:
        # Not implemented: use MDT SDK connection when available
        conn = MDTSDKConnection(serial_number=(dev.get("SerialNumber") if dev else None))
    else:
        conn = SerialDeviceConnection(args.com, baud=args.baud, timeout=args.timeout, terminator=term)

    try:
        conn.open()
    except Exception as e:
        print(f"Failed to open connection to {args.com}: {e}")
        sys.exit(1)

    try:
        if args.cmd:
            try:
                resp = conn.send_command(args.cmd, timeout=args.timeout)
                print(resp)
            except Exception as e:
                print(f"Error: {e}")
        if args.interactive:
            interactive_loop(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
