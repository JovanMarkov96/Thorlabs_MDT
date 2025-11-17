# Quick Start — Thorlabs MDT Controllers

This file contains a minimal Quick Start to get the GUI or Python API running.

Prerequisites
- Python 3.10+ (use your project's virtual environment)
- Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the GUI

```powershell
python MDTControlGUI.py
```

Discover devices (recommended)

The repository includes a convenience wrapper `find_MDT_devices.py` that enumerates COM ports and — by default — actively probes each port with safe MDT queries to detect Thorlabs devices even when the USB adapter reports a generic vendor (e.g., Prolific).

Examples:

```powershell
# Probe all COM ports and print results
python find_MDT_devices.py

# Probe and save JSON output
python find_MDT_devices.py --json

# Disable active probing and use passive enumeration only
python find_MDT_devices.py --no-probe --json
```

Quick Python usage

```python
from mdt import HighLevelMDTController

with HighLevelMDTController() as mdt:
    if mdt.is_connected():
        # Set X-axis to 25 V safely
        mdt.set_voltage_safe("X", 25.0)
        print(mdt.get_device_status()["current_voltages"])
```

Notes
- The project runtime lives under `src/mdt/` and compatibility wrappers at the repository root let you run existing scripts without changing calls.
- Default conservative safety limit is 100 V; device maximum is 150 V (software-enforced).
