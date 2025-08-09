# dbus-canbus-battery
Service for Victron ecosystem run on Venus OS which takes CANBUS data from BMS and publishes on dbus.
All information, files, suggestions are to be used at your own risk, I offer zero guarantees implied or otherwise.

# Update 21July2025
* Added an `install.sh` script that downloads the repository to `/data` and registers
  a persistent service under `/opt/victronenergy/service/`.
* The service now starts via the Utilities service manager rather than `inittab`.
* I did a factory reinstall with the latest venus image just to be sure that it is starting fresh again. Guide: [Factory Reinstall](https://www.victronenergy.com/media/pg/Cerbo_GX/en/reset-to-factory-defaults-and-venus-os-reinstall.html)
* The service only registers on D-Bus after receiving CAN messages and toggles the `/Connected` path if communication is lost.


# Background
This solution follows on from the previous project: [Samsung-Victron-ESS](https://github.com/o-snoopy-o/Samsung-Victron-ESS) which utilised an Arduino to capture CANBUS messages and convert them to MQTT messages for victron dbus. This solution eliminates the Arduino and allows the use of the BMS-CAN interface on the Cerbo GX directly. It could however utilise any CANBUS interface on any host system with minor modifications.
From this point forward I will refer to the Venus OS device as Cerbo GX and instructions are for windows users. If there is a need I can also provide the same for Linux users but I think you'll be more than capable to apply to your way of working.



# Quick Start
1) Make a cable that joins the GND,HIGH,LOW pins on your Battery BMS to the Cerbo GX corresponding pins.
2) Enable root account and SSH: [Root Access](https://www.victronenergy.com/live/ccgx:root_access)
3) SSH to the Cerbo GX and run the install script:
```bash
wget https://raw.githubusercontent.com/Spidy01/dbus-canbus-battery/main/install.sh -O install.sh
sh install.sh
```
4) Reboot the device once the script completes.
5) Go to the fridge and retrieve a cold beverage.
6) After the reboot, check the running processes for the service:
```bash
ps | grep dbus-canbus
```




# Detailed Guide
1) Make a cable that joins the GND,HIGH,LOW pins on your Battery BMS to the Cerbo GX corresponding pins. GND = Pin 3, CAN-Low = Pin 8, CAN-High = Pin 7. The Samsung BMS in the ELPM482-00005 module uses Pins: GND = Pin 3, CAN-Low = Pin 2, CAN-High = Pin 1. Using CAT5/6 type twisted pair cable is recommended, RJ45 ends are essential to interface with each device. The unused conductors can be cut but it does make insertion into the RJ45 plug difficult. Lubricate the wires prior to insertion using a non-corrosive product designed for such purpose.
Ensure that you have the CANBUS cable connected to the BMS and the Cerbo GX. The port on the Cerbo GX is the BMS-CAN. You must fit a termination resistor to the other port labelled BMS-CAN. On the battery BMS, you may need to flick a switch (in the case of the ELPM482-00005 module the switch is built in and can be enabled by sliding the switch to the right. As a reminder to the Samsung ELPM482-00005 module users, the CANBUS port is the one on the far left of the 4. Also, ensure all the modules have unique ID's, I recommend just connecting 1 module for initial testing.

![image](https://github.com/user-attachments/assets/4ad995dc-184f-4d3c-8e2b-2dd06780d1b7)


2) Follow the guide at the victron site: [Root Access](https://www.victronenergy.com/live/ccgx:root_access)


3) Open an SSH session to your Cerbo GX.
4) Download and execute the installer which will place the code under `/data` and register the service:
```bash
wget https://raw.githubusercontent.com/Spidy01/dbus-canbus-battery/main/install.sh -O install.sh
sh install.sh
```
5) Reboot the device:
```bash
reboot
```
6) After the reboot, verify the service is running:
```bash
ps | grep dbus-canbus
```
You should see something like:

```
root@einstein:~# ps | grep dbus-canbus
  943 root      1768 S    supervise dbus-canbus-battery
  964 root     31948 S    python3 /data/dbus-canbus-battery/dbus-canbus-batter
  966 root      1780 S    multilog t s25000 n4 /var/log/dbus-canbus-battery
 2414 root      2704 S    grep dbus-canbus
```

If you only have the line with `grep dbus-canbus` present then the service is **not** running and you need to troubleshoot why.

# Troubleshooting
First troubleshooting step is to run the `ps | grep dbus-canbus` command as before to ensure the service is running.

**If the service is running:**
- Check the log files by running the command
```bash
cat /var/log/dbus-canbus-battery/current
```
- check for last entries.

**If the service is not running**
You may run into some issues if I've forgotten any dependencies since I started this little project.
Here are some potential fixes that you should execute in Putty session to the Cerbo GX.

- Python Not Installed or Incompatible Version or Missing Dependencies
```bash
python3 --version
```
```bash
opkg update
opkg install python3
```
```bash
pip3 install dbus-python python-can
```
- Manual Service Starting
```bash
python3 /data/dbus-canbus-battery/dbus-canbus-battery.py
```
- View Logs
```bash
tail -f /var/log/dbus-canbus-battery.log
```

# Proof it works :p

![image](https://github.com/user-attachments/assets/80d5c3f2-5052-40a4-8ed3-e2d0ea1e4bf4)
![image](https://github.com/user-attachments/assets/beb02c80-8f72-4fdd-8ef7-7365b3495645)
![image](https://github.com/user-attachments/assets/46888c65-252f-4079-a506-c6ce832cfb14)
![image](https://github.com/user-attachments/assets/d34bb176-06cc-490a-acb8-ef9160207b34)
![image](https://github.com/user-attachments/assets/5ea51a8b-ee6d-4f20-82be-af132e9a9c5b)
![image](https://github.com/user-attachments/assets/6ea3afe3-e531-41ab-941d-b9d1e1be15e6)
![image](https://github.com/user-attachments/assets/c97a0518-9934-4166-92b9-d643666b80d4)
![image](https://github.com/user-attachments/assets/ac5b8bcd-f5f9-442a-aa10-56ca6c4768ac)










