#!/bin/bash

# Enhanced Docker deployment script for EM340D with automatic user/group detection
# Handles serial port access by mapping host user to container

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

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    print_success "Using Docker Compose V2"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    print_success "Using Docker Compose V1"
else
    print_error "No Docker Compose found"
    exit 1
fi

print_info "=== EM340D Enhanced Docker Deployment ==="
print_info "========================================"

# Check if em340 user exists and get details
if id em340 &>/dev/null; then
    EM340_UID=$(id -u em340)
    EM340_GID=$(id -g em340)
    DIALOUT_GID=$(getent group dialout | cut -d: -f3)
    
    print_success "Found em340 user: UID=$EM340_UID, GID=$EM340_GID"
    print_info "dialout group GID: $DIALOUT_GID"
    
    # Check if em340 user is in dialout group
    if groups em340 | grep -q dialout; then
        print_success "em340 user is in dialout group"
    else
        print_error "em340 user is NOT in dialout group"
        print_info "Fix with: sudo usermod -aG dialout em340"
        exit 1
    fi
else
    print_error "em340 user does not exist"
    print_info "Create user with: sudo useradd -m -G dialout em340"
    exit 1
fi

# Check for USB serial devices
print_info "Checking USB serial devices..."
USB_DEVICES=$(ls /dev/ttyUSB* 2>/dev/null || true)
if [ -n "$USB_DEVICES" ]; then
    print_success "Found USB serial devices:"
    for device in $USB_DEVICES; do
        ls -la "$device"
        # Check if em340 user can access the device
        if sudo -u em340 test -r "$device" && sudo -u em340 test -w "$device"; then
            print_success "em340 user has access to $device"
        else
            print_warning "em340 user does not have access to $device"
            print_info "User may need to log out/in for dialout group membership to take effect"
        fi
    done
else
    print_warning "No USB serial devices found"
    print_info "Connect your USB-RS485 adapter and try again"
fi

# Update docker-compose.yml with correct user/group IDs
print_info "Updating docker-compose.yml with user mapping..."

# Create a backup of the original
cp docker-compose.yml docker-compose.yml.backup

# Use sed to update the user line
if grep -q "user:" docker-compose.yml; then
    sed -i "s/user: \".*\"/user: \"$EM340_UID:$DIALOUT_GID\"/" docker-compose.yml
    print_success "Updated existing user mapping to $EM340_UID:$DIALOUT_GID"
else
    # Add user line after the restart line
    sed -i "/restart: unless-stopped/a\\    \\n    # Run as em340 user with dialout group access\\n    user: \"$EM340_UID:$DIALOUT_GID\"  # em340_uid:dialout_gid" docker-compose.yml
    print_success "Added user mapping: $EM340_UID:$DIALOUT_GID"
fi

# Verify docker-compose.yml syntax
print_info "Validating docker-compose.yml syntax..."
if $COMPOSE_CMD config > /dev/null 2>&1; then
    print_success "docker-compose.yml syntax is valid"
else
    print_error "docker-compose.yml has syntax errors"
    print_info "Restoring backup..."
    mv docker-compose.yml.backup docker-compose.yml
    exit 1
fi

# Check required files
print_info "Checking required files..."
MISSING_FILES=()

if [ ! -f "Dockerfile" ]; then
    MISSING_FILES+=("Dockerfile")
fi

if [ ! -f "requirements.txt" ]; then
    MISSING_FILES+=("requirements.txt")
fi

if [ ! -f "em340.py" ]; then
    MISSING_FILES+=("em340.py")
fi

if [ ! -f "config/em340.yaml" ]; then
    MISSING_FILES+=("config/em340.yaml")
fi

if [ ! -f ".env" ]; then
    MISSING_FILES+=(".env")
fi

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    print_success "All required files present"
else
    print_error "Missing required files: ${MISSING_FILES[*]}"
    exit 1
fi

# Test Python dependencies
print_info "Testing Python dependencies..."
if python3 -c "import minimalmodbus, paho.mqtt.client, yaml, serial" 2>/dev/null; then
    print_success "All Python dependencies available on host"
else
    print_warning "Some Python dependencies missing on host (this is OK for Docker deployment)"
fi

# Stop existing container
print_info "Stopping existing containers..."
$COMPOSE_CMD down

# Build the image
print_info "Building Docker image..."
if $COMPOSE_CMD build --no-cache; then
    print_success "Docker image built successfully"
else
    print_error "Docker build failed"
    exit 1
fi

# Test container permissions before starting
print_info "Testing container permissions..."
if docker run --rm \
    -v /dev:/dev \
    --user "$EM340_UID:$DIALOUT_GID" \
    $(docker images --format "table {{.Repository}}:{{.Tag}}" | grep em340d | head -1) \
    ls -la /dev/ttyUSB0 2>/dev/null; then
    print_success "Container can see USB device"
else
    print_warning "Container permission test inconclusive (device may not be connected)"
fi

# Start the services
print_info "Starting EM340D services..."
if $COMPOSE_CMD up -d; then
    print_success "EM340D container started successfully"
else
    print_error "Failed to start EM340D container"
    exit 1
fi

# Wait a moment for startup
sleep 3

# Check container status
print_info "Checking container status..."
if $COMPOSE_CMD ps | grep -q "Up"; then
    print_success "Container is running"
    
    # Show recent logs
    print_info "Recent container logs:"
    echo -e "${CYAN}================================${NC}"
    $COMPOSE_CMD logs --tail=20 --timestamps
    echo -e "${CYAN}================================${NC}"
    
else
    print_error "Container is not running properly"
    print_info "Check logs with: $COMPOSE_CMD logs"
    exit 1
fi

# Test serial access inside container
print_info "Testing serial port access inside container..."
if $COMPOSE_CMD exec em340d ls -la /dev/ttyUSB0 2>/dev/null; then
    print_success "Container can access USB device"
else
    print_warning "Cannot test USB device access (device may not be connected)"
fi

print_info ""
print_success "=== Deployment Complete ==="
print_info "Monitor logs with: $COMPOSE_CMD logs -f"
print_info "Stop with: $COMPOSE_CMD down"
print_info "Troubleshoot with: ./troubleshoot.sh"

# Clean up backup
rm -f docker-compose.yml.backup

print_info "Deployment finished successfully!"
