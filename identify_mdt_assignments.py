#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""
Physical-mapping verification for MDT piezo controllers via the unplug test.

For each role in `hardware.mdt_controllers` (SharedParams.json) the script:
  1. Snapshots all currently-present COM ports.
  2. Asks you to physically UNPLUG that one controller's USB cable.
  3. Detects which COM port disappeared and compares to the configured port.
  4. Asks you to plug it back in, waits until it reappears.
  5. Reports a confirmed/mismatched mapping per role and writes a JSON summary.

Why we need this: from electrical readout we can identify *model* and *current
voltage* on each COM port, but for two same-model controllers (e.g. the two
MDT694B units that drive 422 X-tilt and Y-tilt) electrical readout alone
cannot say which physical box is X and which is Y. The unplug test resolves
that.

Run on the lab PC. Close the Thorlabs MDT Control GUI first.

Usage:
    python identify_mdt_assignments.py                # walk through all roles
    python identify_mdt_assignments.py --role 422_detection_X
    python identify_mdt_assignments.py --no-fix       # report only, do not
                                                       # offer to rewrite
                                                       # SharedParams
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from serial.tools import list_ports
except Exception:
    print("ERROR: pyserial is required.\n  pip install pyserial")
    sys.exit(1)

script_dir = Path(__file__).parent
qua_root = script_dir.parent.parent
SHARED_PARAMS = qua_root / "Servers" / "SharedParams.json"

POLL_INTERVAL = 0.5      # seconds between port re-scans while waiting
WAIT_TIMEOUT = 60.0      # max seconds to wait for unplug/replug


def snapshot_ports():
    """Return dict {port_name -> identity_dict} of currently-present COM ports."""
    out = {}
    for p in list_ports.comports():
        out[p.device] = {
            "device": p.device,
            "description": p.description,
            "manufacturer": p.manufacturer,
            "vid_pid": (f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None else ""),
            "serial_number": p.serial_number,
            "hwid": p.hwid,
        }
    return out


def wait_for_change(baseline, expect_disappear=True, timeout=WAIT_TIMEOUT):
    """Poll until set of present ports differs from baseline. Return (changed_ports, current)."""
    deadline = time.time() + timeout
    baseline_keys = set(baseline.keys())
    while time.time() < deadline:
        current = snapshot_ports()
        current_keys = set(current.keys())
        if expect_disappear:
            disappeared = baseline_keys - current_keys
            if disappeared:
                return sorted(disappeared), current
        else:
            appeared = current_keys - baseline_keys
            if appeared:
                return sorted(appeared), current
        time.sleep(POLL_INTERVAL)
    return [], snapshot_ports()


def verify_role(role, cfg):
    expected_port = cfg.get("port")
    model = cfg.get("model", "?")
    purpose = cfg.get("purpose", "")

    print(f"\n=== {role}  (config says port = {expected_port}, model = {model}) ===")
    print(f"    purpose: {purpose}")

    baseline = snapshot_ports()
    if expected_port not in baseline:
        print(f"    NOTE: configured port {expected_port} is NOT currently present.")
        print( "          Either it's already unplugged, or the cable/PC enumeration is off.")

    print(f"\n    >>> Now UNPLUG the USB cable of the controller you believe is '{role}'.")
    print( "        (Press Enter when unplugged; or just unplug and wait.)")
    try:
        input("        [Enter]: ")
    except KeyboardInterrupt:
        return {"role": role, "result": "aborted"}

    disappeared, _ = wait_for_change(baseline, expect_disappear=True)
    if not disappeared:
        print(f"    FAIL: no port disappeared within {WAIT_TIMEOUT:.0f}s.")
        return {
            "role": role, "expected_port": expected_port,
            "disappeared": [], "result": "no_change_detected",
        }

    if len(disappeared) > 1:
        print(f"    WARN: more than one port disappeared: {disappeared}")
    actual_port = disappeared[0]

    matched = (actual_port == expected_port)
    if matched:
        print(f"    OK: '{role}' is on {actual_port}  -- matches config.")
    else:
        print(f"    MISMATCH: '{role}' is actually on {actual_port}, "
              f"config says {expected_port}.")

    print(f"\n    >>> Now PLUG IT BACK IN. Waiting for it to reappear...")
    appeared, _ = wait_for_change(snapshot_ports(), expect_disappear=False)
    if appeared:
        print(f"    Reappeared as {appeared[0]}.  Continuing.")
        if appeared[0] != actual_port:
            print(f"    NOTE: came back as {appeared[0]} (was {actual_port}). "
                   "Windows may have re-enumerated.")
    else:
        print(f"    WARN: did not see the port reappear within {WAIT_TIMEOUT:.0f}s. "
               "Continuing anyway.")

    return {
        "role": role, "expected_port": expected_port,
        "actual_port": actual_port, "all_disappeared": disappeared,
        "result": "matched" if matched else "mismatched",
    }


