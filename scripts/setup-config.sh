#!/bin/bash

# EM340D Configuration Setup Script
# Creates necessary configuration files for first-time setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}  EM340D Configuration Setup${NC}"
    echo -e "${CYAN}================================${NC}"
}

print_header

# Check if .env template exists
if [ ! -f ".env.template" ]; then
    print_error "Template file .env.template missing! Please ensure the repository is complete."
    exit 1
fi

# Setup .env file
if [ ! -f ".env" ]; then
    print_info "Creating .env file from template..."
    cp .env.template .env
    print_success ".env file created"
    print_warning "Please edit .env file with your settings"
else
    print_warning ".env file already exists - skipping"
fi

# Display current configuration status
print_info ""
print_info "Configuration Status:"
print_info "===================="

# Check .env file
if [ -f ".env" ]; then
    print_success ".env file: EXISTS"

    if grep -q "MQTT_BROKER=localhost" .env || grep -q "MQTT_BROKER=$" .env; then
        print_warning "  ⚠️  MQTT_BROKER still set to localhost - needs configuration"
    else
        BROKER=$(grep "MQTT_BROKER=" .env | cut -d'=' -f2)
        print_success "  ✅ MQTT_BROKER configured: $BROKER"
    fi
else
    print_error ".env file: MISSING"
fi

# Check sensors definition file (static, included in repo)
if [ -f "config/sensors.yaml" ]; then
    print_success "config/sensors.yaml: EXISTS (static sensor definitions)"
else
    print_error "config/sensors.yaml: MISSING (should be included in the repository)"
fi

# Check USB devices
print_info ""
print_info "USB Serial Devices:"
if ls /dev/ttyUSB* 2>/dev/null; then
    print_success "USB serial devices found"
else
    print_warning "No /dev/ttyUSB* devices found - connect your USB-RS485 adapter"
fi

# Provide next steps
print_info ""
print_info "Next Steps:"
print_info "==========="
print_info "1. Edit .env file with your settings:"
print_info "   ${YELLOW}nano .env${NC}"
print_info ""
print_info "   Required settings:"
print_info "   ${CYAN}MQTT_BROKER=192.168.1.100${NC}  # Your MQTT broker IP"
print_info "   ${CYAN}MQTT_USERNAME=your_user${NC}     # Optional"
print_info "   ${CYAN}MQTT_PASSWORD=your_pass${NC}     # Optional"
print_info ""
print_info "2. Check your USB-RS485 device:"
print_info "   ${YELLOW}ls -la /dev/ttyUSB*${NC}"
print_info ""
print_info "3. Set up serial port access:"
print_info "   ${YELLOW}sudo ./scripts/setup-serial-access.sh${NC}"
print_info ""
print_info "4. Deploy with Docker:"
print_info "   ${YELLOW}./scripts/quick-rebuild.sh${NC}"
print_info ""
print_info "5. Monitor logs:"
print_info "   ${YELLOW}./scripts/logs.sh -f${NC}"

print_info ""
print_success "Configuration setup complete!"
print_info "Edit the .env file and follow the next steps above."
