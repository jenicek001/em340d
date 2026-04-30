#!/usr/bin/env python
"""
Tests for EM340 class initialisation with invalid / missing configuration.
Hardware (serial port, MQTT broker) is fully mocked.
"""
import os
import tempfile
import pytest
import unittest.mock as mock


def _make_em340(env_overrides=None, sensors_yaml=None):
    """
    Import and instantiate EM340 with hardware mocked out.
    env_overrides: dict of env vars to set for the test.
    sensors_yaml: content of a temporary sensors.yaml (uses a minimal valid one by default).
    """
    default_sensors = (
        "sensors:\n"
        "  - id: voltage_l1\n"
        "    name: Voltage L1-N\n"
        "    address: 0x0000\n"
        "    register_count: 2\n"
        "    value_type: INT32\n"
        "    multiply: 0.1\n"
        "    skip: false\n"
    )
    if sensors_yaml is None:
        sensors_yaml = default_sensors

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(sensors_yaml)
        sensors_path = f.name

    env = {
        'SERIAL_DEVICE': '/dev/ttyUSB0',
        'MODBUS_ADDRESS': '1',
        'DELAY_MS': '50',
        'POLLING_INTERVAL_S': '10',
        'DEVICE_SERIAL_NUMBER': 'TEST123A',
        'MQTT_BROKER': 'localhost',
        'MQTT_PORT': '1883',
        'MQTT_USERNAME': '',
        'MQTT_PASSWORD': '',
        'MQTT_TOPIC': 'em340',
        'SENSORS_FILE': sensors_path,
    }
    if env_overrides:
        env.update(env_overrides)

    with mock.patch.dict(os.environ, env, clear=False):
        with mock.patch('minimalmodbus.Instrument'):
            with mock.patch('paho.mqtt.client.Client') as mock_mqtt:
                mock_mqtt.return_value.connect.return_value = None
                mock_mqtt.return_value.loop_start.return_value = None
                with mock.patch('em340_config_manager.EM340ConfigManager') as mock_cm:
                    mock_cm.return_value.start_config_service.return_value = True
                    import importlib
                    import em340 as em340_mod
                    importlib.reload(em340_mod)
                    instance = em340_mod.EM340()

    os.unlink(sensors_path)
    return instance


def test_em340_init_defaults():
    """EM340 initialises successfully with valid env vars and a mocked sensor file."""
    instance = _make_em340()
    assert instance.device == '/dev/ttyUSB0'
    assert instance.modbus_address == 1
    assert instance.polling_interval == 10.0
    assert instance.serial_number == 'TEST123A'


def test_em340_polling_interval_from_env():
    """POLLING_INTERVAL_S env var is read correctly."""
    instance = _make_em340({'POLLING_INTERVAL_S': '30'})
    assert instance.polling_interval == 30.0


def test_em340_bad_polling_interval_falls_back_to_default():
    """An invalid POLLING_INTERVAL_S uses the default value."""
    instance = _make_em340({'POLLING_INTERVAL_S': 'not_a_number'})
    assert instance.polling_interval == 10.0


def test_em340_missing_sensors_file_exits():
    """EM340 calls sys.exit when the sensors file does not exist."""
    env = {
        'SERIAL_DEVICE': '/dev/ttyUSB0',
        'MODBUS_ADDRESS': '1',
        'DELAY_MS': '50',
        'POLLING_INTERVAL_S': '10',
        'DEVICE_SERIAL_NUMBER': 'TEST',
        'MQTT_BROKER': 'localhost',
        'MQTT_PORT': '1883',
        'MQTT_USERNAME': '',
        'MQTT_PASSWORD': '',
        'MQTT_TOPIC': 'em340',
        'SENSORS_FILE': '/nonexistent/sensors.yaml',
    }
    with mock.patch.dict(os.environ, env, clear=False):
        with mock.patch('minimalmodbus.Instrument'):
            with mock.patch('paho.mqtt.client.Client'):
                import importlib
                import em340 as em340_mod
                importlib.reload(em340_mod)
                with pytest.raises(SystemExit):
                    em340_mod.EM340()

