#!/usr/bin/env python3
"""Probe serial COM ports for Thorlabs MDT controllers.

This script scans available COM ports, opens each port briefly at the
expected MDT baudrate (115200 8N1), sends a handful of identification
or read commands (safe, non-destructive), and looks for replies that
match known MDT signatures (model names or numeric voltages).

It is designed to detect a Thorlabs MDT device even when the USB->Serial
adapter reports a generic vendor (e.g., Prolific) by actively probing the
serial protocol.

Usage:
  python tools\probe_mdt.py           # print human-readable results
  python tools\probe_mdt.py --json out.json  # save JSON results to file

Requires: pyserial (serial, serial.tools.list_ports)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Dict, Optional, Tuple

from serial.tools import list_ports

try:
    import serial
except Exception as e:
    print("Missing dependency 'pyserial'. Install with: pip install pyserial")
    raise

ID_COMMANDS = [b'XR?\r', b'ID?\r', b'*IDN?\r', b'XR?\n', b'XR?']
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 0.3


def _strip_echo_and_prompts(raw: bytes, cmd: bytes) -> str:
    """Decode response, strip echoed command and common prompts."""
    try:
        s = raw.decode('ascii', errors='ignore')
    except Exception:
        s = str(raw)
    s = s.strip()
    # remove echoed command if present at start
    try:
        cmd_text = cmd.decode('ascii', errors='ignore').strip()
        if cmd_text and s.startswith(cmd_text):
            s = s[len(cmd_text) :].strip()
    except Exception:
        pass
    # strip common terminators/prompts
    s = s.strip('\r\n >!*')
    return s


def probe_port(port_name: str, baud: int, timeout: float) -> Dict:
    """Probe a single COM port and return a result dict.

    The result dict contains fields: open_error (if any), match (bool),
    reply (raw/decoded reply or None), info (port product/manuf),
    and vid/pid when available.
    """
    res: Dict = {'port': port_name, 'match': False, 'reply': None}
    try:
        ports = {p.device: p for p in list_ports.comports()}
        pinfo = ports.get(port_name)
        if pinfo:
            res['manufacturer'] = pinfo.manufacturer
            res['product'] = pinfo.product
            res['vid'] = getattr(pinfo, 'vid', None)
            res['pid'] = getattr(pinfo, 'pid', None)
            res['hwid'] = pinfo.hwid
    except Exception:
        pass

    try:
        ser = serial.Serial(port=port_name, baudrate=baud, timeout=timeout)
    except Exception as e:
        res['open_error'] = str(e)
        return res

    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception:
        pass

    best_reply: Optional[str] = None

    for cmd in ID_COMMANDS:
        try:
            ser.write(cmd)
        except Exception:
            continue
        # short pause to give device time to reply
        time.sleep(0.05)
        try:
            raw = ser.read(1024)
        except Exception:
            raw = b''

        if not raw:
            # try a slightly longer read to catch slower devices
            try:
                raw = ser.read(2048)
            except Exception:
                raw = b''

        decoded = _strip_echo_and_prompts(raw, cmd)
        if decoded:
            # heuristic checks
            u = decoded.upper()
            if 'MDT' in u or 'THOR' in u or re.search(r'69[34]', u):
                res['match'] = True
                res['reply'] = decoded
                ser.close()
                return res
            if re.search(r'-?\d+\.\d+', decoded):
                # numeric voltage reply is a strong sign
                res['match'] = True
                res['reply'] = decoded
                ser.close()
                return res
            # keep something for human inspection
            best_reply = decoded

    try:
        ser.close()
    except Exception:
        pass

    if best_reply:
        res['reply'] = best_reply
    return res


def scan_ports(baud: int, timeout: float) -> Dict[str, Dict]:
    ports = list_ports.comports()
    results: Dict[str, Dict] = {}
    for p in ports:
        name = p.device
        results[name] = probe_port(name, baud, timeout)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description='Probe COM ports for Thorlabs MDT devices')
    p.add_argument('--baud', '-b', type=int, default=DEFAULT_BAUD, help='baud rate (default 115200)')
    p.add_argument('--timeout', '-t', type=float, default=DEFAULT_TIMEOUT, help='read timeout seconds')
    p.add_argument('--json', '-j', nargs='?', const='mdt_devices.json', help='write results to JSON file (optional filename)')
    p.add_argument('--pretty', action='store_true', help='pretty-print JSON when using --json')
    args = p.parse_args(argv)

    results = scan_ports(args.baud, args.timeout)

    # print summary
    for port, info in results.items():
        status = 'MATCH' if info.get('match') else 'no'
        reply = info.get('reply') or ''
        manuf = info.get('manufacturer') or ''
        product = info.get('product') or ''
        print(f"{port}: match={status} manuf={manuf} product={product} reply={reply}")

    if args.json:
        fn = args.json if isinstance(args.json, str) and args.json != 'True' else 'mdt_devices.json'
        try:
            with open(fn, 'w', encoding='utf-8') as fh:
                if args.pretty:
                    json.dump(results, fh, indent=2, ensure_ascii=False)
                else:
                    json.dump(results, fh, ensure_ascii=False)
            print(f"Saved {len(results)} entries to JSON: {fn}")
        except Exception as e:
            print(f"Failed to write JSON: {e}")


if __name__ == '__main__':
    main()
