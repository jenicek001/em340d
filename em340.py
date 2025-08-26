#!/usr/bin/env python
import minimalmodbus
import serial
import time
import yaml # pip install PyYAML
import sys
import json
import paho.mqtt.client as mqtt
from datetime import date, datetime, timedelta
from dateutil import tz
from logger import log

class EM340:
    def __init__(self, config_file):
        try:
            self.em340_config = yaml.load(open(config_file), Loader=yaml.FullLoader)
        except Exception as e:
            log.error(f'Error loading YAML file: {e}')
            sys.exit()

        self.device = self.em340_config['config']['device']
        self.modbus_address = self.em340_config['config']['modbus_address']
        self.t_delay_seconds = self.em340_config['config']['t_delay_ms'] / 1000.0

        self.em340 = minimalmodbus.Instrument(self.device, self.modbus_address) # port name, slave address (in decimal)
        self.em340.serial.port # this is the serial port name
        self.em340.serial.baudrate = 9600 # Baud
        self.em340.serial.bytesize = 8
        self.em340.serial.parity = serial.PARITY_NONE
        self.em340.serial.stopbits = 1
        #self.em340.serial.timeout = 0.05 # seconds
        self.em340.serial.timeout = 0.5 # seconds
        self.em340.mode = minimalmodbus.MODE_RTU # rtu or ascii mode

        # MQTT client setup with automatic reconnection
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(self.em340_config['mqtt']['username'], self.em340_config['mqtt']['password'])
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)
        self.topic = self.em340_config['mqtt']['topic'] + '/' + self.em340_config['config']['name']
        # Start network loop in background thread
        self.mqtt_client.loop_start()
        # Try initial connection
        try:
            self.mqtt_client.connect(self.em340_config['mqtt']['broker'], self.em340_config['mqtt']['port'])
        except Exception as e:
            log.error(f'Initial MQTT connection failed: {e}')

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info('Connected to MQTT broker.')
        else:
            log.error(f'Failed to connect to MQTT broker, return code {rc}')

    def on_mqtt_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning('Unexpected MQTT disconnection. Will attempt to reconnect.')
        else:
            log.info('MQTT client disconnected.')

        # TODO send to MQTT to a different subtopic
        measurement_mode = self.em340.read_register(0x1103)
        measurement_mode_type = chr(measurement_mode + 65)
        log.info(f'Measurement mode: {measurement_mode_type}')
        time.sleep(0.1)

        # TODO send to MQTT to a different subtopic
        measuring_system = self.em340.read_register(0x1002)
        measurement_system_text = ''
        if measuring_system == 0:
            measurement_system_text = '3-phase 4-wire with neutral'
        elif measuring_system == 1:
            measurement_system_text = '3-phase 3-wire without neutral'
        elif measuring_system == 2:
            measurement_system_text = '2-phase 3-wire'
        elif measuring_system == 3:
            measurement_system_text = '1-phase - only for EM330'
        log.info(f'Measurement system: {measurement_system_text}')
        time.sleep(0.1)

        # change EM340 measurement mode to B
        #self.em340.write_register(0x1103, 1)
        #time.sleep(0.1)
        
        # Measuring system = 3-phase 4-wire with neutral
        #self.em340.write_register(0x1002, 0)
        #time.sleep(0.1)

    def read_sensors(self):
        # Group contiguous registers into blocks for efficient reading
        sensors = [r for r in self.em340_config['sensor'] if not r.get('skip', False)]
        sensors.sort(key=lambda r: r['address'])

        # Build blocks of contiguous registers
        blocks = []
        block = []
        max_block_size = 20  # EM340 typically allows up to 20 registers per read
        for sensor in sensors:
            if not block:
                block = [sensor]
                continue
            prev = block[-1]
            prev_end = prev['address'] + prev.get('register_count', 1)
            if sensor['address'] == prev_end and len(block) < max_block_size:
                block.append(sensor)
            else:
                blocks.append(block)
                block = [sensor]
        if block:
            blocks.append(block)

        while True:
            log.debug('Reading EM340...')
            data = {}
            for block in blocks:
                start_addr = block[0]['address']
                total_regs = sum(s.get('register_count', 1) for s in block)
                try:
                    values = self.em340.read_registers(start_addr, number_of_registers=total_regs)
                    if values is None:
                        raise ValueError(f"Missing values for block starting at {hex(start_addr)}")
                    idx = 0
                    for sensor in block:
                        reg_count = sensor.get('register_count', 1)
                        sensor_values = values[idx:idx+reg_count]
                        idx += reg_count
                        value = None
                        vt = sensor['value_type']
                        if vt == "INT16":
                            value = sensor_values[0]
                            if value & 0x8000:
                                value = -0x10000 + value
                        elif vt == "UINT16":
                            value = sensor_values[0]
                        elif vt == "INT32":
                            value = sensor_values[0] + (sensor_values[1] << 16)
                            if value & 0x80000000:
                                value = -0x100000000 + value
                        elif vt == "UINT32":
                            value = sensor_values[0] + (sensor_values[1] << 16)
                        elif vt == "INT64":
                            value = sensor_values[0] + (sensor_values[1] << 16) + (sensor_values[2] << 32) + (sensor_values[3] << 48)
                            if value & 0x8000000000000000:
                                value = -0x10000000000000000 + value
                        elif vt == "UINT64":
                            value = sensor_values[0] + (sensor_values[1] << 16) + (sensor_values[2] << 32) + (sensor_values[3] << 48)
                        value = value * float(sensor['multiply'])
                        units = sensor.get('unit_of_measurement', '')
                        log.debug(f'{sensor["name"]} {value} {units}')
                        data[sensor['id']] = value
                    time.sleep(self.t_delay_seconds)
                except IOError as err:
                    log.error(f'Failed to read from ModBus device at {self.em340.serial.port}: {err}')
                except ValueError as err:
                    log.error(f'Error reading block: {err}')
                except KeyError as err:
                    log.error(f'Error in yaml config file: {err}')
                    sys.exit()
                except KeyboardInterrupt:
                    log.error("Keyboard interrupt detected. Exiting...")
                    sys.exit()

            # Add timestamp in local time as last_seen
            data['last_seen'] = datetime.now(tz=tz.tzlocal()).isoformat()

            # Optionally read a large block for diagnostics
            try:
                regs = self.em340.read_registers(registeraddress=0x0028, number_of_registers=20)
                data['all_registers_address'] = 0x0028
                data['all_registers'] = regs
            except Exception as err:
                log.error(f'Error reading all registers block: {err}')
            time.sleep(self.t_delay_seconds)

            # Publish data to MQTT topic
            payload = json.dumps(data)
            try:
                result = self.mqtt_client.publish(self.topic, payload)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    log.warning(f'MQTT publish failed with code {result.rc}')
            except Exception as e:
                log.error(f'Error publishing to MQTT: {e}')

if __name__ == '__main__':
    log.info('Starting EM340d...')
    em340 = EM340('em340.yaml')
    em340.read_sensors()
