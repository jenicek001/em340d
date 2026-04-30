#!/usr/bin/env python3
"""
Health check script for EM340D service.
Monitors device availability and can be used by Docker healthcheck or external monitoring.
"""
import os
import sys
import serial
from datetime import datetime


def check_device_exists(device_path):
    """Check if the device file exists."""
    if not os.path.exists(device_path):
        print(f"FAIL: Device {device_path} does not exist", file=sys.stderr)
        return False
    return True


def check_device_accessible(device_path):
    """Check if the device is accessible and can be opened."""
    try:
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
    """Main health check routine."""
    device = os.getenv('SERIAL_DEVICE', '/dev/ttyUSB0')

    print(f"Health check for EM340D - {datetime.now().isoformat()}")

    if not check_device_exists(device):
        sys.exit(1)

    if not check_device_accessible(device):
        sys.exit(1)

    print("Health check passed")
    sys.exit(0)


if __name__ == '__main__':
    main()

