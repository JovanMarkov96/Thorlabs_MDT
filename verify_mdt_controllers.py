#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""
Non-invasive MDT piezo controller verification.

Reads each controller listed under `hardware.mdt_controllers` in
SharedParams.json, opens its COM port, queries identity + current voltages
+ voltage limits, and writes a timestamped JSON report. No SET commands
are issued -- the 422 detection beam is currently aligned on the ion and
must not be perturbed.

Run on the lab PC (where the MDT controllers are wired). Close the
Thorlabs MDT Control GUI first so the COM ports are free.

Usage:
    python verify_mdt_controllers.py
    python verify_mdt_controllers.py --report-dir reports/

Hands the resulting JSON file back to the user.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

script_dir = Path(__file__).parent
src_dir = script_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

qua_root = script_dir.parent.parent
SHARED_PARAMS = qua_root / "Servers" / "SharedParams.json"

# Read-only command set. Anything that could alter device state is forbidden.
READ_ONLY_COMMANDS = {"ID?", "serial?", "XR?", "YR?", "ZR?",
                      "XL?", "XH?", "YL?", "YH?", "ZL?", "ZH?", "ECHO?"}


def load_expected():
    with open(SHARED_PARAMS) as f:
        params = json.load(f)
    return params.get("hardware", {}).get("mdt_controllers", {})


def safe_query(ctrl, cmd):
    """Send a read-only command, refusing anything not in the allow-list."""
    if cmd not in READ_ONLY_COMMANDS:
        raise ValueError(f"Refusing to send non-read-only command: {cmd!r}")
    try:
        return ctrl.send_command(cmd)
    except Exception as e:
        return f"<error: {e}>"


def verify_one(role, cfg):
    from mdt.controller import MDTController

    port = cfg.get("port")
    expected_model = cfg.get("model", "")
    expected_voltage = cfg.get("voltage", [])
    expected_serial = cfg.get("serial_number", "")

    result = {
        "role": role,
        "port": port,
        "expected_model": expected_model,
        "expected_serial": expected_serial,
        "expected_voltage": expected_voltage,
        "purpose": cfg.get("purpose", ""),
        "connected": False,
        "id_response": None,
        "serial_response": None,
        "echo_status": None,
        "voltages": {},
        "limits": {},
        "model_match": None,
        "voltage_match": None,
        "errors": [],
    }

    if not cfg.get("enabled", True):
        result["errors"].append("disabled in SharedParams; skipped")
        return result

    ctrl = MDTController(port=port, model=expected_model, serial_no=expected_serial)
    try:
        ok = ctrl.connect()
    except Exception as e:
        result["errors"].append(f"connect raised: {e}")
        return result

    if not ok:
        result["errors"].append(f"connect() returned False on {port}")
        return result

    result["connected"] = True

    # Read-only identity
    result["id_response"] = safe_query(ctrl, "ID?")
    result["serial_response"] = safe_query(ctrl, "serial?")
    if "693A" in expected_model:
        result["echo_status"] = safe_query(ctrl, "ECHO?")

    # Read voltages and limits per axis (read-only)
    for axis in ctrl.axes:
        result["voltages"][axis] = safe_query(ctrl, f"{axis}R?")
        result["limits"][axis] = {
            "low": safe_query(ctrl, f"{axis}L?"),
            "high": safe_query(ctrl, f"{axis}H?"),
        }
        time.sleep(0.05)

    id_text = (result["id_response"] or "").upper()
    if expected_model and expected_model.upper() in id_text:
        result["model_match"] = True
    elif expected_model:
        result["model_match"] = False
        result["errors"].append(
            f"ID? did not contain expected model '{expected_model}'"
        )

    # Voltage tolerance: ~1 V (for sanity check only; doesn't fail the script)
    def _to_float(s):
        if s is None:
            return None
        import re
        m = re.search(r"-?\d+\.?\d*", str(s))
        return float(m.group(0)) if m else None

    actuals = [_to_float(v) for v in result["voltages"].values()]
    if expected_voltage and all(a is not None for a in actuals):
        pairs = list(zip(expected_voltage, actuals))
        result["voltage_match"] = all(abs(e - a) <= 2.0 for e, a in pairs)

    try:
        ctrl.disconnect()
    except Exception:
        pass

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report-dir", default=str(script_dir),
                        help="Directory to write the JSON report into "
                             "(default: this script's directory).")
    args = parser.parse_args()

    expected = load_expected()
    if not expected:
        print("ERROR: No 'hardware.mdt_controllers' section in SharedParams.json")
        return 2

    print(f"Verifying {len(expected)} MDT controller(s) from SharedParams.json")
    print("(read-only -- no voltages will be changed)\n")

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "shared_params": str(SHARED_PARAMS),
        "controllers": [],
    }

    for role, cfg in expected.items():
        print(f">>> {role}  ({cfg.get('port', '?')}, expected {cfg.get('model', '?')})")
        result = verify_one(role, cfg)
        report["controllers"].append(result)

        if not result["connected"]:
            print(f"    FAIL: {'; '.join(result['errors']) or 'unknown'}")
        else:
            v_str = ", ".join(f"{ax}={v}" for ax, v in result["voltages"].items())
            tag = "OK" if result["model_match"] else "WARN"
            print(f"    {tag}  ID: {result['id_response']}")
            print(f"        voltages: {v_str}")
            if result["voltage_match"] is False:
                print(f"        WARN: voltage drift vs expected {result['expected_voltage']}")
            for e in result["errors"]:
                print(f"        note: {e}")
        print()

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = report_dir / f"mdt_verify_{stamp}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Report written: {out}")
    print("Send this file back to Claude for documentation/role assignment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
