#!/bin/bash

# Test script to verify serial device access inside Docker container
# This helps debug device mapping issues

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info "EM340D Docker Serial Device Test"
print_info "================================"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_error ".env file not found"
    print_info "Run: cp .env.template .env"
    exit 1
fi

# Get serial device from .env
SERIAL_DEVICE=$(grep "^SERIAL_DEVICE=" .env | cut -d'=' -f2)
if [ -z "$SERIAL_DEVICE" ]; then
    print_error "SERIAL_DEVICE not found in .env"
    exit 1
fi

print_info "Testing serial device: $SERIAL_DEVICE"

# Check device exists on host
if [ ! -e "$SERIAL_DEVICE" ]; then
    print_error "Device $SERIAL_DEVICE does not exist on host"
    print_info "Available devices:"
    ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || print_warning "No serial devices found"
    ls -la /dev/serial/by-id/ 2>/dev/null || print_warning "No by-id devices found"
    exit 1
fi

print_success "Device $SERIAL_DEVICE exists on host"

# Show device details
print_info "Host device details:"
ls -la "$SERIAL_DEVICE"

# If it's a symlink, show what it points to
if [ -L "$SERIAL_DEVICE" ]; then
    REAL_DEVICE=$(readlink -f "$SERIAL_DEVICE")
    print_info "Symlink points to: $REAL_DEVICE"
    ls -la "$REAL_DEVICE"
fi

# Check if Docker is running
if ! docker compose ps | grep -q "em340d"; then
    print_warning "Docker container is not running"
    print_info "Starting container for test..."
    if ! docker compose up -d; then
        print_error "Failed to start Docker container"
        exit 1
    fi
    sleep 3
fi

print_info "Testing device access inside Docker container..."

# Test device access inside container
docker compose exec em340d bash -c "
echo 'Container device check:'
ls -la '$SERIAL_DEVICE' 2>/dev/null && echo 'SUCCESS: Device exists in container' || echo 'ERROR: Device not found in container'

echo ''
echo 'Container /dev contents:'
ls -la /dev/tty* 2>/dev/null | head -10

echo ''
echo 'Container /dev/serial contents:'
ls -la /dev/serial/ 2>/dev/null || echo 'No /dev/serial directory'

echo ''
echo 'Python serial test:'
python3 -c \"
import serial
import os
try:
    device = '$SERIAL_DEVICE'
    if os.path.exists(device):
        ser = serial.Serial(device, 9600, timeout=1)
        print(f'SUCCESS: Can open {device}')
        ser.close()
    else:
        print(f'ERROR: Device {device} not accessible')
except PermissionError as e:
    print(f'ERROR: Permission denied - {e}')
except Exception as e:
    print(f'ERROR: {e}')
\" 2>/dev/null
"

print_info ""
print_info "Test completed!"
print_info "If you see errors, try:"
print_info "1. Update .env with correct SERIAL_DEVICE path"
print_info "2. Run: ./quick-rebuild.sh"
print_info "3. Check device permissions on host"
