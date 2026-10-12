#!/usr/bin/env python
"""EM340 ModBus to MQTT gateway.

Every Modbus request goes through one ModbusBus (#12): it serialises the requests, keeps the meter's
turnaround between them, retries a read once and reopens the port by itself after a failure. This module
only decides what to read and publishes it:
- the regular poll: the sensor blocks of config/sensors.yaml on em340/<serial>, every POLLING_INTERVAL_S;
- at each quarter-hour boundary, first: the energy totals on em340/<serial>/interval, retained (#6).
"""
import json
import os
import sys
import time
from datetime import datetime

import paho.mqtt.client as mqtt
import serial
from dateutil import tz

from config_loader import load_sensors
from em340_config_manager import EM340ConfigManager
from energy import EnergyReader, QuarterHourSnapshots, clock_synchronized, snapshot_payload, wall_clock
from logger import log
from modbus_bus import HIGH, BusUnavailable, ModbusBus, serial_instrument_factory

# Base directory of the project (parent of src/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default path for sensor definitions
_DEFAULT_SENSORS_FILE = os.path.join(_BASE_DIR, 'config', 'sensors.yaml')

MAX_BLOCK_SIZE = 20
MAX_GAP = 5


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


def build_blocks(sensors, max_block_size: int = MAX_BLOCK_SIZE, max_gap: int = MAX_GAP):
    """Contiguous sensors grouped into read blocks: one request per block."""
    sensors = sorted((s for s in sensors if not s.get('skip', False)), key=lambda r: r['address'])
    blocks, current = [], []
    for sensor in sensors:
        if current:
            prev = current[-1]
            gap = sensor['address'] - (prev['address'] + prev.get('register_count', 1))
            needed = sensor['address'] + sensor.get('register_count', 1) - current[0]['address']
            if gap < 0 or gap > max_gap or needed > max_block_size:
                blocks.append(current)
                current = []
        current.append(sensor)
    if current:
        blocks.append(current)
    return blocks


def block_span(block):
    start = block[0]['address']
    return start, block[-1]['address'] + block[-1].get('register_count', 1) - start


def _words(values, signed_bits):
    value = 0
    for i, word in enumerate(values):
        value += word << (16 * i)
    if signed_bits and value & (1 << (signed_bits - 1)):
        value -= 1 << signed_bits
    return value


_TYPES = {'INT16': (1, 16), 'UINT16': (1, 0), 'INT32': (2, 32), 'UINT32': (2, 0), 'INT64': (4, 64), 'UINT64': (4, 0)}


