"""
Local MDT_COMMAND_LIB.py wrapper that automatically selects correct DLL architecture
"""

from ctypes import *
import struct
import os

#region import dll functions

# Auto-detect architecture and load appropriate DLL
is_64bit = struct.calcsize('P') == 8
dll_suffix = "x64" if is_64bit else "win32"

# Try local copy first, then original SDK location
local_dll_path = f"./.mdt_dlls/MDT_COMMAND_LIB.dll"
sdk_dll_path = f"./MDT_COMMAND_LIB_{dll_suffix}.dll"

dll_path = local_dll_path if os.path.exists(local_dll_path) else sdk_dll_path

print(f"Loading MDT DLL: {dll_path}")
mdtLib = cdll.LoadLibrary(dll_path)

cmdOpen = mdtLib.Open
cmdOpen.restype=c_int
cmdOpen.argtypes=[c_char_p, c_int, c_int]

cmdClose = mdtLib.Close
cmdClose.restype=c_int
cmdClose.argtypes=[c_int]

cmdIsOpen = mdtLib.IsOpen
cmdIsOpen.restype=c_bool
cmdIsOpen.argtypes=[c_char_p]

cmdList = mdtLib.List
cmdList.restype=c_int
cmdList.argtypes=[c_char_p, c_int]

cmdGetId = mdtLib.GetId
cmdGetId.restype=c_int
cmdGetId.argtypes=[c_int, c_char_p, c_int]

cmdGetXAxisVoltage = mdtLib.GetXAxisVoltage
cmdGetXAxisVoltage.restype=c_int
cmdGetXAxisVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetXAxisVoltage = mdtLib.SetXAxisVoltage
cmdSetXAxisVoltage.restype=c_int
cmdSetXAxisVoltage.argtypes=[c_int, c_double]

cmdGetYAxisVoltage = mdtLib.GetYAxisVoltage
cmdGetYAxisVoltage.restype=c_int
cmdGetYAxisVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetYAxisVoltage = mdtLib.SetYAxisVoltage
cmdSetYAxisVoltage.restype=c_int
cmdSetYAxisVoltage.argtypes=[c_int, c_double]

cmdGetZAxisVoltage = mdtLib.GetZAxisVoltage
cmdGetZAxisVoltage.restype=c_int
cmdGetZAxisVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetZAxisVoltage = mdtLib.SetZAxisVoltage
cmdSetZAxisVoltage.restype=c_int
cmdSetZAxisVoltage.argtypes=[c_int, c_double]

cmdGetXYZAxisVoltage = mdtLib.GetXYZAxisVoltage
cmdGetXYZAxisVoltage.restype=c_int
cmdGetXYZAxisVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetXYZAxisVoltage = mdtLib.SetXYZAxisVoltage
cmdSetXYZAxisVoltage.restype=c_int
cmdSetXYZAxisVoltage.argtypes=[c_int, POINTER(c_double)]

cmdGetXAxisMinVoltage = mdtLib.GetXAxisMinVoltage
cmdGetXAxisMinVoltage.restype=c_int
cmdGetXAxisMinVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetXAxisMinVoltage = mdtLib.SetXAxisMinVoltage
cmdSetXAxisMinVoltage.restype=c_int
cmdSetXAxisMinVoltage.argtypes=[c_int, c_double]

cmdGetXAxisMaxVoltage = mdtLib.GetXAxisMaxVoltage
cmdGetXAxisMaxVoltage.restype=c_int
cmdGetXAxisMaxVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetXAxisMaxVoltage = mdtLib.SetXAxisMaxVoltage
cmdSetXAxisMaxVoltage.restype=c_int
cmdSetXAxisMaxVoltage.argtypes=[c_int, c_double]

cmdGetYAxisMinVoltage = mdtLib.GetYAxisMinVoltage
cmdGetYAxisMinVoltage.restype=c_int
cmdGetYAxisMinVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetYAxisMinVoltage = mdtLib.SetYAxisMinVoltage
cmdSetYAxisMinVoltage.restype=c_int
cmdSetYAxisMinVoltage.argtypes=[c_int, c_double]

cmdGetYAxisMaxVoltage = mdtLib.GetYAxisMaxVoltage
cmdGetYAxisMaxVoltage.restype=c_int
cmdGetYAxisMaxVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetYAxisMaxVoltage = mdtLib.SetYAxisMaxVoltage
cmdSetYAxisMaxVoltage.restype=c_int
cmdSetYAxisMaxVoltage.argtypes=[c_int, c_double]

cmdGetZAxisMinVoltage = mdtLib.GetZAxisMinVoltage
cmdGetZAxisMinVoltage.restype=c_int
cmdGetZAxisMinVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetZAxisMinVoltage = mdtLib.SetZAxisMinVoltage
cmdSetZAxisMinVoltage.restype=c_int
cmdSetZAxisMinVoltage.argtypes=[c_int, c_double]

cmdGetZAxisMaxVoltage = mdtLib.GetZAxisMaxVoltage
cmdGetZAxisMaxVoltage.restype=c_int
cmdGetZAxisMaxVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetZAxisMaxVoltage = mdtLib.SetZAxisMaxVoltage
cmdSetZAxisMaxVoltage.restype=c_int
cmdSetZAxisMaxVoltage.argtypes=[c_int, c_double]

cmdGetLimtVoltage = mdtLib.GetLimitVoltage
cmdGetLimtVoltage.restype=c_int
cmdGetLimtVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetLimtVoltage = mdtLib.SetLimitVoltage
cmdSetLimtVoltage.restype=c_int
cmdSetLimtVoltage.argtypes=[c_int, c_double]

