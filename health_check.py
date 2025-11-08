#!/usr/bin/env python3
"""
Health check script for EM340D service.
Monitors device availability and can be used by Docker healthcheck or external monitoring.
"""
import os
import sys
import serial
import yaml
from datetime import datetime

def load_config():
    """Load configuration from em340.yaml"""
    try:
        # Try to import config_loader if available for environment variable support
        try:
            from config_loader import load_yaml_with_env
            config = load_yaml_with_env('/app/em340.yaml')
        except ImportError:
            # Fallback to basic yaml loading
            with open('/app/em340.yaml', 'r') as f:
                config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return None

def check_device_exists(device_path):
    """Check if the device file exists"""
    if not os.path.exists(device_path):
        print(f"FAIL: Device {device_path} does not exist", file=sys.stderr)
        return False
    return True

def check_device_accessible(device_path):
    """Check if the device is accessible and can be opened"""
    try:
        # Try to open the serial port briefly
        with serial.Serial(device_path, 9600, timeout=0.5) as ser:
            if ser.is_open:
                print(f"OK: Device {device_path} is accessible")
                return True
    except serial.SerialException as e:
        print(f"FAIL: Cannot access device {device_path}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"FAIL: Unexpected error accessing {device_path}: {e}", file=sys.stderr)
        return False
    
    return False

def main():
    """Main health check routine"""
    config = load_config()
    if not config:
        sys.exit(1)
    
    device = config.get('config', {}).get('device', '/dev/ttyUSB0')
    
    print(f"Health check for EM340D - {datetime.now().isoformat()}")
    
    # Check if device exists
    if not check_device_exists(device):
        sys.exit(1)
    
    # Check if device is accessible
    if not check_device_accessible(device):
        sys.exit(1)
    
    print("Health check passed")
    sys.exit(0)

if __name__ == '__main__':
    main()
