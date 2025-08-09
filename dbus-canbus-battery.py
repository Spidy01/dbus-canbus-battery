#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import logging
import sys
import subprocess
import threading
import time
from vedbus import VeDbusService
from gi.repository import GLib
import platform
from dbus.mainloop.glib import DBusGMainLoop

# Configure logging to output to stdout so daemontools can capture it
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    stream=sys.stdout
)

# Set the PYTHONPATH programmatically to ensure 'vedbus' can be found
os.environ['PYTHONPATH'] = '/data/velib_python-master:' + os.environ.get('PYTHONPATH', '')

# Load CAN ID mappings from JSON.
# The file lives in the same directory as this script when installed so use the
# location of this file to build the path.  Previously the path pointed to
# '/opt/victronenergy/dbus-canbus-battery/can-mappings.json' which does not
# exist when running the service from /data.  Using a relative path ensures the
# service can find the mappings regardless of the installation directory.
CAN_MAPPING_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'can-mappings.json')
with open(CAN_MAPPING_PATH) as f:
    CAN_MAPPINGS = json.load(f)
    logging.debug(f"Loaded CAN_MAPPINGS: {json.dumps(CAN_MAPPINGS, indent=2)}")

# Time in seconds before the battery is considered disconnected
CONNECTION_TIMEOUT = 5
    
