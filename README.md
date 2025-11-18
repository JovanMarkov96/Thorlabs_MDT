# Thorlabs MDT Piezo Controller

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./docs/licenses/LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Professional](https://img.shields.io/badge/code%20style-professional-brightgreen.svg)](https://github.com/JovanMarkov96/Thorlabs_MDT)

Professional-grade Python library and GUI for controlling Thorlabs MDT piezo voltage controllers (MDT693A, MDT693B, MDT694B). Designed for laboratory automation, research applications, and precision positioning systems.

---

## Table of Contents

- [Features](#features)
- [Supported Devices](#supported-devices)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [GUI Application](#gui-application)
  - [Python API](#python-api)
  - [Device Discovery](#device-discovery)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Safety Features](#safety-features)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Multi-Device Support**: Control multiple MDT controllers simultaneously
- **Professional GUI**: PyQt5-based interface with per-device tabs and real-time monitoring
- **Dual-Level API**: Choose between low-level control or high-level safety-wrapped operations
- **Auto-Discovery**: Intelligent COM port scanning with active device probing
- **Safety Systems**: Configurable voltage limits with override capabilities
- **Legacy Compatible**: Full support for older MDT693A devices with echo handling
- **Cross-Platform**: Works on Windows with potential Linux/macOS support
- **Type-Safe**: Modern Python with type hints throughout

---

## Supported Devices

| Model | Channels | Voltage Range | Notes |
|-------|----------|---------------|-------|
| **MDT693A** | 3 (X, Y, Z) | 0-150V | Legacy protocol with echo handling |
| **MDT693B** | 3 (X, Y, Z) | 0-150V | Modern protocol with combined commands |
| **MDT694B** | 1 (X) | 0-150V | Single-axis controller |

All devices communicate via RS232/USB-Serial at 115200 baud (8N1).

---

## Installation

### Prerequisites

- **Python**: 3.8 or higher
- **Operating System**: Windows (primary), Linux/macOS (experimental)
- **Hardware**: Thorlabs MDT controller with USB or RS232 connection

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/JovanMarkov96/Thorlabs_MDT.git
   cd Thorlabs_MDT
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   
   # Linux/macOS
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional) Install Thorlabs SDK DLLs:**
   - See [`docs/obtain_dlls.md`](./docs/obtain_dlls.md) for instructions
   - DLLs are optional and enable additional SDK functionality
   - Place DLLs in local `.mdt_dlls/` directory (not committed to repository)

---

## Quick Start

### Run the GUI

```bash
python MDTControlGUI.py
```

![MDT GUI](docs/images/mdt_gui_screenshot.png)

_Figure: MDT GUI showing multi-device control (replace with high-res screenshot at `docs/images/mdt_gui_screenshot.png`)._

The GUI will auto-discover connected devices and provide per-device control tabs.

### Python Quick Example

```python
from mdt import HighLevelMDTController

# Auto-connect to first available device
with HighLevelMDTController() as mdt:
    if mdt.is_connected():
        # Set X-axis to 25V (safe mode with 100V default limit)
        mdt.set_voltage_safe("X", 25.0)
        
        # Read current voltages
        status = mdt.get_device_status()
        print(f"Voltages: {status['current_voltages']}")
```

### Discover Devices

```bash
# Scan and probe all COM ports
python find_MDT_devices.py --json

# Output saved to mdt_devices.json (local-only)
```

For more details, see [`QUICKSTART.md`](./QUICKSTART.md).

---

## Usage

### GUI Application

Launch the multi-device control GUI:

```bash
python MDTControlGUI.py
```

**Features:**
- Auto-discovery of all connected MDT devices
- Independent tabs for each device
- Real-time voltage monitoring
- Per-axis sliders and spinboxes (0.1V resolution)
- Safety limits with visual indicators
- Quick-set buttons (0V, 10V, 25V, 50V, 75V, 100V, 150V)
- Connection management with live status

**GUI Workflow:**
1. Click "Refresh" to scan for devices
2. Select device from dropdown
3. Click "Connect" to establish communication
4. Use sliders or spinboxes to adjust voltages
5. Toggle safety limits as needed
6. Monitor live readback values

### Python API

#### High-Level Controller (Recommended)

```python
from mdt import HighLevelMDTController

# Connect to specific device
with HighLevelMDTController(port="COM9") as mdt:
    # Safe voltage operations with built-in limits
    mdt.set_voltage_safe("X", 30.0)  # 100V default safety limit
    mdt.set_voltage_safe("Y", 40.0)
    mdt.set_voltage_safe("Z", 50.0)
    
    # Set all axes simultaneously
    voltages = {"X": 20.0, "Y": 25.0, "Z": 30.0}
    mdt.set_all_voltages_safe(voltages)
    
    # Relative movement
    mdt.move_relative("X", +5.0)  # Add 5V to current X voltage
    
    # Voltage scanning for experiments
    scan_data = mdt.scan_axis("X", start_v=0, end_v=50, steps=21, step_time=0.1)
    
    # Get comprehensive device status
    status = mdt.get_device_status()
    print(f"Model: {status['model']}")
    print(f"Port: {status['port']}")
    print(f"Axes: {status['axes']}")
    print(f"Current voltages: {status['current_voltages']}")
    
    # Zero all axes
    mdt.zero_all_axes()
    
    # Override safety for advanced operations
    mdt.disable_safety()
    mdt.set_voltage_safe("X", 120.0, force=True)
```

#### Low-Level Controller (Advanced)

```python
from mdt import MDTController

# Direct serial control without safety wrappers
with MDTController(port="COM9", model="MDT693B") as controller:
    # Get device information
    info = controller.get_device_info()
    print(f"Model: {info.get('model')}")
    print(f"Firmware: {info.get('firmware')}")
    
    # Direct voltage operations
    voltage = controller.get_voltage("X")
    controller.set_voltage("X", 10.5, verify=True)
    
    # Read all axes (for 693A/B)
    all_voltages = controller.get_all_voltages()
    
    # Get/set voltage limits
    min_v, max_v = controller.get_voltage_limits("X")
    
    # Raw command interface
    response = controller.send_command("ID?")
```

### Device Discovery

```bash
# Probe all COM ports (default behavior)
python find_MDT_devices.py

# Save JSON output
python find_MDT_devices.py --json --out my_devices.json

# Passive scan only (no active probing)
python find_MDT_devices.py --no-probe

# Filter by manufacturer
python find_MDT_devices.py --vendors "Thorlabs,Prolific"
```

**Discovery Features:**
- Active probing with safe MDT queries (default)
- Detects devices behind generic USB-serial adapters (e.g., Prolific)
- Model identification from probe responses
- JSON export for integration with other tools
- Cross-reference with Thorlabs SDK (if available)

---

## Architecture

### Project Structure

```
Thorlabs_MDT/
├── src/mdt/              # Core package
│   ├── __init__.py       # Public API exports
│   ├── controller.py     # Low/high-level controllers
│   ├── discovery.py      # Device enumeration
│   ├── gui.py            # PyQt5 GUI application
│   └── MDT_COMMAND_LIB*.py  # SDK wrappers (optional)
├── tools/                # Utility scripts
│   └── probe_mdt.py      # Active device probing tool
├── docs/                 # Documentation
│   ├── manuals/          # PDF device manuals
│   ├── licenses/         # License files
│   └── obtain_dlls.md    # SDK DLL instructions
├── MDTControlGUI.py      # GUI launcher (compatibility wrapper)
├── find_MDT_devices.py   # Discovery script (compatibility wrapper)
├── connect_mdt.py        # Connection utilities (compatibility wrapper)
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Package metadata
├── README.md             # This file
└── QUICKSTART.md         # Quick start guide
```

### Design Patterns

1. **Layered Architecture**
   - Low-level: Direct serial communication (`MDTController`)
   - High-level: Safety-wrapped operations (`HighLevelMDTController`)
   - GUI: User-facing PyQt5 interface

2. **Context Managers**
   - Automatic connection/disconnection
   - Resource cleanup
   - Exception-safe operation

3. **Factory Functions**
   - `create_mdt_controller()` - Auto-discovery and instantiation
   - `discover_mdt_devices()` - Device enumeration

4. **Safety Systems**
   - Configurable voltage limits (default: 100V conservative, 150V maximum)
   - Range validation before operations
   - Override mechanisms for advanced use

### Command Protocol

All devices use RS232/USB-Serial at **115200 baud, 8N1**.

#### Short-Form Commands (Used by Controller)

| Command | Response | Description |
|---------|----------|-------------|
| `ID?` | Device info | Model, firmware, voltage range |
| `XR?` | `[  25.5]` | Read X-axis voltage |
| `XV25.5` | `xv25.5>` | Set X-axis to 25.5V |
| `XL?` / `XH?` | Voltage value | Get X-axis min/max limits |
| `XL0` / `XH150` | Acknowledgment | Set X-axis min/max limits |
| `YR?` / `ZR?` | Voltage value | Read Y/Z-axis (693A/B only) |
| `YV10` / `ZV20` | Acknowledgment | Set Y/Z-axis (693A/B only) |
| `XYZVOLTAGE?` | `[x, y, z]` | Read all axes (693B only) |

**Legacy Protocol (MDT693A):**
- Device echoes commands as acknowledgment
- Uses `!`, `*`, or `\r\n` terminators
- Controller applies ±1.0V verification tolerance
- Attempts to disable echo on connect

---

## Documentation

### Included Documentation

- **[QUICKSTART.md](./QUICKSTART.md)** - Minimal getting-started guide
- **[docs/obtain_dlls.md](./docs/obtain_dlls.md)** - How to obtain Thorlabs SDK DLLs
- **[docs/requirements.md](./docs/requirements.md)** - Hardware and software requirements
- **[docs/manuals/](./docs/manuals/)** - Device PDF manuals
- **[docs/licenses/](./docs/licenses/)** - License information

### API Reference

For detailed API documentation, see inline docstrings in source code:

```python
from mdt import HighLevelMDTController
help(HighLevelMDTController)
```

---

## Safety Features

### Built-In Protections

1. **Voltage Limits**
   - Conservative limit: **100V** (default)
   - Hardware limit: **150V** (enforced by software)
   - Per-axis validation
   - Configurable safety thresholds

2. **Connection Validation**
   - Device presence checking before operations
   - Axis validation per device model
   - Timeout protection on serial commands

3. **Error Handling**
   - Graceful disconnection on failures
   - Voltage readback verification (±1.0V tolerance for legacy devices)
   - Exception-safe context managers

### Override Mechanisms

```python
# Disable safety limits for calibration
mdt.disable_safety()
mdt.set_voltage_safe("X", 120.0, force=True)

# Re-enable safety
mdt.enable_safety()

# Adjust safety threshold
mdt.set_safe_max(120.0)  # Set new limit to 120V
```

**Warning:** Always understand the implications before disabling safety limits. Excessive voltage can damage piezo elements.

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Follow code style**: PEP 8, type hints, docstrings
4. **Add tests** for new functionality
5. **Update documentation** as needed
6. **Submit a pull request** with clear description

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run code formatting (if using black/ruff)
black src/ tests/
ruff check src/ tests/

# Run tests
pytest tests/
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) (if available) for detailed guidelines.

---

## License

This project is licensed under the **MIT License**. See [`docs/licenses/LICENSE`](./docs/licenses/LICENSE) for full text.

### Third-Party Components

- **Thorlabs SDK DLLs**: Governed by Thorlabs End-User License Agreement
  - Not included in repository
  - See [`docs/obtain_dlls.md`](./docs/obtain_dlls.md) for instructions
  - EULA summary: [`docs/licenses/Thorlabs_End-user_License.txt`](./docs/licenses/Thorlabs_End-user_License.txt)

- **PyQt5**: Licensed under GPL v3 / Commercial License
- **pyserial**: Licensed under BSD License

---

## Acknowledgments

- **Thorlabs Inc.** for MDT controller hardware and SDK
- **PyQt5 Community** for the GUI framework
- **Python Serial** (pyserial) contributors

---

## Support

For issues, questions, or feature requests:
- **GitHub Issues**: [https://github.com/JovanMarkov96/Thorlabs_MDT/issues](https://github.com/JovanMarkov96/Thorlabs_MDT/issues)
- **Documentation**: See [`docs/`](./docs/) folder
- **Device Manuals**: See [`docs/manuals/`](./docs/manuals/)

---

## Changelog

See [`CHANGELOG.md`](./CHANGELOG.md) for version history and release notes.

---

**Last Updated:** November 17, 2025  
**Version:** 0.1.0  
**Author:** JovanMarkov96
