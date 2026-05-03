#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""
Query each MDT piezo controller for its model + serial number over RS-232.

This is the non-disruptive way to disambiguate two same-model controllers
(e.g. the two MDT694B units on the 422 detection X- and Y-tilt) without
unplugging USB cables -- which on the 422 line would risk losing ion
alignment.

How it works
------------
For each role in `hardware.mdt_controllers` (SharedParams.json) the script
opens the configured COM port, sends the read-only commands `id?` and
`serial?`, and parses the device-firmware-reported serial (the "Serial#"
field embedded in the ID response, plus the dedicated `serial?` reply).
It then compares against an expected mapping you provide (built-in default
matches the known Lab 185 422-line assignment) and prints / writes a
report. Optionally rewrites the SharedParams entries' `port` fields if a
swap is detected.

No SET / write commands are issued. The 422 stays at its current voltage.

Two backends are supported:
  --backend=direct  (default)  Open the COM port ourselves. Fails with
                                "Access is denied" if ServerLab is running
                                because it already owns the port.
  --backend=server             Route the query through ClientLab ->
                                ServerLab.get_mdt_device_info(name=...).
                                Returns the device_info ServerLab cached at
                                startup (or with refresh=True, re-queries
                                over its existing connection). Works with
                                ServerLab running. Requires that ServerLab
                                was (re)started after the
                                `get_mdt_device_info` method was added.

Usage
-----
    python query_mdt_serials.py                              # direct backend
    python query_mdt_serials.py --backend server             # via ServerLab
    python query_mdt_serials.py --backend server --refresh   # force re-query
    python query_mdt_serials.py --backend server --apply     # rewrite SharedParams
