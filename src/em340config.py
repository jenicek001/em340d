#!/usr/bin/env python
import minimalmodbus
import serial
import time
#import yaml # pip install PyYAML
#import sys
#import json
#import paho.mqtt.client as mqtt
#from datetime import date, datetime, timedelta
#from dateutil import tz
# from logger import log

if __name__ == '__main__':
    print('EM340 Configuration')

    em340 = minimalmodbus.Instrument('/dev/ttyUSB0', 1) # port name, slave address (in decimal)
    em340.serial.baudrate = 9600 # Baud
    em340.serial.bytesize = 8
    em340.serial.parity = serial.PARITY_NONE
    em340.serial.stopbits = 1
    em340.serial.timeout = 0.05 # seconds
    em340.serial.timeout = 0.5 # seconds
    em340.mode = minimalmodbus.MODE_RTU # rtu or ascii mode

    measurement_mode = em340.read_register(0x1103)
    print(f'Measurement mode: {measurement_mode}')
    measurement_mode_type = chr(measurement_mode + 65)
    print(f'Measurement mode: {measurement_mode_type}')
    time.sleep(0.1)

    measuring_system = em340.read_register(0x1002)
    print(f'Measurement system: {measuring_system}')
    measurement_system_text = ''
    if measuring_system == 0:
        measurement_system_text = '3-phase 4-wire with neutral'
    elif measuring_system == 1:
        measurement_system_text = '3-phase 3-wire without neutral'
    elif measuring_system == 2:
        measurement_system_text = '2-phase 3-wire'
    elif measuring_system == 3:
        measurement_system_text = '1-phase - only for EM330'
    print(f'Measurement system: {measurement_system_text}')
    time.sleep(0.1)

    # change EM340 measurement mode to B
    print('Changing measurement mode to B')
    em340.write_register(registeraddress=0x1103, value=1, functioncode=6)
    #em340.write_register(0x1103, 1)
    time.sleep(0.1)
    
    # Measuring system = 3-phase 4-wire with neutral
    # print('Changing measuring system to 3-phase 4-wire with neutral')
    #self.em340.write_register(0x1002, 0)
    #time.sleep(0.1)
