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
from config_loader import load_yaml_with_env

class EM340:
    def __init__(self, config_file):
        log.info(f'Initializing EM340 with config file: {config_file}')
        try:
            self.em340_config = load_yaml_with_env(config_file)
            log.info('Configuration loaded successfully')
        except Exception as e:
            log.error(f'Error loading YAML file: {e}')
            sys.exit()

        self.device = self.em340_config['config']['device']
        self.modbus_address = self.em340_config['config']['modbus_address']
        self.t_delay_seconds = self.em340_config['config']['t_delay_ms'] / 1000.0
        
        log.info(f'ModBus configuration: device={self.device}, address={self.modbus_address}, delay={self.t_delay_seconds}s')

        self.em340 = minimalmodbus.Instrument(self.device, self.modbus_address) # port name, slave address (in decimal)
        self.em340.serial.port # this is the serial port name
        self.em340.serial.baudrate = 9600 # Baud
        self.em340.serial.bytesize = 8
        self.em340.serial.parity = serial.PARITY_NONE
        self.em340.serial.stopbits = 1
        #self.em340.serial.timeout = 0.05 # seconds
        self.em340.serial.timeout = 0.5 # seconds
        self.em340.mode = minimalmodbus.MODE_RTU # rtu or ascii mode
        
        log.info(f'ModBus instrument configured: port={self.device}, baudrate=9600, timeout=0.5s')

        # MQTT client setup with automatic reconnection
        log.info(f'Setting up MQTT client for broker: {self.em340_config["mqtt"]["broker"]}:{self.em340_config["mqtt"]["port"]}')
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(self.em340_config['mqtt']['username'], self.em340_config['mqtt']['password'])
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)
        self.topic = self.em340_config['mqtt']['topic'] + '/' + self.em340_config['config']['name']
        log.info(f'MQTT topic configured: {self.topic}')
        # Start network loop in background thread
        self.mqtt_client.loop_start()
        # Try initial connection
        try:
            self.mqtt_client.connect(self.em340_config['mqtt']['broker'], self.em340_config['mqtt']['port'])
            log.info('MQTT initial connection attempt initiated')
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
        current_block = []
        max_block_size = 20  # EM340 typically allows up to 20 registers per read
        max_gap = 5  # Maximum gap between registers to still consider them in the same block
        
        for sensor in sensors:
            if not current_block:
                current_block = [sensor]
                continue
                
            prev_sensor = current_block[-1]
            prev_end_addr = prev_sensor['address'] + prev_sensor.get('register_count', 1)
            current_start_addr = sensor['address']
            gap = current_start_addr - prev_end_addr
            
            # Calculate total registers needed if we add this sensor to current block
            total_regs_needed = sensor['address'] + sensor.get('register_count', 1) - current_block[0]['address']
            
            # Start new block if:
            # - Gap is too large (inefficient to read empty registers)
            # - Block would exceed max size
            # - Gap is negative (overlapping - shouldn't happen but safety check)
            if gap < 0 or gap > max_gap or total_regs_needed > max_block_size:
                blocks.append(current_block)
                current_block = [sensor]
            else:
                current_block.append(sensor)
                
        if current_block:
            blocks.append(current_block)

        # Log block organization for debugging
        log.info(f'Organized {len(sensors)} sensors into {len(blocks)} blocks:')
        for i, block in enumerate(blocks):
            start_addr = block[0]['address']
            end_addr = block[-1]['address'] + block[-1].get('register_count', 1)
            total_regs = end_addr - start_addr
            sensor_names = [s['name'] for s in block]
            log.info(f'  Block {i+1}: 0x{start_addr:04X}-0x{end_addr-1:04X} ({total_regs} regs) - {", ".join(sensor_names)}')

        while True:
            log.debug('Reading EM340...')
            data = {}
            for block in blocks:
                start_addr = block[0]['address']
                end_addr = block[-1]['address'] + block[-1].get('register_count', 1)
                total_regs = end_addr - start_addr
                
                try:
                    log.debug(f'Reading block: 0x{start_addr:04X} to 0x{end_addr-1:04X} ({total_regs} registers)')
                    values = self.em340.read_registers(start_addr, number_of_registers=total_regs)
                    if values is None or len(values) != total_regs:
                        raise ValueError(f"Expected {total_regs} values for block starting at {hex(start_addr)}, got {len(values) if values else 0}")
                    
                    # Process each sensor in the block
                    for sensor in block:
                        sensor_start = sensor['address'] - start_addr  # Offset within the block
                        reg_count = sensor.get('register_count', 1)
                        sensor_values = values[sensor_start:sensor_start + reg_count]
                        
                        if len(sensor_values) != reg_count:
                            log.warning(f'Sensor {sensor["name"]} expected {reg_count} registers, got {len(sensor_values)}')
                            continue
                            
                        value = None
                        vt = sensor['value_type']
                        if vt == "INT16":
                            value = sensor_values[0]
                            if value & 0x8000:
                                value = -0x10000 + value
                        elif vt == "UINT16":
                            value = sensor_values[0]
                        elif vt == "INT32":
                            if len(sensor_values) >= 2:
                                value = sensor_values[0] + (sensor_values[1] << 16)
                                if value & 0x80000000:
                                    value = -0x100000000 + value
                            else:
                                log.error(f'INT32 sensor {sensor["name"]} needs 2 registers, got {len(sensor_values)}')
                                continue
                        elif vt == "UINT32":
                            if len(sensor_values) >= 2:
                                value = sensor_values[0] + (sensor_values[1] << 16)
                            else:
                                log.error(f'UINT32 sensor {sensor["name"]} needs 2 registers, got {len(sensor_values)}')
                                continue
                        elif vt == "INT64":
                            if len(sensor_values) >= 4:
                                value = sensor_values[0] + (sensor_values[1] << 16) + (sensor_values[2] << 32) + (sensor_values[3] << 48)
                                if value & 0x8000000000000000:
                                    value = -0x10000000000000000 + value
                            else:
                                log.error(f'INT64 sensor {sensor["name"]} needs 4 registers, got {len(sensor_values)}')
                                continue
                        elif vt == "UINT64":
                            if len(sensor_values) >= 4:
                                value = sensor_values[0] + (sensor_values[1] << 16) + (sensor_values[2] << 32) + (sensor_values[3] << 48)
                            else:
                                log.error(f'UINT64 sensor {sensor["name"]} needs 4 registers, got {len(sensor_values)}')
                                continue
                        else:
                            log.error(f'Unknown value_type {vt} for sensor {sensor["name"]}')
                            continue
                            
                        value = value * float(sensor['multiply'])
                        units = sensor.get('unit_of_measurement', '')
                        log.debug(f'{sensor["name"]} (0x{sensor["address"]:04X}): {value} {units}')
                        data[sensor['id']] = value
                        
                except IOError as err:
                    log.error(f'Failed to read from ModBus device at {self.em340.serial.port}: {err}')
                    # For IOError, continue to next block - might be temporary communication issue
                    continue
                except ValueError as err:
                    log.error(f'Error reading block starting at 0x{start_addr:04X}: {err}')
                    continue
                except KeyError as err:
                    log.error(f'Error in yaml config file: {err}')
                    sys.exit()
                except KeyboardInterrupt:
                    log.error("Keyboard interrupt detected. Exiting...")
                    sys.exit()
                finally:
                    # Add delay between blocks to avoid overwhelming the device
                    time.sleep(self.t_delay_seconds)

            # Add timestamp in local time as last_seen
            data['last_seen'] = datetime.now(tz=tz.tzlocal()).isoformat()

            # Publish data to MQTT topic
            payload = json.dumps(data)
            try:
                result = self.mqtt_client.publish(self.topic, payload)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    log.warning(f'MQTT publish failed with code {result.rc}')
            except Exception as e:
                log.error(f'Error publishing to MQTT: {e}')

if __name__ == '__main__':
    log.info('=== Starting EM340D ModBus to MQTT Gateway ===')
    log.info('Application startup initiated')
    em340 = EM340('em340.yaml')
    log.info('EM340 instance created successfully')
    log.info('Beginning sensor reading loop...')
    em340.read_sensors()
