#!/bin/bash

# Quick troubleshooting script for EM340D Docker on Raspberry Pi
# Run this script to diagnose common issues

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

print_info "EM340D Docker Troubleshooting Script"
print_info "===================================="

# Check Docker version
print_info "Checking Docker version..."
if docker --version; then
    print_success "Docker is installed"
else
    print_error "Docker is not installed"
    exit 1
fi

# Check Docker Compose
print_info "Checking Docker Compose..."
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    docker compose version
    print_success "Docker Compose V2 is available"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    docker-compose version
    print_success "Docker Compose V1 is available"
else
    print_error "No Docker Compose found"
    exit 1
fi

# Check if user is in docker group
print_info "Checking user permissions..."
if groups $USER | grep -q docker; then
    print_success "User $USER is in docker group"
else
    print_warning "User $USER is not in docker group"
    print_info "Run: sudo usermod -aG docker $USER"
    print_info "Then log out and back in"
fi

# Check USB devices
print_info "Checking USB serial devices and permissions..."
if ls /dev/ttyUSB* 2>/dev/null; then
    print_success "USB serial devices found:"
    for device in /dev/ttyUSB*; do
        if [ -e "$device" ]; then
            ls -la "$device"
            # Check if current user has access
            if [ -r "$device" ] && [ -w "$device" ]; then
                print_success "Current user has access to $device"
            else
                print_warning "Current user does not have access to $device"
                # Check if user is in dialout group
                if groups $USER | grep -q dialout; then
                    print_info "User $USER is in dialout group - may need to log out/in"
                else
                    print_warning "User $USER is not in dialout group"
                    print_info "Run: sudo usermod -aG dialout $USER"
                    print_info "Then log out and back in"
                fi
            fi
        fi
    done
else
    print_warning "No /dev/ttyUSB* devices found"
fi

if ls /dev/ttyACM* 2>/dev/null; then
    print_success "ACM serial devices found:"
    for device in /dev/ttyACM*; do
        if [ -e "$device" ]; then
            ls -la "$device"
            # Check if current user has access
            if [ -r "$device" ] && [ -w "$device" ]; then
                print_success "Current user has access to $device"
            else
                print_warning "Current user does not have access to $device"
            fi
        fi
    done
else
    print_info "No /dev/ttyACM* devices found"
fi

# Check dialout group membership
print_info "Checking dialout group membership..."
if groups $USER | grep -q dialout; then
    print_success "User $USER is in dialout group"
else
    print_warning "User $USER is not in dialout group"
    print_info "Serial devices require dialout group membership"
    print_info "Fix with: sudo usermod -aG dialout $USER"
fi

# Check configuration files
print_info "Checking configuration files..."
if [ -f "config/em340.yaml" ]; then
    print_success "Configuration file exists: config/em340.yaml"
else
    print_warning "Configuration file missing: config/em340.yaml"
    if [ -f "em340.yaml.template" ]; then
        print_info "Template available, run: cp em340.yaml.template config/em340.yaml"
    fi
fi

if [ -f ".env" ]; then
    print_success "Environment file exists: .env"
else
    print_warning "Environment file missing: .env"
    if [ -f ".env.template" ]; then
        print_info "Template available, run: cp .env.template .env"
    fi
fi

# Check docker-compose.yml syntax
print_info "Checking docker-compose.yml syntax..."
if $COMPOSE_CMD config > /dev/null 2>&1; then
    print_success "docker-compose.yml syntax is valid"
else
    print_error "docker-compose.yml has syntax errors:"
    $COMPOSE_CMD config
fi

# Test Python dependencies in a temporary container
print_info "Testing Python dependencies..."
if docker run --rm python:3.12-slim bash -c "pip install -r /dev/stdin <<< 'minimalmodbus==2.1.1
paho-mqtt==2.1.0
pyserial==3.5
python-dateutil==2.9.0.post0
PyYAML==6.0.2
six==1.17.0
pytest==8.4.1' && python -c 'import minimalmodbus, paho.mqtt.client, yaml; print(\"All dependencies work\")'"; then
    print_success "Python dependencies can be installed and imported"
else
    print_error "Python dependencies test failed"
fi

# Check available disk space
print_info "Checking disk space..."
AVAILABLE=$(df . | tail -1 | awk '{print $4}')
if [ "$AVAILABLE" -gt 1048576 ]; then  # 1GB in KB
    print_success "Sufficient disk space available"
else
    print_warning "Low disk space: $(df -h . | tail -1 | awk '{print $4}') available"
fi

# Check memory
print_info "Checking memory..."
MEM_TOTAL=$(free -m | grep '^Mem:' | awk '{print $2}')
if [ "$MEM_TOTAL" -gt 512 ]; then
    print_success "Sufficient memory: ${MEM_TOTAL}MB"
else
    print_warning "Low memory: ${MEM_TOTAL}MB (512MB+ recommended)"
fi

print_info "Troubleshooting complete!"
print_info "If issues persist, check the logs with: $COMPOSE_CMD logs"