class DbusBatteryService:
    def __init__(self):
        self.mainloop = DBusGMainLoop(set_as_default=True)
        self._dbusservice = VeDbusService('com.victronenergy.battery.canbusbattery', register=False)

        # Set mandatory paths
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', 'BMS-CAN')

        # Device and product info
        self._dbusservice.add_path('/DeviceInstance', 42)
        self._dbusservice.add_path('/ProductId', 0xBA77)
        self._dbusservice.add_path('/ProductName', 'ELPM482-00005')
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 0)
        # Start disconnected until CAN frames are received
        self._dbusservice.add_path('/Connected', 0)

        # Paths
        self._dbusservice.add_path('/Info/MaxDischargeCurrent', 0.0)
        self._dbusservice.add_path('/Info/MaxChargeVoltage', 0.0)
        self._dbusservice.add_path('/Info/MaxChargeCurrent', 0.0)
        self._dbusservice.add_path('/Info/BatteryLowVoltage', 0.0)
        self._dbusservice.add_path('/Soc', 0)
        self._dbusservice.add_path('/Soh', 0)
        self._dbusservice.add_path('/System/StateOfHealth', 0)
        self._dbusservice.add_path('/Dc/0/Voltage', 0.0)
        self._dbusservice.add_path('/Dc/0/Current', 0.0)
        self._dbusservice.add_path('/Dc/0/Power', 0.0)
        self._dbusservice.add_path('/Dc/0/Temperature', 0.0)
        self._dbusservice.add_path('/System/MinCellVoltage', 0.0)
        self._dbusservice.add_path('/System/MaxCellVoltage', 0.0)
        self._dbusservice.add_path('/System/MinCellTemperature', 0)
        self._dbusservice.add_path('/System/MaxCellTemperature', 0)
        self._dbusservice.add_path('/System/NrOfModulesOnline', 0)
        self._dbusservice.add_path('/System/NrOfModulesOffline', 0)
        self._dbusservice.add_path('/InstalledCapacity', 0.0)
        self._dbusservice.add_path('/Capacity', 0.0)

        for alarm in ['HighVoltage', 'LowVoltage', 'HighTemperature', 'LowTemperature', 'HighChargeCurrent', 'HighDischargeCurrent', 'HighChargeTemperature', 'CellImbalance']:
            self._dbusservice.add_path(f'/Alarms/{alarm}', 0)

        self._dbusservice.register()

        self.data_buffer = {path: [] for can_id in CAN_MAPPINGS for path in CAN_MAPPINGS[can_id]}
        self.precision_buffer = {path: CAN_MAPPINGS[can_id][path].get("precision") for can_id in CAN_MAPPINGS for path in CAN_MAPPINGS[can_id]}
        self.start_time = time.time()

        self.installed_capacity = 0
        self.soc = 0
        self.last_valid_can_time = None
        self.last_dbus_update_time = time.time()

        threading.Thread(target=self._start_dbus_update_loop).start()
        self._can_listener()

    def _start_dbus_update_loop(self):
        logging.info("Starting D-Bus update loop...")
        GLib.timeout_add(1000, self._update)
        mainloop = GLib.MainLoop()
        mainloop.run()

    def _can_listener(self):
        logging.info("Starting CAN listener...")
        # Listen on any available CAN interface instead of a fixed one
        self.proc = subprocess.Popen(['candump', 'any'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self._process_can_output()

    def _process_can_output(self):
        logging.info("Started processing CAN output...")
        try:
            while True:
                output = self.proc.stdout.readline()
                if output == '' and self.proc.poll() is not None:
                    break
                if output:
                    logging.debug(f"candump output: {output.strip()}")
                    parts = output.split()
                    if len(parts) < 4:
                        logging.debug("Malformed CAN line received, skipping")
                        continue
                    can_id = parts[1]
                    data = parts[3:]
                    if data and data[0].startswith('['):
                        data = data[1:]
                    logging.debug(f"Parsed CAN ID: {can_id}, Data: {data}")
                    if can_id in CAN_MAPPINGS:
                        self._parse_can_data(can_id, data)
                        self.last_valid_can_time = time.time()
                    else:
                        logging.debug(f"CAN ID: {can_id} not present")

                if time.time() - self.start_time >= 2:
                    self._send_averaged_data()
                    self.start_time = time.time()
                    self.data_buffer = {path: [] for can_id in CAN_MAPPINGS for path in CAN_MAPPINGS[can_id]}
        except KeyboardInterrupt:
            logging.info("Process interrupted. Stopping the listener.")
            self.proc.terminate()

    def _parse_can_data(self, can_id, data):
        mapping = CAN_MAPPINGS.get(can_id, {})
        for path, config in mapping.items():
            try:
                bytes_list = config.get("bytes")
                data_type = config.get("type")
                if bytes_list is None or data_type is None:
                    logging.error(f"Invalid mapping for {can_id} -> {path}, skipping")
                    continue
                value = self._extract_value(
                    data,
                    bytes_list,
                    data_type,
                    config.get("scale", 1),
                    config.get("byte_order"),
                    bit=config.get("bit"),
                    true_value=config.get("true_value", 2),
                    false_value=config.get("false_value", 0)
                )
                logging.debug(f"Parsed {path} from {can_id}: {value}")
                if value is not None:
                    self.data_buffer.setdefault(path, []).append(value)
                    if path not in self.precision_buffer:
                        self.precision_buffer[path] = config.get("precision")
            except Exception as e:
                logging.error(f"Error parsing {path} from CAN ID {can_id}: {e}")

    def _extract_value(self, data, bytes_list, data_type, scale, byte_order=None, bit=None, true_value=2, false_value=0):
        try:
            raw_bytes = [data[i] for i in bytes_list]
        except IndexError:
            logging.error(f"Data {data} too short for bytes {bytes_list}")
            return None
        if byte_order == "reversed":
            raw_bytes.reverse()
        try:
            raw_value = int(''.join(raw_bytes), 16)
        except ValueError as e:
            logging.error(f"Invalid hex data {raw_bytes}: {e}")
            return None
        if data_type == "bool" and bit is not None:
            is_bit_set = (raw_value >> bit) & 1
            return true_value if is_bit_set else false_value
        if data_type == "S8":
            raw_value = int.from_bytes(raw_value.to_bytes(1, 'big'), 'big', signed=True)
        elif data_type == "S16":
            raw_value = int.from_bytes(raw_value.to_bytes(2, 'big'), 'big', signed=True)
        scaled_value = raw_value * scale
        logging.debug(f"Extracted value: raw={raw_value}, scaled={scaled_value}, type={data_type}")
        return scaled_value

    def _average(self, values):
        return sum(values) / len(values) if values else None

    def _calculate_available_capacity(self):
        available_capacity = int(self.installed_capacity * (self.soc / 100))
        logging.info(f"Setting /Capacity (Available Capacity): {available_capacity}")
        self._dbusservice['/Capacity'] = available_capacity

    def _send_averaged_data(self):
        nr_of_modules_online = None
        voltage = None
        current = None
        updated = False
        for path, values in self.data_buffer.items():
            if values:
                avg_value = self._average(values)
                precision = self.precision_buffer.get(path)
                if precision is not None:
                    avg_value = float(f"{avg_value:.{precision}f}")
                logging.info(f"Setting averaged {path}: {avg_value}")
                self._dbusservice[path] = avg_value
                updated = True
                logging.debug(f"D-Bus write: {path} = {avg_value}")
                if path == '/Dc/0/Voltage':
                    voltage = avg_value
                elif path == '/Dc/0/Current':
                    current = avg_value
                if path == '/System/NrOfModulesOnline':
                    nr_of_modules_online = int(avg_value)
                elif path == '/Soc':
                    self.soc = int(avg_value)
        if voltage is not None and current is not None:
            power = round(voltage * current)
            logging.info(f"Setting /Dc/0/Power: {power}")
            self._dbusservice['/Dc/0/Power'] = power
            updated = True
        if nr_of_modules_online is not None:
            self.installed_capacity = nr_of_modules_online * 94
            logging.info(f"Setting /InstalledCapacity: {self.installed_capacity}")
            self._dbusservice['/InstalledCapacity'] = self.installed_capacity
            updated = True
        if self.installed_capacity and self.soc:
            self._calculate_available_capacity()
            updated = True
        if updated:
            self.last_dbus_update_time = time.time()

    def _update(self):
        logging.debug("Updating D-Bus battery data...")
        now = time.time()
        if self.last_valid_can_time and now - self.last_valid_can_time <= CONNECTION_TIMEOUT:
            if self._dbusservice['/Connected'] != 1:
                logging.info("CAN connection established")
                self._dbusservice['/Connected'] = 1
        else:
            if self._dbusservice['/Connected'] != 0:
                logging.warning("CAN connection lost")
                self._dbusservice['/Connected'] = 0
        if now - self.last_dbus_update_time > 60:
            logging.error("No D-Bus updates for 60 seconds. Restarting service.")
            try:
                if hasattr(self, 'proc') and self.proc.poll() is None:
                    self.proc.terminate()
            finally:
                os._exit(1)
        return True

if __name__ == "__main__":
    service = DbusBatteryService()
    logging.info('Battery D-Bus service initialized and running.')
