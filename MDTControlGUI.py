#!/usr/bin/env python
"""
MDT Piezo Controller GUI - Multi-Device Version

PyQt5 GUI for controlling multiple MDT693A/B and MDT694B piezo voltage controllers simultaneously.
Each connected device gets its own tab for independent control.
"""

import sys
import json
from pathlib import Path
from typing import Dict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QPushButton, QSlider, QDoubleSpinBox,
    QGroupBox, QCheckBox, QTextEdit, QTabWidget, QMessageBox, QProgressBar
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont

from mdt_controller import HighLevelMDTController, discover_mdt_devices


class AxisControlWidget(QWidget):
    """Widget for controlling a single axis"""
    
    voltageChanged = pyqtSignal(float)  # voltage
    
    def __init__(self, axis_name, limits, parent_tab):
        super().__init__()
        self.axis = axis_name
        self.limits = limits
        self.parent_tab = parent_tab
        self.updating = False
        self.last_valid_value = 0.0
        
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Axis label
        label = QLabel(f"{self.axis}:")
        label.setMinimumWidth(30)
        layout.addWidget(label)
        
        # Slider - always 0-150V, safety enforced dynamically
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1500)  # 150V * 10 for 0.1V resolution
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.on_slider_changed)
        layout.addWidget(self.slider, 1)
        
        # Spinbox - always 0-150V, safety enforced dynamically
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.0, 150.0)
        self.spinbox.setSingleStep(0.1)
        self.spinbox.setDecimals(2)
        self.spinbox.setSuffix(" V")
        self.spinbox.setValue(0.0)
        self.spinbox.valueChanged.connect(self.on_spinbox_changed)
        layout.addWidget(self.spinbox)
        
        self.setLayout(layout)
    
    def on_slider_changed(self, value):
        if not self.updating:
            voltage = value / 10.0
            
            # Check safety limits
            if self.parent_tab.safety_check.isChecked():
                safe_max = self.limits["safe_max"]
                if voltage > safe_max:
                    # Block the change and revert to last valid value
                    self.updating = True
                    self.slider.setValue(int(self.last_valid_value * 10))
                    self.spinbox.setValue(self.last_valid_value)
                    self.updating = False
                    self.parent_tab.show_safety_error(safe_max)
                    return
            
            self.last_valid_value = voltage
            self.updating = True
            self.spinbox.setValue(voltage)
            self.voltageChanged.emit(voltage)
            self.updating = False
    
    def on_spinbox_changed(self, voltage):
        if not self.updating:
            # Check safety limits
            if self.parent_tab.safety_check.isChecked():
                safe_max = self.limits["safe_max"]
                if voltage > safe_max:
                    # Block the change and revert to last valid value
                    self.updating = True
                    self.slider.setValue(int(self.last_valid_value * 10))
                    self.spinbox.setValue(self.last_valid_value)
                    self.updating = False
                    self.parent_tab.show_safety_error(safe_max)
                    return
            
            self.last_valid_value = voltage
            self.updating = True
            self.slider.setValue(int(voltage * 10))
            self.voltageChanged.emit(voltage)
            self.updating = False
    
    def update_safe_max(self, safe_max):
        """Update safe maximum voltage limit"""
        self.limits["safe_max"] = safe_max