"""

import argparse
import json
import re
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

# --- Read-only allow-list. The script will refuse to send anything else. ---
READ_ONLY_COMMANDS = {"id?", "serial?", "ID?", "SERIAL?"}

# --- Known physical serials per role (Lab 185, 422 detection line) ---
# Update this dict if a controller is replaced.
EXPECTED_SERIALS = {
    "422_detection_X": "140317-02",
    "422_detection_Y": "140317-03",
    # 1064/yag controllers' physical serials are recorded in SharedParams
    # 'device_serial' (filled in from the last verify run); we don't enforce
    # them here because the user has not yet annotated which physical box
    # is yag1 vs yag2 from a serial label.
}


def parse_serial_from_id(id_text):
    """Extract the 'Serial#:<value>' field from an ID? reply, if present.

    Thorlabs MDT ID strings concatenate fields with no separator
    (e.g. ``...Serial#:140317-02Friendly Name:...``), so we restrict the
    capture to digits and dashes -- both observed serial formats
    (``140317-02`` and ``150226175403``) match. An empty match is a
    legitimate "no serial programmed" outcome.
    """
    if not id_text:
        return ""
    m = re.search(r"Serial#:\s*([0-9\-]*)", id_text)
    return m.group(1).strip() if m else ""


def parse_friendly_from_id(id_text):
    if not id_text:
        return ""
    m = re.search(r"Friendly Name:\s*([^A-Z]*?)(?:Thorlabs|$)", id_text)
    return m.group(1).strip() if m else ""


def safe_query(ctrl, cmd):
    if cmd not in READ_ONLY_COMMANDS:
        raise ValueError(f"Refusing non-read-only command: {cmd!r}")
    try:
        return ctrl.send_command(cmd)
    except Exception as e:
        return f"<error: {e}>"


def _new_result(role, cfg):
    return {
        "role": role,
        "port": cfg.get("port"),
        "expected_model": cfg.get("model", ""),
        "expected_serial": EXPECTED_SERIALS.get(role, ""),
        "id_response": None,
        "serial_response": None,
        "id_serial": "",
        "friendly_name": "",
        "match": None,
        "errors": [],
    }


def _finalize_match(out):
    actual = out["id_serial"] or (out["serial_response"] or "").strip()
    if out["expected_serial"]:
        out["match"] = (actual == out["expected_serial"]) if actual else None


def query_one_direct(role, cfg):
    """Open the COM port ourselves. Fails if ServerLab owns the port."""
    from mdt.controller import MDTController

    out = _new_result(role, cfg)
    if not cfg.get("enabled", True):
        out["errors"].append("disabled in SharedParams; skipped")
        return out

    ctrl = MDTController(port=cfg.get("port"), model=cfg.get("model", ""),
                         serial_no=cfg.get("serial_number", ""))
    try:
        if not ctrl.connect():
            out["errors"].append(f"connect() returned False on {cfg.get('port')}")
            return out
    except Exception as e:
        out["errors"].append(f"connect raised: {e}")
        return out

    out["id_response"] = safe_query(ctrl, "id?")
    time.sleep(0.05)
    out["serial_response"] = safe_query(ctrl, "serial?")
    out["id_serial"] = parse_serial_from_id(out["id_response"])
    out["friendly_name"] = parse_friendly_from_id(out["id_response"])
    _finalize_match(out)

    try:
        ctrl.disconnect()
    except Exception:
        pass
    return out


def query_one_via_server(role, cfg, lab, refresh=False):
    """Route through ClientLab.get_mdt_device_info -- works while ServerLab runs."""
    out = _new_result(role, cfg)
    if not cfg.get("enabled", True):
        out["errors"].append("disabled in SharedParams; skipped")
        return out

    try:
        resp = lab.get_mdt_device_info(name=role, refresh=refresh)
    except Exception as e:
        out["errors"].append(f"RPC raised: {e}")
        return out

    if not isinstance(resp, dict):
        out["errors"].append(f"unexpected RPC response: {resp!r}")
        return out
    if "error" in resp:
        out["errors"].append(f"server: {resp['error']}")
        return out

    info = resp.get("device_info", {}) or {}
    out["id_response"] = info.get("full_info") or ""
    out["serial_response"] = info.get("serial_number") or ""
    out["id_serial"] = (
        parse_serial_from_id(out["id_response"])
        or (info.get("serial_number") or "").strip()
    )
    out["friendly_name"] = parse_friendly_from_id(out["id_response"])
    _finalize_match(out)
    return out


def detect_swaps(results):
    """If two same-model roles have each other's expected serials, flag a swap."""
    by_role = {r["role"]: r for r in results}
    swaps = []  # list of (role_a, role_b) pairs to swap ports for
    seen = set()
    for role_a, r_a in by_role.items():
        if role_a in seen:
            continue
        if not r_a.get("id_serial"):
            continue
        for role_b, r_b in by_role.items():
            if role_b == role_a or role_b in seen:
                continue
            exp_a = EXPECTED_SERIALS.get(role_a, "")
            exp_b = EXPECTED_SERIALS.get(role_b, "")
            got_a = r_a.get("id_serial")
            got_b = r_b.get("id_serial")
            if exp_a and exp_b and got_a == exp_b and got_b == exp_a:
                swaps.append((role_a, role_b))
                seen.add(role_a)
                seen.add(role_b)
    return swaps


def detect_single_evidence_assignments(results):
    """Roles where one controller's serial is unambiguous (matches expected for
    a *different* role) but its sibling's serial is blank/unreadable. We can
    then assign by elimination."""
    inferred = []
    by_role = {r["role"]: r for r in results}
    for role, r in by_role.items():
        got = r.get("id_serial")
        if not got:
            continue
        for other_role, exp_other in EXPECTED_SERIALS.items():
            if other_role == role:
                continue
            if got == exp_other:
                # This controller's serial says it's `other_role`, not `role`.
                # If the *other* role's controller has blank serial, we can
                # infer the swap.
                other = by_role.get(other_role)
                if other and not other.get("id_serial"):
                    inferred.append((role, other_role))
    return inferred


def apply_port_swap(role_a, role_b):
    """Swap the `port` field between two roles in SharedParams.json."""
    with open(SHARED_PARAMS) as f:
        params = json.load(f)
    mdt = params["hardware"]["mdt_controllers"]
    a, b = mdt[role_a], mdt[role_b]
    # Swap every per-physical-controller field; the role label and `purpose`
    # stay put because they describe what that beam axis is supposed to do.
    for field in ("port", "serial_number", "device_serial", "firmware",
                  "vid_pid", "location", "voltage", "voltage_recorded",
                  "voltage_status", "voltage_limit", "model"):
        if field in a or field in b:
            a[field], b[field] = b.get(field), a.get(field)
    note = f" | Port swapped with {role_b if role_a < role_b else role_a} on {datetime.now().date().isoformat()} after serial-number verification."
    a["notes"] = (a.get("notes", "") + note).strip(" |")
    b["notes"] = (b.get("notes", "") + note).strip(" |")

    backup = SHARED_PARAMS.with_suffix(
        SHARED_PARAMS.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    backup.write_text(SHARED_PARAMS.read_text(encoding="utf-8"), encoding="utf-8")
    with open(SHARED_PARAMS, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=4)
    return backup


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Defaults are tuned for the common case: ServerLab is running, so we
    # route the query through it and force a fresh id?/serial? read. Just hit
    # Run in PyCharm; no flags needed.
    parser.add_argument("--backend", choices=["direct", "server"], default="server",
                        help="'server' (default) routes via ClientLab so it works "
                             "while ServerLab is running. 'direct' opens the COM "
                             "port ourselves (only use if ServerLab is stopped).")
    parser.add_argument("--no-refresh", dest="refresh", action="store_false",
                        help="Use ServerLab's startup-cached id?/serial? reply "
                             "instead of forcing a fresh query (default: refresh).")
    parser.set_defaults(refresh=True)
    parser.add_argument("--apply", dest="apply", action="store_true",
                        help="Skip the y/N prompt and rewrite SharedParams.json "
                             "if a swap is detected.")
    parser.add_argument("--no-prompt", dest="prompt", action="store_false",
                        help="Don't ask before applying / not applying.")
    parser.set_defaults(apply=False, prompt=True)
    parser.add_argument("--report-dir", default=str(script_dir),
                        help="Where to write the JSON report.")
    args = parser.parse_args()

    lab = None
    if args.backend == "server":
        # Make Qua project root importable so ClientLab is reachable.
        if str(qua_root) not in sys.path:
            sys.path.insert(0, str(qua_root))
        try:
            from Clients.ClientLab import ClientLab
            lab = ClientLab()
            status = lab.get_status()
            print(f"ServerLab status: {status}")
        except Exception as e:
            print(f"ERROR: --backend server selected but ClientLab connect failed: {e}")
            return 3

    with open(SHARED_PARAMS) as f:
        params = json.load(f)
    mdt = params.get("hardware", {}).get("mdt_controllers", {})
    if not mdt:
        print("ERROR: No 'hardware.mdt_controllers' in SharedParams.json")
        return 2

    print(f"Querying {len(mdt)} MDT controller(s) -- READ-ONLY (id?, serial?)")
    print(f"Backend: {args.backend}"
          + ("  (refresh=True)" if (args.backend == "server" and args.refresh) else ""))
    print(f"Expected serials per role: {EXPECTED_SERIALS}\n")

    results = []
    for role, cfg in mdt.items():
        print(f">>> {role}  ({cfg.get('port', '?')}, expected {cfg.get('model', '?')})")
        if args.backend == "server":
            r = query_one_via_server(role, cfg, lab, refresh=args.refresh)
        else:
            r = query_one_direct(role, cfg)
        results.append(r)

        if r["errors"]:
            for e in r["errors"]:
                print(f"    ERROR: {e}")
        else:
            print(f"    id?      -> {r['id_response']}")
            print(f"    serial?  -> {r['serial_response']!r}")
            print(f"    parsed Serial# = {r['id_serial']!r}, "
                  f"Friendly = {r['friendly_name']!r}")
            if r["expected_serial"]:
                if r["match"] is True:
                    print(f"    OK: matches expected {r['expected_serial']}")
                elif r["match"] is False:
                    print(f"    MISMATCH: expected {r['expected_serial']}, "
                          f"got {r['id_serial']!r}")
                else:
                    print(f"    UNKNOWN: expected {r['expected_serial']}, "
                          "but device returned no serial.")
        print()

    swaps = detect_swaps(results)
    inferred = detect_single_evidence_assignments(results)

    print("=== Conclusion ===")
    if swaps:
        for a, b in swaps:
            print(f"  SWAP NEEDED: {a} <-> {b} (each is on the other's port)")
    if inferred:
        for cur_role, true_role in inferred:
            print(f"  INFERRED:    controller currently labeled {cur_role!r} "
                  f"is actually {true_role!r}.")
            print( "               Sibling has blank serial; assignment by elimination.")
    if not swaps and not inferred:
        print("  No swap detected. All read serials match their configured roles "
              "(or no expected mapping was set).")

    out = Path(args.report_dir) / f"mdt_serials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "expected_serials": EXPECTED_SERIALS,
        "results": results,
        "swaps": swaps,
        "inferred": inferred,
    }, indent=2), encoding="utf-8")
    print(f"\nReport: {out}")

    if swaps or inferred:
        do_apply = args.apply
        if not do_apply and args.prompt:
            try:
                ans = input("\nApply this swap to SharedParams.json now? [y/N]: ").strip().lower()
                do_apply = (ans == "y")
            except (EOFError, KeyboardInterrupt):
                do_apply = False
        if do_apply:
            for a, b in swaps:
                backup = apply_port_swap(a, b)
                print(f"  Applied swap {a} <-> {b}.  Backup: {backup}")
            for cur_role, true_role in inferred:
                backup = apply_port_swap(cur_role, true_role)
                print(f"  Applied inferred swap {cur_role} <-> {true_role}.  Backup: {backup}")
        else:
            print("\nSharedParams.json was NOT modified. "
                  "Re-run and answer 'y', or pass --apply.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
