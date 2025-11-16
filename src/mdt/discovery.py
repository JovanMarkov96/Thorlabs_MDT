#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enumerate COM ports on Windows and flag likely Thorlabs MDT693B/694B devices.
Also (optionally) cross-check with the MDT Python SDK if available.

Usage (PowerShell):
  python .\find_mdt_devices.py
"""

import sys
import re
import argparse
import json
from typing import List

# ---- pyserial is required for COM enumeration ----
try:
    from serial.tools import list_ports
except Exception as e:
    print("pyserial not found. Install it with:\n  pip install --user pyserial")
    sys.exit(1)

# ---- Try to import MDT SDK wrappers if available (optional) ----
mdt_available = False
mdt_devices = []
try:
    # This import will succeed only if your MDT wrapper can import its DLLs.
    from MDT_COMMAND_LIB import mdtListDevices
    try:
        mdt_devices = mdtListDevices()  # -> [[serialNumber, model], ...]
        mdt_available = True
    except Exception as ex:
        print(f"(Note) MDT SDK present but mdtListDevices() failed: {ex}")
except Exception:
    # Totally fine; we can still enumerate COM ports without SDK.
    pass

# ---- Heuristics for identifying likely MDT devices on USB-Serial ----
MDT_KEYWORDS = [
    "thorlabs",
    "mdt",
    "mdt69",
    "mdt693b",
    "mdt694b",
]

def is_mdt_candidate(portinfo) -> bool:
    """
    Return True if any known MDT keywords appear in relevant fields.
    """
    fields = [
        str(getattr(portinfo, "manufacturer", "")),
        str(getattr(portinfo, "product", "")),
        str(getattr(portinfo, "description", "")),
        str(getattr(portinfo, "name", "")),
        str(getattr(portinfo, "device", "")),
        str(getattr(portinfo, "hwid", "")),
    ]
    combined = " ".join(f for f in fields if f).lower()
    return any(k in combined for k in MDT_KEYWORDS)

def fmt_vid_pid(p):
    vid = getattr(p, "vid", None)
    pid = getattr(p, "pid", None)
    if vid is None and pid is None:
        # Try to parse from HWID if present e.g. 'USB VID:PID=0403:6001'
        hwid = str(getattr(p, "hwid", ""))
        m = re.search(r"VID:PID=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})", hwid)
        if m:
            return f"{m.group(1)}:{m.group(2)}"
        return ""
    if vid is not None and pid is not None:
        return f"{vid:04X}:{pid:04X}"
    return ""

def main():
    parser = argparse.ArgumentParser(description="Enumerate COM ports and optionally filter by vendor/manufacturer.")
    parser.add_argument("--vendors", "-v", help="Comma-separated vendor keywords to filter (case-insensitive). Defaults to 'Thorlabs,Prolific'", default="Thorlabs,Prolific")
    parser.add_argument("--json", help="Output results as JSON", action="store_true")
    parser.add_argument("--out", "-o", help="Output JSON file path (default: mdt_devices.json)", default="mdt_devices.json")
    parser.add_argument("--assign", "-a", help="Assign model by rule. Format: key=value. Key can be COM port (e.g. COM10), manufacturer (Prolific), or VID:PID (067B:23A3). Can be repeated.", action="append", default=[])
    args = parser.parse_args()

    vendor_filters: List[str] = [v.strip().lower() for v in args.vendors.split(",") if v.strip()] if args.vendors else ["thorlabs", "prolific"]

    # Parse assignments into lists of matchers
    assigns = []
    for a in args.assign:
        if "=" in a:
            k, v = a.split("=", 1)
            assigns.append((k.strip().lower(), v.strip()))

    print("=== COM Port Scan (Windows) ===")
    ports = list(list_ports.comports())
    if not ports:
        print("No COM ports found.")
        return

    # Build a quick index for cross-reference by serial number (if SDK is available)
    mdt_serials = set()
    mdt_models = {}
    if mdt_available:
        for sn, model in mdt_devices:
            mdt_serials.add(str(sn))
            mdt_models[str(sn)] = model

    rows = []
    for p in ports:
        row = {
            "Device": p.device,
            "Desc": getattr(p, "description", ""),
            "Manufacturer": getattr(p, "manufacturer", ""),
            "Product": getattr(p, "product", ""),
            "SerialNumber": getattr(p, "serial_number", ""),
            "VID:PID": fmt_vid_pid(p),
            "Location": getattr(p, "location", ""),
            "HWID": getattr(p, "hwid", ""),
        }
        row["LikelyMDT"] = "YES" if is_mdt_candidate(p) else ""
        # Cross-ref with MDT SDK serials if available
        sn = row["SerialNumber"]
        if mdt_available and sn and sn in mdt_serials:
            row["MDT_SDK_Model"] = mdt_models.get(sn, "")
        # Determine model
        model = ""
        # Priority 1: SDK reported model
        if "MDT_SDK_Model" in row and row.get("MDT_SDK_Model"):
            model = row.get("MDT_SDK_Model")
        # Priority 2: try to parse from description/product/name
        if not model:
            combined_parse = " ".join([str(row.get(k, "")) for k in ("Desc", "Product")])
            m = re.search(r"MDT[- ]?\d{3,4}[A-Za-z]?", combined_parse, re.IGNORECASE)
            if m:
                model = m.group(0).replace(" ", "")
        # Priority 3: apply assignments provided by user (--assign)
        if not model and assigns:
            combined_fields = " ".join([str(row.get(k, "")) for k in ("Device", "Manufacturer", "VID:PID", "HWID")]).lower()
            for key, val in assigns:
                if key in combined_fields:
                    model = val
                    break
                # allow matching by exact COM port
                if key.upper() == str(row.get("Device", "")).upper():
                    model = val
                    break
        # Priority 4: if it's a Prolific adapter with no model, allow mapping by manufacturer
        if not model and str(row.get("Manufacturer", "")).lower().find("prolific") != -1:
            # try to find an assign for 'prolific'
            for key, val in assigns:
                if key == "prolific":
                    model = val
                    break
            # If still not assigned, default Prolific adapters to MDT693A
            if not model:
                model = "MDT693A"

        row["Model"] = model

        # Apply vendor filtering if requested
        if vendor_filters:
            combined = " ".join([str(row.get(k, "")) for k in ("Manufacturer", "Product", "Desc", "HWID")]).lower()
            if any(v in combined for v in vendor_filters):
                rows.append(row)
        else:
            rows.append(row)

    # Pretty print
    def w(s, n):
        s = "" if s is None else str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    headers = [
        "Device", "Desc", "Manufacturer", "Product",
        "SerialNumber", "VID:PID", "Location", "LikelyMDT"
    ]
    # Include HWID and SDK_Model as extended columns at the end
    headers_ext = headers + ["MDT_SDK_Model", "HWID"]

    # Compute column widths
    widths = {h: max(len(h), *(len(str(r.get(h, ""))) for r in rows)) for h in headers_ext}
    # Print header
    line = " | ".join(h.ljust(widths[h]) for h in headers_ext)
    print(line)
    print("-" * len(line))
    # Add Model to headers and write output
    headers_ext = headers + ["MDT_SDK_Model", "Model", "HWID"]
    widths = {h: max(len(h), *(len(str(r.get(h, ""))) for r in rows)) for h in headers_ext}

    # Print rows (or JSON)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        # Print header
        line = " | ".join(h.ljust(widths[h]) for h in headers_ext)
        print(line)
        print("-" * len(line))
        for r in rows:
            print(" | ".join(w(r.get(h, ""), widths[h]).ljust(widths[h]) for h in headers_ext))

    # Always write JSON output file with the rows (including Model)
    try:
        out_path = args.out
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
        print(f"\nSaved {len(rows)} entries to JSON: {out_path}")
    except Exception as e:
        print(f"Failed to write JSON output {args.out}: {e}")

    print("\nTips:")
    print(" - 'LikelyMDT' = YES means the port description/manufacturer matched MDT/Thorlabs keywords.")
    print(" - If 'MDT_SDK_Model' appears, your MDT SDK reported a device with matching USB serial.")
    print(" - You can refine matches by adding exact VID:PID or product strings to MDT_KEYWORDS in this script.")
    if not mdt_available:
        print(" - MDT SDK was not imported; that’s fine. To enable cross-check, fix the SDK DLL loading and rerun.")

if __name__ == "__main__":
    main()
