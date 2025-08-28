#!/bin/bash

# EM340D Auto-Start Installation Script
# Configures the service to start automatically on boot

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

print_info "EM340D Auto-Start Installation"
print_info "==============================="

# Check if running as regular user (not root)
if [ "$EUID" -eq 0 ]; then
    print_error "Please run this script as a regular user (not root)"
    print_info "The script will ask for sudo permissions when needed"
    exit 1
fi

CURRENT_USER=$(whoami)
CURRENT_DIR=$(pwd)
print_info "Current user: $CURRENT_USER"
print_info "Installation directory: $CURRENT_DIR"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ] || [ ! -f "em340.py" ]; then
    print_error "This doesn't appear to be the EM340D directory"
    print_info "Please run this script from the EM340D project directory"
    exit 1
fi

print_success "EM340D project directory detected"

# Method selection
print_info ""
print_info "Choose installation method:"
print_info "1. Docker Compose Auto-Start (Simple, Recommended)"
print_info "2. Systemd Service (Advanced, More Control)"
print_info "3. Both (Maximum Reliability)"

read -p "Enter your choice (1-3): " choice

case $choice in
    1|2|3)
        print_info "Selected method: $choice"
        ;;
    *)
        print_error "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Method 1: Docker Compose Auto-Start
if [ "$choice" = "1" ] || [ "$choice" = "3" ]; then
    print_info ""
    print_info "=== Setting up Docker Compose Auto-Start ==="
    
    # Check if Docker is installed
    if command -v docker >/dev/null 2>&1; then
        print_success "Docker is installed"
    else
        print_error "Docker is not installed"
        print_info "Install Docker first: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    
    # Check if Docker Compose is available
    if docker compose version >/dev/null 2>&1; then
        print_success "Docker Compose is available"
    elif command -v docker-compose >/dev/null 2>&1; then
        print_success "Docker Compose (standalone) is available"
    else
        print_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Enable Docker service
    print_info "Enabling Docker service to start on boot..."
    if sudo systemctl enable docker; then
        print_success "Docker service enabled"
    else
        print_error "Failed to enable Docker service"
        exit 1
    fi
    
    # Start Docker service if not running
    if ! sudo systemctl is-active --quiet docker; then
        print_info "Starting Docker service..."
        sudo systemctl start docker
    fi
    
    # Add user to docker group if not already
    if groups "$CURRENT_USER" | grep -q "\bdocker\b"; then
        print_success "User '$CURRENT_USER' is already in docker group"
    else
        print_info "Adding user '$CURRENT_USER' to docker group..."
        sudo usermod -aG docker "$CURRENT_USER"
        print_warning "You need to log out and back in for group changes to take effect"
        print_info "Or run: newgrp docker"
    fi
    
    # Build and start the container
    print_info "Building and starting EM340D container..."
    if docker compose up -d --build; then
        print_success "EM340D container started successfully"
        DOCKER_METHOD_OK=true
    else
        print_error "Failed to start EM340D container"
        DOCKER_METHOD_OK=false
    fi
fi

# Method 2: Systemd Service
if [ "$choice" = "2" ] || [ "$choice" = "3" ]; then
    print_info ""
    print_info "=== Setting up Systemd Service ==="
    
    # Create systemd service file
    SERVICE_FILE="/etc/systemd/system/em340d.service"
    print_info "Creating systemd service file: $SERVICE_FILE"
    
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=EM340D ModBus to MQTT Gateway
Documentation=https://github.com/jenicek001/em340d
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart
TimeoutStartSec=300
User=$CURRENT_USER
Group=$CURRENT_USER
Environment=HOME=/home/$CURRENT_USER

[Install]
WantedBy=multi-user.target
EOF

    if [ -f "$SERVICE_FILE" ]; then
        print_success "Systemd service file created"
    else
        print_error "Failed to create systemd service file"
        exit 1
    fi
    
    # Reload systemd and enable service
    print_info "Enabling systemd service..."
    sudo systemctl daemon-reload
    
    if sudo systemctl enable em340d.service; then
        print_success "EM340D systemd service enabled"
        SYSTEMD_METHOD_OK=true
    else
        print_error "Failed to enable EM340D systemd service"
        SYSTEMD_METHOD_OK=false
    fi
    
    # Start the service
    print_info "Starting EM340D service..."
    if sudo systemctl start em340d.service; then
        print_success "EM340D service started successfully"
    else
        print_error "Failed to start EM340D service"
        print_info "Check logs with: sudo journalctl -u em340d.service -f"
    fi
fi

# Summary and verification
print_info ""
print_info "=== Installation Summary ==="

if [ "$choice" = "1" ] || [ "$choice" = "3" ]; then
    if [ "$DOCKER_METHOD_OK" = true ]; then
        print_success "✅ Docker Compose auto-start: CONFIGURED"
    else
        print_error "❌ Docker Compose auto-start: FAILED"
    fi
fi

if [ "$choice" = "2" ] || [ "$choice" = "3" ]; then
    if [ "$SYSTEMD_METHOD_OK" = true ]; then
        print_success "✅ Systemd service: CONFIGURED"
    else
        print_error "❌ Systemd service: FAILED"
    fi
fi

print_info ""
print_info "=== Verification Commands ==="
print_info "Check Docker container status:"
print_info "  docker compose ps"
print_info ""
print_info "Monitor application logs:"
print_info "  ./logs.sh -f"
print_info ""

if [ "$choice" = "2" ] || [ "$choice" = "3" ]; then
    print_info "Check systemd service status:"
    print_info "  sudo systemctl status em340d.service"
    print_info ""
    print_info "View systemd service logs:"
    print_info "  sudo journalctl -u em340d.service -f"
    print_info ""
fi

print_info "Test MQTT connectivity:"
print_info "  ./test-mqtt-connectivity.sh"

print_info ""
print_info "=== Manual Control Commands ==="
print_info "Start service:  sudo systemctl start em340d.service"
print_info "Stop service:   sudo systemctl stop em340d.service"
print_info "Restart service: sudo systemctl restart em340d.service"
print_info "Disable auto-start: sudo systemctl disable em340d.service"

print_info ""
if [ "$DOCKER_METHOD_OK" = true ] || [ "$SYSTEMD_METHOD_OK" = true ]; then
    print_success "EM340D will now start automatically on boot!"
    print_info "Reboot your Raspberry Pi to test: sudo reboot"
else
    print_error "Installation failed. Check the errors above."
    exit 1
fi
