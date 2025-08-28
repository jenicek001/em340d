#!/bin/bash

# Serial port access setup script for EM340 user
# Run this script to properly configure serial port access

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

# Configuration
TARGET_USER="em340"
REQUIRED_GROUP="dialout"

print_info "EM340D Serial Port Access Setup"
print_info "==============================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

# Check if target user exists
if ! id "$TARGET_USER" &>/dev/null; then
    print_error "User '$TARGET_USER' does not exist"
    print_info "Create the user first with: sudo useradd -m -s /bin/bash $TARGET_USER"
    exit 1
fi

print_success "User '$TARGET_USER' exists"

# Check if dialout group exists
if ! getent group "$REQUIRED_GROUP" >/dev/null; then
    print_error "Group '$REQUIRED_GROUP' does not exist"
    print_info "This is unusual - dialout group should exist by default"
    exit 1
fi

print_success "Group '$REQUIRED_GROUP' exists"

# Check current group membership
if groups "$TARGET_USER" | grep -q "\b$REQUIRED_GROUP\b"; then
    print_success "User '$TARGET_USER' is already in '$REQUIRED_GROUP' group"
    ALREADY_IN_GROUP=true
else
    print_info "User '$TARGET_USER' is not in '$REQUIRED_GROUP' group"
    ALREADY_IN_GROUP=false
fi

# Add user to dialout group if needed
if [ "$ALREADY_IN_GROUP" = false ]; then
    print_info "Adding user '$TARGET_USER' to '$REQUIRED_GROUP' group..."
    if usermod -aG "$REQUIRED_GROUP" "$TARGET_USER"; then
        print_success "User '$TARGET_USER' added to '$REQUIRED_GROUP' group"
    else
        print_error "Failed to add user to group"
        exit 1
    fi
fi

# Show current group membership
print_info "Current groups for user '$TARGET_USER':"
groups "$TARGET_USER"

# Check for USB serial devices
print_info "Checking for USB serial devices..."
USB_DEVICES=$(ls /dev/ttyUSB* 2>/dev/null || true)
ACM_DEVICES=$(ls /dev/ttyACM* 2>/dev/null || true)

if [ -n "$USB_DEVICES" ]; then
    print_success "Found USB serial devices:"
    for device in $USB_DEVICES; do
        ls -la "$device"
    done
else
    print_warning "No /dev/ttyUSB* devices found"
fi

if [ -n "$ACM_DEVICES" ]; then
    print_success "Found ACM serial devices:"
    for device in $ACM_DEVICES; do
        ls -la "$device"
    done
else
    print_info "No /dev/ttyACM* devices found"
fi

# Test access to a specific device if it exists
TEST_DEVICE="/dev/ttyUSB0"
if [ -e "$TEST_DEVICE" ]; then
    print_info "Testing access to $TEST_DEVICE..."
    
    # Get device permissions
    DEVICE_PERMS=$(ls -la "$TEST_DEVICE")
    print_info "Device permissions: $DEVICE_PERMS"
    
    # Test access as target user
    if sudo -u "$TARGET_USER" test -r "$TEST_DEVICE" && sudo -u "$TARGET_USER" test -w "$TEST_DEVICE"; then
        print_success "User '$TARGET_USER' has read/write access to $TEST_DEVICE"
    else
        if [ "$ALREADY_IN_GROUP" = false ]; then
            print_warning "User '$TARGET_USER' does not have access to $TEST_DEVICE yet"
            print_info "This is normal - user needs to log out and back in for group changes to take effect"
            print_info "Or restart the application/service that will use the serial port"
        else
            print_error "User '$TARGET_USER' still does not have access to $TEST_DEVICE"
            print_info "Check device permissions and group ownership"
        fi
    fi
    
    # Test Python serial access
    print_info "Testing Python serial access..."
    if sudo -u "$TARGET_USER" python3 -c "
import serial
try:
    ser = serial.Serial('$TEST_DEVICE', 9600, timeout=1)
    print('SUCCESS: Python can access serial port')
    ser.close()
except PermissionError:
    print('ERROR: Permission denied - group membership may not be active yet')
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null; then
        print_success "Python serial access test passed"
    else
        print_warning "Python serial access test failed - this may be normal if group membership is not active yet"
    fi
else
    print_warning "Test device $TEST_DEVICE not found"
    print_info "Connect your USB-RS485 adapter and run this script again"
fi

# Provide next steps
print_info ""
print_info "Next Steps:"
print_info "==========="

if [ "$ALREADY_IN_GROUP" = false ]; then
    print_info "1. User '$TARGET_USER' needs to log out and back in for group changes to take effect"
    print_info "   OR restart any services/applications that need serial access"
    print_info "2. Verify access with: sudo -u $TARGET_USER ls -la /dev/ttyUSB0"
    print_info "3. Test the EM340D application with the new permissions"
else
    print_info "1. User '$TARGET_USER' should already have access to serial devices"
    print_info "2. If still having issues, check device permissions and try unplugging/reconnecting the USB device"
    print_info "3. Test the EM340D application"
fi

print_info ""
print_info "For Docker deployment:"
print_info "- Keep the current device mapping in docker-compose.yml"
print_info "- The container should inherit the host user's group permissions"
print_info "- Run: docker compose down && docker compose up -d"

print_info ""
print_success "Serial port access setup completed!"
