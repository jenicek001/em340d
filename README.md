# em340d
Simple Daemon to read Carlo Gavazzi EM340 Smart Meter via serial port / RS485 converter using ModBus RTU protocol and send data via MQTT.

em340.yaml config file havily reused from https://github.com/martgras/esphome-modbus/blob/main/em340/EM340.yaml

# Installation
git clone https://github.com/jenicek001/em340d.git

cd em340

modify individual settings in em340.yaml - Serial port with RS485, MQTT broker, etc.

chmod +x install.sh

sudo ./install.sh

To configure EM340 Smart Meter settings - specifically measurement mode to B, use included tool em340config.py


