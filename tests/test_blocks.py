#!/usr/bin/env python
"""
Test script to verify ModBus register block organization
"""
import yaml
from logger import log

def test_block_organization():
    """Test the block organization logic without actual ModBus communication"""
    
    # Load configuration
    config_file = 'em340.yaml'
    try:
        config = yaml.load(open(config_file), Loader=yaml.FullLoader)
    except Exception as e:
        log.error(f'Error loading YAML file: {e}')
        return

    # Group contiguous registers into blocks (same logic as in main code)
    sensors = [r for r in config['sensor'] if not r.get('skip', False)]
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
    print(f'Organized {len(sensors)} sensors into {len(blocks)} blocks:')
    for i, block in enumerate(blocks):
        start_addr = block[0]['address']
        end_addr = block[-1]['address'] + block[-1].get('register_count', 1)
        total_regs = end_addr - start_addr
        sensor_names = [s['name'] for s in block]
        print(f'  Block {i+1}: 0x{start_addr:04X}-0x{end_addr-1:04X} ({total_regs} regs) - {", ".join(sensor_names)}')

    # Analyze efficiency
    total_sensors = len(sensors)
    total_blocks = len(blocks)
    total_registers_individual = sum(s.get('register_count', 1) for s in sensors)
    total_registers_blocks = sum(block[-1]['address'] + block[-1].get('register_count', 1) - block[0]['address'] for block in blocks)
    
    efficiency = (total_registers_individual / total_registers_blocks) * 100 if total_registers_blocks > 0 else 0
    
    print(f'\nEfficiency Analysis:')
    print(f'  Individual reads would require: {total_sensors} ModBus calls')
    print(f'  Block reads require: {total_blocks} ModBus calls ({total_blocks/total_sensors*100:.1f}% of individual)')
    print(f'  Individual register count: {total_registers_individual}')
    print(f'  Block register count: {total_registers_blocks}')
    print(f'  Register efficiency: {efficiency:.1f}% (higher is better)')
    
    # Show address map
    print(f'\nAddress map:')
    for sensor in sensors:
        reg_count = sensor.get('register_count', 1)
        end_addr = sensor['address'] + reg_count - 1
        if reg_count == 1:
            print(f'  0x{sensor["address"]:04X}      : {sensor["name"]} ({sensor["value_type"]})')
        else:
            print(f'  0x{sensor["address"]:04X}-0x{end_addr:04X}: {sensor["name"]} ({sensor["value_type"]}, {reg_count} regs)')

if __name__ == '__main__':
    test_block_organization()
