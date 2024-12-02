# -*- coding: utf-8 -*-
import os
import json
import logging
import subprocess
import threading
import time
from vedbus import VeDbusService
from gi.repository import GLib
import platform
from dbus.mainloop.glib import DBusGMainLoop

# Set the PYTHONPATH programmatically to ensure 'vedbus' can be found
os.environ['PYTHONPATH'] = '/data/velib_python-master:' + os.environ.get('PYTHONPATH', '')

# Load CAN ID mappings from JSON
with open('/opt/victronenergy/dbus-canbus-battery/can-mappings.json') as f:
    CAN_MAPPINGS = json.load(f)

class DbusBatteryService:
    def __init__(self):
        # Set up the default main loop for D-Bus connection
        self.mainloop = DBusGMainLoop(set_as_default=True)

        # Initialize the D-Bus service with register=False
        self._dbusservice = VeDbusService('com.victronenergy.battery', register=False)

        # Set mandatory paths for the service
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', 'BMS-CAN')

        # Initialize product paths
        self._dbusservice.add_path('/DeviceInstance', 41)
        self._dbusservice.add_path('/ProductId', 0xBA77)
        self._dbusservice.add_path('/ProductName', 'ELPM482-00005')
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

        # Custom paths for battery data
        self._dbusservice.add_path('/Info/MaxDischargeCurrent', 0.0)
        self._dbusservice.add_path('/Info/MaxChargeVoltage', 0.0)
        self._dbusservice.add_path('/Info/MaxChargeCurrent', 0.0)
        self._dbusservice.add_path('/Info/BatteryLowVoltage', 0.0)

        # Initialize additional D-Bus paths
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
        
        # New paths for Installed Capacity and Available Capacity
        self._dbusservice.add_path('/InstalledCapacity', 0.0)
        self._dbusservice.add_path('/Capacity', 0.0)  # Available Capacity

        # Add alarm paths
        self._dbusservice.add_path('/Alarms/HighVoltage', 0)
        self._dbusservice.add_path('/Alarms/LowVoltage', 0)
        self._dbusservice.add_path('/Alarms/HighTemperature', 0)
        self._dbusservice.add_path('/Alarms/LowTemperature', 0)
        self._dbusservice.add_path('/Alarms/HighChargeCurrent', 0)
        self._dbusservice.add_path('/Alarms/HighDischargeCurrent', 0)
        self._dbusservice.add_path('/Alarms/HighChargeTemperature', 0)
        self._dbusservice.add_path('/Alarms/CellImbalance', 0)

        # Register the service only after all paths are added
        self._dbusservice.register()

        # Buffer for storing data to average over 10 seconds
        self.data_buffer = {path: [] for can_id in CAN_MAPPINGS for path in CAN_MAPPINGS[can_id]}
        self.precision_buffer = {path: CAN_MAPPINGS[can_id][path].get("precision") for can_id in CAN_MAPPINGS for path in CAN_MAPPINGS[can_id]}
        self.start_time = time.time()

        # Variables to track Installed Capacity and State of Charge
        self.installed_capacity = 0
        self.soc = 0

        # Start the D-Bus update loop in a separate thread
        threading.Thread(target=self._start_dbus_update_loop).start()

        # Start listening to CAN bus for battery data
        self._can_listener()

    def _start_dbus_update_loop(self):
        """Start the D-Bus update loop in a separate thread"""
        logging.info("Starting D-Bus update loop...")
        GLib.timeout_add(1000, self._update)
        mainloop = GLib.MainLoop()
        mainloop.run()

    def _can_listener(self):
        """Listen to CAN bus for messages using candump"""
        logging.info("Starting CAN listener...")

        # Start a subprocess to run candump and capture its output
        self.proc = subprocess.Popen(
            ['candump', 'can1'],  # Listen to can1 interface
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Read output line by line
        self._process_can_output()

    def _process_can_output(self):
        """Process the output of candump and extract the battery data"""
        logging.info("Started processing CAN output...")

        try:
            while True:
                output = self.proc.stdout.readline()
                if output == '' and self.proc.poll() is not None:
                    break

                if output:
                    logging.debug(f"candump output: {output.strip()}")

                    parts = output.split()
                    can_id = parts[1]
                    data = parts[3:]
                    if data[0] == '[8]':
                        data = data[1:]

                    if can_id in CAN_MAPPINGS:
                        self._parse_can_data(can_id, data)

                # Check if 10 seconds have passed
                if time.time() - self.start_time >= 10:
                    self._send_averaged_data()
                    self.start_time = time.time()
                    # Clear the buffer after sending averaged data
                    self.data_buffer = {path: [] for can_id in CAN_MAPPINGS for path in CAN_MAPPINGS[can_id]}

        except KeyboardInterrupt:
            logging.info("Process interrupted. Stopping the listener.")
            self.proc.terminate()

    def _parse_can_data(self, can_id, data):
        """Parse CAN data based on mappings"""
        mapping = CAN_MAPPINGS[can_id]
        for path, config in mapping.items():
            value = self._extract_value(
                data,
                config["bytes"],
                config["type"],
                config.get("scale", 1),  # Set default scale to 1 if missing
                config.get("byte_order"),
                bit=config.get("bit"),
                true_value=config.get("true_value", 2),
                false_value=config.get("false_value", 0)
            )
            logging.info(f"Buffering {path}: {value}")
            if value is not None:  # Only add non-null values
                self.data_buffer[path].append(value)

    def _extract_value(self, data, bytes_list, data_type, scale, byte_order=None, bit=None, true_value=2, false_value=0):
        """Extract and convert value based on type, scale, byte order, and bit processing"""
        # Collect the raw bytes
        raw_bytes = [data[i] for i in bytes_list]
        if byte_order == "reversed":
            raw_bytes.reverse()

        # Convert bytes to an integer value
        raw_value = int(''.join(raw_bytes), 16)

        # Check if a specific bit extraction is required
        if data_type == "bool" and bit is not None:
            # Check if the specified bit is set
            is_bit_set = (raw_value >> bit) & 1
            return true_value if is_bit_set else false_value

        # Interpret signed types if specified
        if data_type == "S8":
            raw_value = int.from_bytes(raw_value.to_bytes(1, 'big'), 'big', signed=True)
        elif data_type == "S16":
            raw_value = int.from_bytes(raw_value.to_bytes(2, 'big'), 'big', signed=True)
        
        return raw_value * scale

    def _average(self, values):
        """Calculate the average of a list, excluding null values"""
        if not values:
            return None
        return sum(values) / len(values)

    def _calculate_available_capacity(self):
        """Calculate Available Capacity based on Installed Capacity and SoC"""
        available_capacity = int(self.installed_capacity * (self.soc / 100))
        logging.info(f"Setting /Capacity (Available Capacity): {available_capacity}")
        self._dbusservice['/Capacity'] = available_capacity

    def _send_averaged_data(self):
        """Calculate and send the average of each buffered value to D-Bus, including power calculation."""
        nr_of_modules_online = None
        voltage = None
        current = None

        for path, values in self.data_buffer.items():
            if values:  # Only calculate average if there are values
                avg_value = self._average(values)
                # Apply precision formatting after averaging
                precision = self.precision_buffer.get(path)
                if precision is not None:
                    avg_value = float(f"{avg_value:.{precision}f}")  # Convert formatted string back to float
                logging.info(f"Setting averaged {path}: {avg_value}")
                self._dbusservice[path] = avg_value

                # Track voltage and current for power calculation
                if path == '/Dc/0/Voltage':
                    voltage = avg_value
                elif path == '/Dc/0/Current':
                    current = avg_value

                # Track the NrOfModulesOnline value to calculate InstalledCapacity
                if path == '/System/NrOfModulesOnline':
                    nr_of_modules_online = int(avg_value)
                elif path == '/Soc':
                    self.soc = int(avg_value)

        # Calculate power if both voltage and current are available
        if voltage is not None and current is not None:
            power = round(voltage * current)  # Round power to integer for precision 0
            logging.info(f"Setting /Dc/0/Power (Voltage * Current, rounded to 0 precision): {power}")
            self._dbusservice['/Dc/0/Power'] = power

        # Calculate InstalledCapacity based on NrOfModulesOnline
        if nr_of_modules_online is not None:
            self.installed_capacity = nr_of_modules_online * 94
            logging.info(f"Setting /InstalledCapacity: {self.installed_capacity}")
            self._dbusservice['/InstalledCapacity'] = self.installed_capacity

        # Calculate Available Capacity based on InstalledCapacity and SoC
        if self.installed_capacity and self.soc:
            self._calculate_available_capacity()

    def _update(self):
        """Dummy update method for D-Bus service"""
        logging.debug("Updating D-Bus battery data (if any dynamic data needed)")
        return True


# Main execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    service = DbusBatteryService()
    logging.info('Battery D-Bus service initialized and running.')
