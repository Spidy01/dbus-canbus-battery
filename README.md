# dbus-canbus-battery
Service for Victron ecosystem run on Venus OS which takes CANBUS data from BMS and publishes on dbus.
This is my second github repo, it might even be slightly better than the first!
As such, all information, files, suggestions are to be used at your own risk, I offer zero guarantees implied or otherwise.

# Update 15June2025
* I have made some changes to the python script to include necessary debugging.
* I have updated the method for starting the script and monitoring it's running, rebooting when required.
* I did a factory reinstall with the latest venus image just to be sure that it is starting fresh again. Guide: [Factory Reinstall](https://www.victronenergy.com/media/pg/Cerbo_GX/en/reset-to-factory-defaults-and-venus-os-reinstall.html)

## THIS SOLUTION DOES NOT PERSIST SOFTWARE UPDATES TO THE CERBO GX ##
You will be required to repeat the steps below after each update. If you have some tips on how I can improve this solution to persist updates I'd be very appreciative.
The solution is confirmed working for Venus OS v3.60 on Cerbo GX.

# Background
This solution follows on from the previous project: [Samsung-Victron-ESS](https://github.com/o-snoopy-o/Samsung-Victron-ESS) which utilised an Arduino to capture CANBUS messages and convert them to MQTT messages for victron dbus. This solution eliminates the Arduino and allows the use of the BMS-CAN interface on the Cerbo GX directly. It could however utilise any CANBUS interface on any host system with minor modifications.
From this point forward I will refer to the Venus OS device as Cerbo GX and instructions are for windows users. If there is a need I can also provide the same for Linux users but I think you'll be more than capable to apply to your way of working.



# Quick Start
1) Make a cable that joins the GND,HIGH,LOW pins on your Battery BMS to the Cerbo GX corresponding pins.
2) Enable root account and SSH: [Root Access](https://www.victronenergy.com/live/ccgx:root_access)
3) Access the Cerbo GX through WinSCP.
4) Copy the 'dbus-canbus-battery' folder to: /opt/victronenergy/
5) Copy the 'inittab' file to: /etc/ overwriting the existing.
6) Access the Cerbo GX through Putty and execute the reboot command.
7) Go to the fridge and retrieve a cold beverage.
8) Restart your Putty Session
9) Check the running processes for succesful starting of the service.




# Detailed Guide
1) Make a cable that joins the GND,HIGH,LOW pins on your Battery BMS to the Cerbo GX corresponding pins. GND = Pin 3, CAN-Low = Pin 8, CAN-High = Pin 7. The Samsung BMS in the ELPM482-00005 module uses Pins: GND = Pin 3, CAN-Low = Pin 2, CAN-High = Pin 1. Using CAT5/6 type twisted pair cable is recommended, RJ45 ends are essential to interface with each device. The unused conductors can be cut but it does make insertion into the RJ45 plug difficult. Lubricate the wires prior to insertion using a non-corrosive product designed for such purpose.
Ensure that you have the CANBUS cable connected to the BMS and the Cerbo GX. The port on the Cerbo GX is the BMS-CAN. You must fit a termination resistor to the other port labelled BMS-CAN. On the battery BMS, you may need to flick a switch (in the case of the ELPM482-00005 module the switch is built in and can be enabled by sliding the switch to the right. As a reminder to the Samsung ELPM482-00005 module users, the CANBUS port is the one on the far left of the 4. Also, ensure all the modules have unique ID's, I recommend just connecting 1 module for initial testing.

![image](https://github.com/user-attachments/assets/4ad995dc-184f-4d3c-8e2b-2dd06780d1b7)


2) Follow the guide at the victron site: [Root Access](https://www.victronenergy.com/live/ccgx:root_access)


3) Download WinSCP if you are a windows user and set up a new connection to your Cerbo GX using the root account details you have just created. You should be presented with a list of folders and files. As an example:

![image](https://github.com/user-attachments/assets/529bd6df-8475-4ab9-b38c-ed88c1a92a25)


4) Copy the 'dbus-canbus-battery' folder to: /opt/victronenergy/ . You can drag and drop the files from Windows Explorer or upload through the WinSCP interface. This step creates the folder dbus-canbus-battery and also adds the required files. can-mappings.json defines the canbus registers and the appropriate pairing with the dbus paths. dbus-canbus-battery.py script initiates the canbus listening, data handling and publishing of data onto the dbus.

![image](https://github.com/user-attachments/assets/7dfd3263-62e8-49a0-96ba-b9bb30cdd991)



5) Copy the 'inittab' file to: /etc/ . You now must navigate upwards to the root folder then into the /etc/ folder. Copy the inittab file to this folder. This file ensures that the service will start whenever the Cerbo is rebooted and will ensure the service is restarted should there be any error. The service will not run without this file unless you start it manually with python dbus-canbus-battery.py from within the /opt/victronenergy/ folder.

6) Now set the permissions for the files:
```bash
chmod +x /opt/victronenergy/dbus-canbus-battery/dbus-canbus-battery.py
chmod +x /opt/victronenergy/dbus-canbus-battery/start-delayed.sh
```
   
7) Access the Cerbo GX through Putty and execute the command:
```bash
init q
```
At this time, the inittab will reinitialse and start the battery service script.
If it does not you may need to issue a reboot command:
```bash
reboot
```
8) After the reboot, Issue the command:
```bash
ps | grep dbus-canbus
```
You should see something like this:

root@einstein:~# ps | grep dbus-canbus  
19832 root      2560 T    cat /var/log/dbus-canbus-battery.log  
20155 root      2952 S    {start-delayed.s} /bin/sh /opt/victronenergy/dbus-canbus-battery/start-delayed.sh  
20361 root      2692 S    grep dbus-canbus  

The second line is the startup script, this is currently counting down 180 seconds until main script starting.
If you only have the line with grep dbus-canbus present then the service is NOT running and you need to troubleshoot why. 
![image](https://github.com/user-attachments/assets/0831ab84-918f-45fc-a64b-d4eaf5f1ad3b)


After the 180 seconds have passsed, you can repeat the command `ps | grep dbus-canbus`.
Now you should see the starter script dissapear and the actual script running.
EG: 20155 root     31212 S    /usr/bin/python3 /opt/victronenergy/dbus-canbus-battery/dbus-canbus-battery.py

![image](https://github.com/user-attachments/assets/5a8f1818-5607-44db-a4c4-45ebeb2b8623)

# Troubleshooting
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
python3 /opt/victronenergy/dbus-canbus-battery/dbus-canbus-battery.py
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