def maybe_fix_shared_params(results, dry_run=False):
    """If any role mismatched, propose a port swap and offer to write it back."""
    mismatches = [r for r in results if r.get("result") == "mismatched"]
    if not mismatches:
        return False

    print("\n--- Proposed corrections to SharedParams.json ---")
    proposed = {r["role"]: r["actual_port"] for r in mismatches}
    for role, port in proposed.items():
        print(f"    {role}: port -> {port}")

    if dry_run:
        print("(--no-fix set; not modifying SharedParams.json)")
        return False

    try:
        ans = input("\nApply these changes to SharedParams.json now? [y/N]: ").strip().lower()
    except KeyboardInterrupt:
        return False
    if ans != "y":
        print("Skipped. You can edit SharedParams.json by hand.")
        return False

    with open(SHARED_PARAMS) as f:
        params = json.load(f)
    mdt = params.get("hardware", {}).get("mdt_controllers", {})
    for role, port in proposed.items():
        if role in mdt:
            mdt[role]["port"] = port
            mdt[role].setdefault("notes", "")
            mdt[role]["notes"] = (
                mdt[role]["notes"] + f" | Port reassigned to {port} on "
                f"{datetime.now().date().isoformat()} by unplug test."
            ).strip(" |")

    backup = SHARED_PARAMS.with_suffix(
        SHARED_PARAMS.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    backup.write_text(SHARED_PARAMS.read_text(encoding="utf-8"), encoding="utf-8")
    with open(SHARED_PARAMS, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=4)
    print(f"Updated {SHARED_PARAMS}.  Backup at {backup}.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", default=None,
                        help="Verify only this single role (default: all).")
    parser.add_argument("--no-fix", action="store_true",
                        help="Report only; do not offer to rewrite SharedParams.")
    parser.add_argument("--report-dir", default=str(script_dir),
                        help="Directory for the JSON report (default: script dir).")
    args = parser.parse_args()

    with open(SHARED_PARAMS) as f:
        params = json.load(f)
    expected = params.get("hardware", {}).get("mdt_controllers", {})

    if args.role:
        if args.role not in expected:
            print(f"ERROR: role '{args.role}' not in SharedParams.mdt_controllers")
            print(f"       available: {list(expected.keys())}")
            return 2
        roles = [args.role]
    else:
        roles = list(expected.keys())

    print(f"Will walk through {len(roles)} role(s):")
    for r in roles:
        print(f"  - {r}  (configured port {expected[r].get('port')})")
    print(f"\nUnplug/replug each one when prompted.  Ctrl-C to abort.\n")

    results = []
    for role in roles:
        try:
            results.append(verify_role(role, expected[role]))
        except KeyboardInterrupt:
            print("\nAborted by user.")
            break

    print("\n=== Summary ===")
    for r in results:
        if r["result"] == "matched":
            print(f"  OK        {r['role']:<22} -> {r.get('actual_port')}")
        elif r["result"] == "mismatched":
            print(f"  MISMATCH  {r['role']:<22} expected {r['expected_port']} "
                  f"but found {r.get('actual_port')}")
        else:
            print(f"  ?         {r['role']:<22} {r['result']}")

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "shared_params": str(SHARED_PARAMS),
        "results": results,
    }
    out = Path(args.report_dir) / f"mdt_assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {out}")

    maybe_fix_shared_params(results, dry_run=args.no_fix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
