#!/usr/bin/env python
"""
Test script to verify ModBus register block organisation
"""
import os
from config_loader import load_sensors

# Locate sensors.yaml relative to the project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SENSORS_FILE = os.path.join(_PROJECT_ROOT, 'config', 'sensors.yaml')


def _build_blocks(sensors, max_block_size=20, max_gap=5):
    """Group sorted sensor list into contiguous ModBus read blocks."""
    sensors = sorted([s for s in sensors if not s.get('skip', False)], key=lambda r: r['address'])
    blocks = []
    current_block = []

    for sensor in sensors:
        if not current_block:
            current_block = [sensor]
            continue

        prev_sensor = current_block[-1]
        prev_end_addr = prev_sensor['address'] + prev_sensor.get('register_count', 1)
        gap = sensor['address'] - prev_end_addr
        total_regs_needed = sensor['address'] + sensor.get('register_count', 1) - current_block[0]['address']

        if gap < 0 or gap > max_gap or total_regs_needed > max_block_size:
            blocks.append(current_block)
            current_block = [sensor]
        else:
            current_block.append(sensor)

    if current_block:
        blocks.append(current_block)

    return blocks


def test_block_organisation():
    """Test the block organisation logic without actual ModBus communication."""
    sensors = load_sensors(_SENSORS_FILE)
    active_sensors = [s for s in sensors if not s.get('skip', False)]
    blocks = _build_blocks(sensors)

    assert len(blocks) > 0, "Expected at least one block"
    assert len(blocks) <= len(active_sensors), "More blocks than sensors is impossible"

    # Every active sensor must appear in exactly one block
    sensors_in_blocks = [s for block in blocks for s in block]
    assert len(sensors_in_blocks) == len(active_sensors), (
        f"Expected {len(active_sensors)} sensors in blocks, got {len(sensors_in_blocks)}"
    )

    # Each block must be sorted and contiguous within max_gap
    for block in blocks:
        for i in range(len(block) - 1):
            gap = block[i + 1]['address'] - (block[i]['address'] + block[i].get('register_count', 1))
            assert gap >= 0, f"Negative gap in block between {block[i]['name']} and {block[i+1]['name']}"
            assert gap <= 5, f"Gap too large in block between {block[i]['name']} and {block[i+1]['name']}"


def test_all_sensor_ids_unique():
    """Each sensor id must be unique."""
    sensors = load_sensors(_SENSORS_FILE)
    ids = [s['id'] for s in sensors]
    assert len(ids) == len(set(ids)), "Duplicate sensor IDs found"


def test_required_sensor_fields():
    """Every sensor must have the required fields."""
    required = {'id', 'name', 'address', 'register_count', 'value_type', 'multiply'}
    sensors = load_sensors(_SENSORS_FILE)
    for sensor in sensors:
        missing = required - sensor.keys()
        assert not missing, f"Sensor '{sensor.get('id', '?')}' is missing fields: {missing}"


if __name__ == '__main__':
    sensors = load_sensors(_SENSORS_FILE)
    blocks = _build_blocks(sensors)
    active = [s for s in sensors if not s.get('skip', False)]
    print(f'Organised {len(active)} sensors into {len(blocks)} blocks:')
    for i, block in enumerate(blocks):
        start_addr = block[0]['address']
        end_addr = block[-1]['address'] + block[-1].get('register_count', 1)
        total_regs = end_addr - start_addr
        names = [s['name'] for s in block]
        print(f'  Block {i + 1}: 0x{start_addr:04X}-0x{end_addr - 1:04X} ({total_regs} regs) - {", ".join(names)}')

