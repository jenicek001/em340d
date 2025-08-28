#!/bin/bash

# EM340D Configuration Setup Script
# Creates necessary configuration files for first-time setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

# Check if templates exist
if [ ! -f ".env.template" ] || [ ! -f "em340.yaml.template" ]; then
    print_error "Template files missing! Please ensure .env.template and em340.yaml.template exist."
    exit 1
fi

# Create config directory if it doesn't exist
if [ ! -d "config" ]; then
    print_info "Creating config directory..."
    mkdir -p config
    print_success "Config directory created"
else
    print_info "Config directory already exists"
fi

# Setup .env file
if [ ! -f ".env" ]; then
    print_info "Creating .env file from template..."
    cp .env.template .env
    print_success ".env file created"
    print_warning "Please edit .env file with your MQTT broker settings"
else
    print_warning ".env file already exists - skipping"
fi

# Setup em340.yaml file (for direct Python installation)
if [ ! -f "em340.yaml" ]; then
    print_info "Creating em340.yaml from template..."
    cp em340.yaml.template em340.yaml
    print_success "em340.yaml created"
    print_warning "Please edit em340.yaml with your specific settings"
else
    print_warning "em340.yaml already exists - skipping"
fi

# Setup config/em340.yaml file
if [ ! -f "config/em340.yaml" ]; then
    print_info "Creating config/em340.yaml from template..."
    cp em340.yaml.template config/em340.yaml
    print_success "config/em340.yaml created"
else
    print_warning "config/em340.yaml already exists - skipping"
fi

# Display current configuration status
print_info ""
print_info "Configuration Status:"
print_info "===================="

# Check .env file
if [ -f ".env" ]; then
    print_success ".env file: EXISTS"
    
    # Check if MQTT_BROKER is configured
    if grep -q "MQTT_BROKER=localhost" .env || grep -q "MQTT_BROKER=$" .env; then
        print_warning "  ⚠️  MQTT_BROKER still set to localhost - needs configuration"
    else
        BROKER=$(grep "MQTT_BROKER=" .env | cut -d'=' -f2)
        print_success "  ✅ MQTT_BROKER configured: $BROKER"
    fi
else
    print_error ".env file: MISSING"
fi

# Check em340.yaml file (for direct Python installation)
if [ -f "em340.yaml" ]; then
    print_success "em340.yaml: EXISTS"
    
    # Check if serial number is configured
    if grep -q "serial_number.*235411W" em340.yaml; then
        print_success "  ✅ Serial number configured"
    else
        print_warning "  ⚠️  Serial number may need customization"
    fi
else
    print_error "em340.yaml: MISSING"
fi

# Check config file
if [ -f "config/em340.yaml" ]; then
    print_success "config/em340.yaml: EXISTS (Docker template)"
else
    print_error "config/em340.yaml: MISSING"
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
print_info "1. Edit .env file with your MQTT broker settings:"
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
print_info "   ${YELLOW}sudo ./setup-serial-access.sh${NC}"
print_info ""
print_info "4. Deploy with Docker:"
print_info "   ${YELLOW}./quick-rebuild.sh${NC}"
print_info ""
print_info "5. Monitor logs:"
print_info "   ${YELLOW}./logs.sh -f${NC}"

print_info ""
print_success "Configuration setup complete!"
print_info "Edit the configuration files and follow the next steps above."