cmdGetMasterScanEnable = mdtLib.GetMasterScanEnable
cmdGetMasterScanEnable.restype=c_int
cmdGetMasterScanEnable.argtypes=[c_int, POINTER(c_bool)]

cmdSetMasterScanEnable = mdtLib.SetMasterScanEnable
cmdSetMasterScanEnable.restype=c_int
cmdSetMasterScanEnable.argtypes=[c_int, c_bool]

cmdGetMasterScanVoltage = mdtLib.GetMasterScanVoltage
cmdGetMasterScanVoltage.restype=c_int
cmdGetMasterScanVoltage.argtypes=[c_int, POINTER(c_double)]

cmdSetMasterScanVoltage = mdtLib.SetMasterScanVoltage
cmdSetMasterScanVoltage.restype=c_int
cmdSetMasterScanVoltage.argtypes=[c_int, c_double]

cmdGetVoltageAdjustmentResolution = mdtLib.GetVoltageAdjustmentResolution
cmdGetVoltageAdjustmentResolution.restype=c_int
cmdGetVoltageAdjustmentResolution.argtypes=[c_int, POINTER(c_double)]

cmdSetVoltageAdjustmentResolution = mdtLib.SetVoltageAdjustmentResolution
cmdSetVoltageAdjustmentResolution.restype=c_int
cmdSetVoltageAdjustmentResolution.argtypes=[c_int, c_double]

#endregion

#region function define

def mdtOpen(serialNo, baud, timeout):
    serialNo_c = c_char_p(serialNo.encode("utf-8"))
    return cmdOpen(serialNo_c, c_int(baud), c_int(timeout))

def mdtClose(hdl):
    return cmdClose(c_int(hdl))

def mdtIsOpen(serialNo):
    serialNo_c = c_char_p(serialNo.encode("utf-8"))
    return cmdIsOpen(serialNo_c)

def mdtListDevices():
    ret = []
    buf = (c_char * 4096)()
    rst = cmdList(buf, c_int(4096))
    if rst == 0:
        temp1 = buf.value.decode('utf-8')
        temp2 = temp1.split(',')
        if(len(temp2) >= 2):
            for i in range(int(len(temp2)/2)):
                ret.append((temp2[i*2], temp2[i*2+1]))
    return ret

def mdtGetId(hdl, idString):
    buf = (c_char * 256)()
    rst = cmdGetId(c_int(hdl), buf, c_int(256))
    return buf.value.decode('utf-8') if rst == 0 else ""

def mdtGetXAxisVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetXAxisVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetXAxisVoltage(hdl, voltageValue):
    return cmdSetXAxisVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetYAxisVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetYAxisVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetYAxisVoltage(hdl, voltageValue):
    return cmdSetYAxisVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetZAxisVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetZAxisVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetZAxisVoltage(hdl, voltageValue):
    return cmdSetZAxisVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetXYZAxisVoltage(hdl, voltageValue):
    if len(voltageValue) != 3:
        return -1
    volt = (c_double * 3)(voltageValue[0], voltageValue[1], voltageValue[2])
    rst = cmdGetXYZAxisVoltage(c_int(hdl), volt)
    if rst == 0:
        return [volt[0], volt[1], volt[2]]
    else:
        return rst

def mdtSetXYZAxisVoltage(hdl, voltageValue):
    if len(voltageValue) != 3:
        return -1
    volt = (c_double * 3)(voltageValue[0], voltageValue[1], voltageValue[2])
    return cmdSetXYZAxisVoltage(c_int(hdl), volt)

def mdtGetXAxisMinVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetXAxisMinVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetXAxisMinVoltage(hdl, voltageValue):
    return cmdSetXAxisMinVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetXAxisMaxVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetXAxisMaxVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetXAxisMaxVoltage(hdl, voltageValue):
    return cmdSetXAxisMaxVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetYAxisMinVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetYAxisMinVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetYAxisMinVoltage(hdl, voltageValue):
    return cmdSetYAxisMinVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetYAxisMaxVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetYAxisMaxVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetYAxisMaxVoltage(hdl, voltageValue):
    return cmdSetYAxisMaxVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetZAxisMinVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetZAxisMinVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetZAxisMinVoltage(hdl, voltageValue):
    return cmdSetZAxisMinVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetZAxisMaxVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetZAxisMaxVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetZAxisMaxVoltage(hdl, voltageValue):
    return cmdSetZAxisMaxVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetLimtVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetLimtVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetLimtVoltage(hdl, voltageValue):
    return cmdSetLimtVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetMasterScanEnable(hdl, enableValue):
    enable = c_bool(enableValue)
    rst = cmdGetMasterScanEnable(c_int(hdl), byref(enable))
    return enable.value if rst == 0 else rst

def mdtSetMasterScanEnable(hdl, enableValue):
    return cmdSetMasterScanEnable(c_int(hdl), c_bool(enableValue))

def mdtGetMasterScanVoltage(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetMasterScanVoltage(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetMasterScanVoltage(hdl, voltageValue):
    return cmdSetMasterScanVoltage(c_int(hdl), c_double(voltageValue))

def mdtGetVoltageAdjustmentResolution(hdl, voltageValue):
    volt = c_double(voltageValue)
    rst = cmdGetVoltageAdjustmentResolution(c_int(hdl), byref(volt))
    return volt.value if rst == 0 else rst

def mdtSetVoltageAdjustmentResolution(hdl, voltageValue):
    return cmdSetVoltageAdjustmentResolution(c_int(hdl), c_double(voltageValue))

#endregion