# em340d
Simple Daemon to read Carlo Gavazzi EM340 Smart Meter via serial port / RS485 converter using ModBus RTU protocol and send data via MQTT.
With USB-RS485 converter (e.g. https://www.laskakit.cz/prevodnik-usb-rs485--ch340/) it behaves as ModBus Master.
Default ModBus address of EM340 is 1 (exceptionally 2).

em340.yaml config file havily reused from https://github.com/martgras/esphome-modbus/blob/main/em340/EM340.yaml

# Installation
To connect to EM340 it is recommended to check voltage between RS485 pin A and GND and RS485 pin B and GND on both converter and EM340 and connect GND-GND, higher voltage (approx 4V) to higher voltage (A-A) and lower voltage (approx 1V) to lower boltage (B-B).
On EM340 it is necessary to connect to terminating pin.

git clone https://github.com/jenicek001/em340d.git

cd em340

modify individual settings in em340.yaml - Serial port with RS485, MQTT broker, etc.

chmod +x install.sh

sudo ./install.sh

To configure EM340 Smart Meter settings - specifically measurement mode to B, use included tool em340config.py