def decode_value(sensor, values):
    """One sensor's value from its registers (least significant word first), times its multiplier."""
    vt = sensor['value_type']
    if vt not in _TYPES:
        raise ValueError(f'Unknown value_type {vt} for sensor {sensor["name"]}')
    count, signed_bits = _TYPES[vt]
    if len(values) < count:
        raise ValueError(f'{vt} sensor {sensor["name"]} needs {count} registers, got {len(values)}')
    return _words(values[:count], signed_bits) * float(sensor['multiply'])


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
            f'turnaround={self.t_delay_seconds}s, polling_interval={self.polling_interval}s'
        )

        # Load sensor definitions from static YAML
        sensors_file = os.getenv('SENSORS_FILE', _DEFAULT_SENSORS_FILE)
        try:
            self.sensors = load_sensors(sensors_file)
            log.info(f'Loaded {len(self.sensors)} sensor definitions from {sensors_file}')
        except Exception as e:
            log.error(f'Error loading sensors file: {e}')
            sys.exit(1)

        # The one owner of the serial port (#12)
        self.bus = ModbusBus(self.device, turnaround_s=self.t_delay_seconds,
                             instrument_factory=serial_instrument_factory(timeout_s=0.5))
        self.bus.start()

        self._initialize_mqtt()
        self._initialize_config_manager()

        # Energy at 1 Wh resolution and the quarter-hour snapshots (issue #6)
        self.energy = EnergyReader(self.bus, self.modbus_address)
        self.snapshots = QuarterHourSnapshots(wall_clock())
        self.interval_topic = f'{self.mqtt_topic_base}/{self.serial_number}/interval'
        synced = clock_synchronized()
        if synced is False:
            log.warning('The system clock is NOT synchronised (NTP): quarter-hour snapshots will be off by its error')
        else:
            log.info(f'Quarter-hour energy snapshots on {self.interval_topic}; clock synchronised: {synced}')

    def _initialize_mqtt(self):
        """Once, at start: the MQTT client reconnects by itself (paho), independently of the serial port."""
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

    # --- quarter-hour snapshots (#6) ---------------------------------------------------------------------

    def _publish_due_snapshot(self):
        """At a quarter-hour boundary: read the energy totals (first in the bus queue) and publish them retained."""
        boundary = self.snapshots.due(wall_clock())
        if boundary is None:
            return
        try:
            imp, exp, resolution = self.energy.read(priority=HIGH)
        except (IOError, ValueError, TimeoutError, serial.SerialException) as err:
            log.error(f'Quarter-hour snapshot not read: {err}')
            return
        payload = snapshot_payload(boundary, wall_clock(), imp, exp, resolution, self.serial_number, self.snapshots.seq)
        if payload['read_delay_ms'] > 5000:
            log.warning(f'Quarter-hour snapshot read {payload["read_delay_ms"]} ms after the boundary')
        try:
            result = self.mqtt_client.publish(self.interval_topic, json.dumps(payload), qos=1, retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning(f'MQTT publish of the quarter-hour snapshot failed with code {result.rc}')
        except Exception as e:
            log.error(f'Error publishing the quarter-hour snapshot: {e}')

    def _add_fine_totals(self, data: dict):
        """The regular message's total_energy_import/export at the best resolution (same names, kWh)."""
        try:
            imp, exp, _ = self.energy.read()
        except (IOError, ValueError, TimeoutError, serial.SerialException) as err:
            log.warning(f'Energy totals not read at 1 Wh resolution: {err}')
            return
        data['total_energy_import'] = imp
        data['total_energy_export'] = exp

    def _sleep_until_next_cycle(self):
        """The polling interval, or less: wake just after the next quarter-hour boundary."""
        to_boundary = self.snapshots.seconds_to_next(wall_clock()) + 0.01
        time.sleep(min(self.polling_interval, to_boundary))

    # --- the regular poll --------------------------------------------------------------------------------

    def poll_once(self, blocks) -> dict:
        """Read every block through the bus; a block that fails is left out of this message."""
        data = {}
        for block in blocks:
            start, count = block_span(block)
            try:
                values = self.bus.read_registers(self.modbus_address, start, count)
                if values is None or len(values) != count:
                    raise ValueError(f'expected {count} values, got {len(values) if values else 0}')
            except BusUnavailable as err:
                log.error(f'Modbus bus unavailable: {err}')     # the bus reopens the port by itself
                break
            except (IOError, ValueError, TimeoutError) as err:
                log.error(f'Block 0x{start:04X} ({count} registers) not read: {err}')
                continue
            for sensor in block:
                offset = sensor['address'] - start
                try:
                    data[sensor['id']] = decode_value(sensor, values[offset:offset + sensor.get('register_count', 1)])
                except ValueError as err:
                    log.error(str(err))
        return data

    def read_sensors(self):
        """Main loop: the quarter-hour snapshot when due, the poll, publish, sleep."""
        blocks = build_blocks(self.sensors)
        log.info(f'Organised {sum(len(b) for b in blocks)} sensors into {len(blocks)} ModBus read blocks:')
        for i, block in enumerate(blocks):
            start, count = block_span(block)
            log.info(f'  Block {i + 1}: 0x{start:04X}-0x{start + count - 1:04X} ({count} regs) - '
                     f'{", ".join(s["name"] for s in block)}')

        try:
            while True:
                self._publish_due_snapshot()
                data = self.poll_once(blocks)
                self._add_fine_totals(data)
                data['last_seen'] = datetime.now(tz=tz.tzlocal()).isoformat()
                try:
                    result = self.mqtt_client.publish(self.topic, json.dumps(data))
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        log.warning(f'MQTT publish failed with code {result.rc}')
                except Exception as e:
                    log.error(f'Error publishing to MQTT: {e}')
                self._sleep_until_next_cycle()
        except KeyboardInterrupt:
            log.info('Keyboard interrupt detected. Exiting...')
            self.config_manager.stop_config_service()
            self.bus.stop()


if __name__ == '__main__':
    log.info('=== Starting EM340D ModBus to MQTT Gateway ===')
    em340 = EM340()
    log.info('EM340 instance created successfully')
    log.info('Beginning sensor polling loop...')
    em340.read_sensors()
