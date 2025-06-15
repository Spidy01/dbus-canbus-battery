#!/bin/sh
sleep 180
exec /usr/bin/python3 /opt/victronenergy/dbus-canbus-battery/dbus-canbus-battery.py >> /var/log/dbus-canbus-battery.log 2>&1
