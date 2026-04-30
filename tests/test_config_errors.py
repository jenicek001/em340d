#!/usr/bin/env python
"""
Tests for config_loader.py - sensor YAML loading and error handling.
"""
import os
import tempfile
import pytest
from config_loader import load_sensors


def _write_tmp_yaml(content: str) -> str:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(content)
        return f.name


def test_load_valid_sensors():
    """load_sensors returns a list of dicts for a valid YAML file."""
    yaml_content = """
sensors:
  - id: voltage_l1
    name: "Voltage L1-N"
    address: 0x0000
    register_count: 2
    value_type: INT32
    multiply: 0.1
"""
    path = _write_tmp_yaml(yaml_content)
    try:
        sensors = load_sensors(path)
        assert isinstance(sensors, list)
        assert len(sensors) == 1
        assert sensors[0]['id'] == 'voltage_l1'
    finally:
        os.unlink(path)


def test_load_sensors_empty_list():
    """load_sensors returns an empty list when sensors key is empty."""
    yaml_content = "sensors: []\n"
    path = _write_tmp_yaml(yaml_content)
    try:
        sensors = load_sensors(path)
        assert sensors == []
    finally:
        os.unlink(path)


def test_load_sensors_missing_file():
    """load_sensors raises Exception for a non-existent file."""
    with pytest.raises(Exception, match='Error loading sensors file'):
        load_sensors('/nonexistent/path/sensors.yaml')


def test_load_sensors_invalid_yaml():
    """load_sensors raises Exception for malformed YAML."""
    path = _write_tmp_yaml("sensors: [\n  - unclosed bracket\n")
    try:
        with pytest.raises(Exception, match='Error loading sensors file'):
            load_sensors(path)
    finally:
        os.unlink(path)


def test_load_sensors_wrong_type():
    """load_sensors raises ValueError when 'sensors' is not a list."""
    path = _write_tmp_yaml("sensors: not_a_list\n")
    try:
        with pytest.raises(Exception, match='Error loading sensors file'):
            load_sensors(path)
    finally:
        os.unlink(path)


def test_load_sensors_missing_key():
    """load_sensors returns empty list when 'sensors' key is absent (defaults via .get)."""
    path = _write_tmp_yaml("other_key: value\n")
    try:
        sensors = load_sensors(path)
        assert sensors == []
    finally:
        os.unlink(path)