class DeviceTabWidget(QWidget):
    """Tab widget for controlling a single device"""
    
    def __init__(self, port, controller):
        super().__init__()
        self.port = port
        self.controller = controller
        self.axis_controls = {}
        
        self.init_ui()
        self.load_current_voltages()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Device info
        info_group = QGroupBox("Device Information")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"Port: {self.port}"))
        info_layout.addWidget(QLabel(f"Axes: {', '.join(self.controller.controller.axes)}"))
        device_max = max(self.controller.voltage_limits[ax]["max"] for ax in self.controller.controller.axes)
        safe_max = max(self.controller.voltage_limits[ax]["safe_max"] for ax in self.controller.controller.axes)
        info_layout.addWidget(QLabel(f"Range: 0 - {device_max:.0f}V (Safe Max: {safe_max:.0f}V)"))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Axis controls (only for axes that exist on this device)
        controls_group = QGroupBox("Voltage Control")
        controls_layout = QVBoxLayout()
        
        # Only create controls for axes that exist on this specific device
        for axis in self.controller.controller.axes:
            if axis in self.controller.voltage_limits:
                axis_widget = AxisControlWidget(axis, self.controller.voltage_limits[axis], self)
                self.axis_controls[axis] = axis_widget
                controls_layout.addWidget(axis_widget)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Quick-set buttons
        quick_group = QGroupBox("Quick Set")
        quick_layout = QHBoxLayout()
        
        for voltage in [10, 25, 50, 75, 100, 150]:
            btn = QPushButton(f"{voltage}V")
            btn.clicked.connect(lambda checked, v=voltage: self.quick_set(v))
            quick_layout.addWidget(btn)
        
        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)
        
        # Advanced controls
        adv_group = QGroupBox("Advanced")
        adv_layout = QVBoxLayout()
        
        # Safe max control
        safe_layout = QHBoxLayout()
        safe_layout.addWidget(QLabel("Safe Maximum:"))
        self.safe_max_spin = QDoubleSpinBox()
        self.safe_max_spin.setRange(0, device_max)
        self.safe_max_spin.setValue(safe_max)
        self.safe_max_spin.setSuffix(" V")
        self.safe_max_spin.setDecimals(1)
        self.safe_max_spin.valueChanged.connect(self.on_safe_max_changed)
        safe_layout.addWidget(self.safe_max_spin)
        safe_layout.addStretch()
        adv_layout.addLayout(safe_layout)
        
        # Safety enable
        self.safety_check = QCheckBox("Safety Limits Enabled")
        self.safety_check.setChecked(True)
        self.safety_check.stateChanged.connect(self.on_safety_changed)
        adv_layout.addWidget(self.safety_check)
        
        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        zero_btn = QPushButton("Zero All")
        zero_btn.clicked.connect(self.zero_all)
        actions_layout.addWidget(zero_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def quick_set(self, voltage):
        """Set all axes (that exist on this device) to voltage"""
        safety_enabled = self.safety_check.isChecked()
        
        for axis in self.controller.controller.axes:
            safe_max = self.controller.voltage_limits[axis]["safe_max"]
            
            # Only check safety if checkbox is enabled
            if safety_enabled and voltage > safe_max:
                # Log warning if voltage exceeds safe max and safety is ON
                parent = self.parent()
                while parent and not isinstance(parent, MDTControlGUI):
                    parent = parent.parent()
                if parent:
                    parent.log(f"{self.port}: Quick-set {voltage}V exceeds safe max {safe_max:.1f}V for {axis} (Safety is ON)", "WARNING")
            else:
                # Set voltage (either safety is off, or voltage is within limits)
                self.controller.set_voltage(axis, voltage)
                # Update the slider/spinbox for this axis
                if axis in self.axis_controls:
                    widget = self.axis_controls[axis]
                    widget.updating = True
                    widget.slider.setValue(int(voltage * 10))
                    widget.spinbox.setValue(voltage)
                    widget.last_valid_value = voltage
                    widget.updating = False
    
    def zero_all(self):
        """Set all axes to zero"""
        for axis in self.controller.controller.axes:
            self.controller.set_voltage(axis, 0.0)
    
    def on_safe_max_changed(self, value):
        """Update safe maximum for all axes"""
        self.controller.set_safe_max(value)
        for axis_widget in self.axis_controls.values():
            axis_widget.update_safe_max(value)
    
    def show_safety_error(self, safe_max):
        """Show error message when trying to exceed safety limit"""
        # Find the main window to log the error
        parent = self.parent()
        while parent and not isinstance(parent, MDTControlGUI):
            parent = parent.parent()
        
        if parent:
            parent.log(f"{self.port}: Cannot exceed safe maximum of {safe_max:.1f}V (Safety is ON)", "ERROR")
    
    def on_safety_changed(self, state):
        """Toggle safety limits"""
        enabled = state == Qt.Checked
        if enabled:
            self.controller.enable_safety()
        else:
            self.controller.disable_safety()
    
    def load_current_voltages(self):
        """Read current voltages from device and initialize controls"""
        try:
            for axis in self.controller.controller.axes:
                voltage = self.controller.controller.get_voltage(axis)
                if voltage is not None and axis in self.axis_controls:
                    widget = self.axis_controls[axis]
                    # Update controls without triggering signals
                    widget.updating = True
                    widget.slider.setValue(int(voltage * 10))
                    widget.spinbox.setValue(voltage)
                    widget.last_valid_value = voltage
                    widget.updating = False
        except Exception as e:
            # Log error to parent window
            parent = self.parent()
            while parent and not isinstance(parent, MDTControlGUI):
                parent = parent.parent()
            if parent:
                parent.log(f"{self.port}: Error loading current voltages: {e}", "WARNING")


class MDTControlGUI(QMainWindow):
    """Main GUI window for MDT multi-device control"""
    
    def __init__(self):
        super().__init__()
        self.controllers = {}  # port -> HighLevelMDTController
        self.device_info = {}  # port -> device info dict
        self.monitoring_active = False
        
        self.init_ui()
        self.discover_devices()
        
        # Start monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_readings)
        self.monitor_timer.start(500)
    
    def init_ui(self):
        self.setWindowTitle("MDT Piezo Controller - Multi-Device")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Connection controls
        conn_group = QGroupBox("Device Connection")
        conn_layout = QHBoxLayout()
        
        conn_layout.addWidget(QLabel("Available:"))
        self.device_combo = QComboBox()
        conn_layout.addWidget(self.device_combo, 1)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_device)
        conn_layout.addWidget(self.connect_btn)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.discover_devices)
        conn_layout.addWidget(refresh_btn)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Device tabs
        self.device_tabs = QTabWidget()
        self.device_tabs.setTabsClosable(True)
        self.device_tabs.tabCloseRequested.connect(self.on_tab_close)
        layout.addWidget(self.device_tabs, 1)
        
        # Log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.log("MDT Multi-Device Control GUI initialized")
    
    def discover_devices(self):
        """Discover available MDT devices"""
        self.device_combo.clear()
        
        try:
            devices = discover_mdt_devices()
            
            if not devices:
                self.log("No devices found")
                return
            
            self.device_info = {}
            for dev in devices:
                port = dev.get("Device", "")
                if port:
                    model = dev.get("Model", "Unknown")
                    sn = dev.get("Serial Number", "")
                    label = f"{model} on {port}"
                    if sn:
                        label += f" (S/N: {sn})"
                    
                    self.device_combo.addItem(label, port)
                    self.device_info[port] = dev
            
            self.log(f"Found {len(devices)} device(s)")
            
        except Exception as e:
            self.log(f"Error discovering devices: {e}", "ERROR")
    
    def connect_device(self):
        """Connect to selected device"""
        port = self.device_combo.currentData()
        if not port:
            self.log("No device selected", "WARNING")
            return
        
        if port in self.controllers:
            self.log(f"Already connected to {port}", "WARNING")
            return
        
        try:
            # Construct high-level controller bound to the desired port
            controller = HighLevelMDTController(port=port)
            if controller.is_connected():
                self.controllers[port] = controller

                # Create tab
                info = self.device_info.get(port, {})
                model = info.get("Model", "Unknown")
                tab_name = f"{model} - {port}"

                device_tab = DeviceTabWidget(port, controller)

                # Connect axis control signals
                for axis, widget in device_tab.axis_controls.items():
                    widget.voltageChanged.connect(
                        lambda v, p=port, a=axis: self.on_voltage_changed(p, a, v)
                    )

                self.device_tabs.addTab(device_tab, tab_name)

                msg = f"Connected to {model} on {port}"
                if info.get("Serial Number"):
                    msg += f" (S/N: {info['Serial Number']})"
                self.log(msg)

                # Start monitoring
                if not self.monitoring_active:
                    self.monitoring_active = True
            else:
                self.log(f"Failed to connect to {port}", "ERROR")

        except Exception as e:
            self.log(f"Error connecting to {port}: {e}", "ERROR")
    
    def on_tab_close(self, index):
        """Handle tab close request"""
        tab = self.device_tabs.widget(index)
        if isinstance(tab, DeviceTabWidget):
            port = tab.port
            self.disconnect_device(port)
    
    def disconnect_device(self, port):
        """Disconnect from device"""
        if port not in self.controllers:
            return
        
        try:
            self.controllers[port].disconnect()
            del self.controllers[port]
            
            # Remove tab
            for i in range(self.device_tabs.count()):
                tab = self.device_tabs.widget(i)
                if isinstance(tab, DeviceTabWidget) and tab.port == port:
                    self.device_tabs.removeTab(i)
                    break
            
            self.log(f"Disconnected from {port}")
            
            # Stop monitoring if no devices
            if not self.controllers:
                self.monitoring_active = False
                
        except Exception as e:
            self.log(f"Error disconnecting {port}: {e}", "ERROR")
    
    def on_voltage_changed(self, port, axis, voltage):
        """Handle voltage change from axis control"""
        if port not in self.controllers:
            return
        
        try:
            success = self.controllers[port].set_voltage(axis, voltage)
            if not success:
                self.log(f"{port} {axis}: Set {voltage:.2f}V - verification uncertain", "WARNING")
        except Exception as e:
            self.log(f"{port} {axis}: Error setting voltage: {e}", "ERROR")
    
    def update_readings(self):
        """Update voltage readings for all devices"""
        if not self.monitoring_active or not self.controllers:
            return
        
        for i in range(self.device_tabs.count()):
            tab = self.device_tabs.widget(i)
            if isinstance(tab, DeviceTabWidget):
                port = tab.port
                if port in self.controllers:
                    controller = self.controllers[port]
                    for axis, widget in tab.axis_controls.items():
                        try:
                            voltage = controller.controller.get_voltage(axis)
                            if voltage is not None:
                                # Update spinbox to show live reading without triggering set
                                widget.updating = True
                                widget.spinbox.setValue(voltage)
                                widget.updating = False
                        except:
                            pass
    
    def log(self, message, level="INFO"):
        """Add message to log"""
        if level == "ERROR":
            color = "red"
        elif level == "WARNING":
            color = "orange"
        else:
            color = "black"
        
        self.log_text.append(f'<span style="color:{color}">[{level}] {message}</span>')
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def closeEvent(self, event):
        """Handle window close"""
        # Disconnect all devices
        for port in list(self.controllers.keys()):
            self.disconnect_device(port)
        event.accept()


def main():
    app = QApplication(sys.argv)
    gui = MDTControlGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

