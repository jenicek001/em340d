#!/usr/bin/env python
import minimalmodbus
import serial
import time
import os
import sys
import json
import paho.mqtt.client as mqtt
from datetime import datetime
from dateutil import tz
from logger import log
from config_loader import load_sensors
from em340_config_manager import EM340ConfigManager

# Base directory of the project (parent of src/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default path for sensor definitions
_DEFAULT_SENSORS_FILE = os.path.join(_BASE_DIR, 'config', 'sensors.yaml')


def _getenv_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        log.warning(f'Invalid value for {name}, using default {default}')
        return default


def _getenv_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        log.warning(f'Invalid value for {name}, using default {default}')
        return default


class EM340:
    def __init__(self):
        log.info('Initializing EM340 ModBus to MQTT Gateway')

        # Runtime configuration from environment variables
        self.device = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')
        self.modbus_address = _getenv_int('MODBUS_ADDRESS', 1)
        self.t_delay_seconds = _getenv_float('DELAY_MS', 50) / 1000.0
        self.polling_interval = _getenv_float('POLLING_INTERVAL_S', 10.0)
        self.serial_number = os.getenv('DEVICE_SERIAL_NUMBER', 'EM340_UNKNOWN')

        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
        self.mqtt_port = _getenv_int('MQTT_PORT', 1883)
        self.mqtt_username = os.getenv('MQTT_USERNAME', '')
        self.mqtt_password = os.getenv('MQTT_PASSWORD', '')
        self.mqtt_topic_base = os.getenv('MQTT_TOPIC', 'em340')

        log.info(
            f'ModBus configuration: device={self.device}, address={self.modbus_address}, '
            f'block_delay={self.t_delay_seconds}s, polling_interval={self.polling_interval}s'
        )

        # Load sensor definitions from static YAML
        sensors_file = os.getenv('SENSORS_FILE', _DEFAULT_SENSORS_FILE)
        try:
            self.sensors = load_sensors(sensors_file)
            log.info(f'Loaded {len(self.sensors)} sensor definitions from {sensors_file}')
        except Exception as e:
            log.error(f'Error loading sensors file: {e}')
            sys.exit(1)

        # Initialize serial connection with retry support
        self._initialize_serial_connection()

    def _initialize_serial_connection(self):
        """Initialize or reinitialize the serial connection to the ModBus device."""
        self.em340 = minimalmodbus.Instrument(self.device, self.modbus_address)
        self.em340.serial.baudrate = 9600
        self.em340.serial.bytesize = 8
        self.em340.serial.parity = serial.PARITY_NONE
        self.em340.serial.stopbits = 1
        self.em340.serial.timeout = 0.5
        self.em340.mode = minimalmodbus.MODE_RTU

        log.info(f'ModBus instrument configured: port={self.device}, baudrate=9600, timeout=0.5s')

        # MQTT client setup with automatic reconnection
        log.info(f'Setting up MQTT client for broker: {self.mqtt_broker}:{self.mqtt_port}')
        self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)
        self.topic = f'{self.mqtt_topic_base}/{self.serial_number}'
        log.info(f'MQTT topic configured: {self.topic}')
        self.mqtt_client.loop_start()
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port)
            log.info('MQTT initial connection attempt initiated')
        except Exception as e:
            log.error(f'Initial MQTT connection failed: {e}')

        # Initialize configuration manager
        self._initialize_config_manager()

    def _initialize_config_manager(self):
        """Initialize the configuration manager for MQTT-based device configuration."""
        config_mqtt_config = {
            'broker': self.mqtt_broker,
            'port': self.mqtt_port,
            'username': self.mqtt_username,
            'password': self.mqtt_password,
            'topic': self.mqtt_topic_base,
            'device_id': self.serial_number,
        }

        self.config_manager = EM340ConfigManager(
            config_mqtt_config,
            self.device,
            self.modbus_address,
        )

        if self.config_manager.start_config_service():
            log.info('EM340 configuration service started successfully')
        else:
            log.warning('Failed to start EM340 configuration service')

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            log.info('Connected to MQTT broker.')
        else:
            log.error(f'Failed to connect to MQTT broker, return code {reason_code}')

    def on_mqtt_disconnect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            log.warning('Unexpected MQTT disconnection. Will attempt to reconnect.')
        else:
            log.info('MQTT client disconnected.')

    def _reconnect_serial_device(self, max_retries=None, base_delay=2.0, max_delay=60.0):
        """
        Attempt to reconnect to the serial device with exponential backoff.

        Args:
            max_retries: Maximum number of retry attempts (None for infinite).
            base_delay: Initial delay between retries in seconds.
            max_delay: Maximum delay between retries in seconds.

        Returns:
            True if reconnection successful, False otherwise.
        """
        retry_count = 0
        delay = base_delay

        while max_retries is None or retry_count < max_retries:
            retry_count += 1
            log.warning(f'Serial device disconnected. Attempting reconnection (attempt {retry_count})...')

            try:
                if hasattr(self.em340, 'serial') and hasattr(self.em340.serial, 'is_open'):
                    try:
                        if self.em340.serial.is_open:
                            self.em340.serial.close()
                            log.info('Closed old serial connection')
                    except Exception:
                        pass

                log.info(f'Waiting {delay:.1f}s before reconnection attempt...')
                time.sleep(delay)

                if not os.path.exists(self.device):
                    log.error(f'Device file {self.device} does not exist')
                    delay = min(delay * 1.5, max_delay)
                    continue

                self._initialize_serial_connection()

                log.info('Testing connection by reading device measurement mode...')
                measurement_mode = self.em340.read_register(0x1103)
                measurement_mode_type = chr(measurement_mode + 65)
                log.info(f'Connection successful! Measurement mode: {measurement_mode_type}')
                return True

            except serial.SerialException as e:
                log.error(f'Serial connection failed: {e}')
            except IOError as e:
                log.error(f'ModBus communication failed: {e}')
            except Exception as e:
                log.error(f'Unexpected error during reconnection: {e}')

            delay = min(delay * 1.5, max_delay)

        log.error(f'Failed to reconnect after {retry_count} attempts')
        return False

    def read_sensors(self):
        """Main polling loop: read all sensors and publish to MQTT, then sleep for polling_interval."""
        # Group contiguous registers into blocks for efficient reading
        sensors = [r for r in self.sensors if not r.get('skip', False)]
        sensors.sort(key=lambda r: r['address'])

        # Build blocks of contiguous registers
        blocks = []
        current_block = []
        max_block_size = 20
        max_gap = 5

        for sensor in sensors:
            if not current_block:
                current_block = [sensor]
                continue

            prev_sensor = current_block[-1]
            prev_end_addr = prev_sensor['address'] + prev_sensor.get('register_count', 1)
            current_start_addr = sensor['address']
            gap = current_start_addr - prev_end_addr
            total_regs_needed = sensor['address'] + sensor.get('register_count', 1) - current_block[0]['address']

            if gap < 0 or gap > max_gap or total_regs_needed > max_block_size:
                blocks.append(current_block)
                current_block = [sensor]
            else:
                current_block.append(sensor)

        if current_block:
            blocks.append(current_block)

        log.info(f'Organised {len(sensors)} sensors into {len(blocks)} ModBus read blocks:')
        for i, block in enumerate(blocks):
            start_addr = block[0]['address']
            end_addr = block[-1]['address'] + block[-1].get('register_count', 1)
            total_regs = end_addr - start_addr
            sensor_names = [s['name'] for s in block]
            log.info(f'  Block {i + 1}: 0x{start_addr:04X}-0x{end_addr - 1:04X} ({total_regs} regs) - {", ".join(sensor_names)}')

        while True:
            log.debug('Reading EM340...')
            data = {}
            for block in blocks:
                start_addr = block[0]['address']
                end_addr = block[-1]['address'] + block[-1].get('register_count', 1)
                total_regs = end_addr - start_addr

                try:
                    log.debug(f'Reading block: 0x{start_addr:04X} to 0x{end_addr - 1:04X} ({total_regs} registers)')
                    values = self.em340.read_registers(start_addr, number_of_registers=total_regs)
                    if values is None or len(values) != total_regs:
                        raise ValueError(
                            f'Expected {total_regs} values for block starting at {hex(start_addr)}, '
                            f'got {len(values) if values else 0}'
                        )

                    for sensor in block:
                        sensor_start = sensor['address'] - start_addr
                        reg_count = sensor.get('register_count', 1)
                        sensor_values = values[sensor_start:sensor_start + reg_count]

                        if len(sensor_values) != reg_count:
                            log.warning(f'Sensor {sensor["name"]} expected {reg_count} registers, got {len(sensor_values)}')
                            continue

                        value = None
                        vt = sensor['value_type']
                        if vt == 'INT16':
                            value = sensor_values[0]
                            if value & 0x8000:
                                value = -0x10000 + value
                        elif vt == 'UINT16':
                            value = sensor_values[0]
                        elif vt == 'INT32':
                            if len(sensor_values) >= 2:
                                value = sensor_values[0] + (sensor_values[1] << 16)
                                if value & 0x80000000:
                                    value = -0x100000000 + value
                            else:
                                log.error(f'INT32 sensor {sensor["name"]} needs 2 registers, got {len(sensor_values)}')
                                continue
                        elif vt == 'UINT32':
                            if len(sensor_values) >= 2:
                                value = sensor_values[0] + (sensor_values[1] << 16)
                            else:
                                log.error(f'UINT32 sensor {sensor["name"]} needs 2 registers, got {len(sensor_values)}')
                                continue
                        elif vt == 'INT64':
                            if len(sensor_values) >= 4:
                                value = (
                                    sensor_values[0]
                                    + (sensor_values[1] << 16)
                                    + (sensor_values[2] << 32)
                                    + (sensor_values[3] << 48)
                                )
                                if value & 0x8000000000000000:
                                    value = -0x10000000000000000 + value
                            else:
                                log.error(f'INT64 sensor {sensor["name"]} needs 4 registers, got {len(sensor_values)}')
                                continue
                        elif vt == 'UINT64':
                            if len(sensor_values) >= 4:
                                value = (
                                    sensor_values[0]
                                    + (sensor_values[1] << 16)
                                    + (sensor_values[2] << 32)
                                    + (sensor_values[3] << 48)
                                )
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
                    log.warning('Attempting to reconnect to serial device...')
                    if self._reconnect_serial_device():
                        log.info('Successfully reconnected to serial device. Resuming operations.')
                        continue
                    else:
                        log.error('Failed to reconnect to serial device. Will retry on next iteration.')
                        break
                except serial.SerialException as err:
                    log.error(f'Serial communication error: {err}')
                    log.warning('Serial exception detected. Attempting to reconnect...')
                    if self._reconnect_serial_device():
                        log.info('Successfully reconnected after serial exception. Resuming operations.')
                        continue
                    else:
                        log.error('Failed to reconnect after serial exception. Will retry on next iteration.')
                        break
                except ValueError as err:
                    log.error(f'Error reading block starting at 0x{start_addr:04X}: {err}')
                    continue
                except KeyError as err:
                    log.error(f'Error in sensor definition: {err}')
                    sys.exit(1)
                except KeyboardInterrupt:
                    log.info('Keyboard interrupt detected. Exiting...')
                    if hasattr(self, 'config_manager'):
                        self.config_manager.stop_config_service()
                    sys.exit(0)
                finally:
                    time.sleep(self.t_delay_seconds)

            # Add timestamp in local time
            data['last_seen'] = datetime.now(tz=tz.tzlocal()).isoformat()

            # Publish data to MQTT
            payload = json.dumps(data)
            try:
                result = self.mqtt_client.publish(self.topic, payload)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    log.warning(f'MQTT publish failed with code {result.rc}')
            except Exception as e:
                log.error(f'Error publishing to MQTT: {e}')

            # Sleep until next polling cycle
            log.debug(f'Sleeping {self.polling_interval}s until next polling cycle...')
            time.sleep(self.polling_interval)


if __name__ == '__main__':
    log.info('=== Starting EM340D ModBus to MQTT Gateway ===')
    em340 = EM340()
    log.info('EM340 instance created successfully')
    log.info('Beginning sensor polling loop...')
    em340.read_sensors()
