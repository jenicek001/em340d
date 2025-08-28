#!/bin/bash

# EM340D Docker Deployment Script
# This script sets up and deploys EM340D in a Docker container

set -e

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

# Check if Docker and Docker Compose are installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        print_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        print_info "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi

    print_success "Docker and Docker Compose are available"
}

# Create necessary directories
setup_directories() {
    print_info "Creating necessary directories..."
    mkdir -p config logs
    print_success "Directories created"
}

# Setup configuration files
setup_config() {
    if [ ! -f "config/em340.yaml" ]; then
        print_info "Creating configuration file from template..."
        cp em340.yaml.template config/em340.yaml
        print_warning "Please edit config/em340.yaml with your specific settings"
    else
        print_success "Configuration file already exists"
    fi

    if [ ! -f ".env" ]; then
        print_info "Creating environment file from template..."
        cp .env.template .env
        print_warning "Please edit .env file with your MQTT broker settings"
    else
        print_success "Environment file already exists"
    fi
}

# Check USB-RS485 device
check_device() {
    local device="${SERIAL_DEVICE:-/dev/ttyUSB0}"
    
    print_info "Checking for serial device: $device"
    
    if [ -c "$device" ]; then
        print_success "Serial device $device found"
        
        # Check permissions
        if [ -r "$device" ] && [ -w "$device" ]; then
            print_success "Device permissions are correct"
        else
            print_warning "Device permissions may need adjustment"
            print_info "You may need to add your user to the 'dialout' group:"
            print_info "sudo usermod -a -G dialout \$USER"
            print_info "Then log out and back in"
        fi
    else
        print_warning "Serial device $device not found"
        print_info "Please ensure your USB-RS485 adapter is connected"
        print_info "Available serial devices:"
        ls -la /dev/ttyUSB* 2>/dev/null || print_info "No /dev/ttyUSB* devices found"
        ls -la /dev/ttyACM* 2>/dev/null || print_info "No /dev/ttyACM* devices found"
    fi
}

# Build and start the application
deploy() {
    print_info "Building Docker image..."
    if docker-compose build; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi

    print_info "Starting EM340D container..."
    if docker-compose up -d; then
        print_success "Container started successfully"
    else
        print_error "Failed to start container"
        exit 1
    fi

    print_info "Waiting for container to stabilize..."
    sleep 5

    # Check container status
    if docker-compose ps | grep -q "Up"; then
        print_success "EM340D is running successfully"
        print_info "View logs with: docker-compose logs -f"
        print_info "Stop with: docker-compose down"
        print_info "Restart with: docker-compose restart"
    else
        print_error "Container failed to start properly"
        print_info "Check logs with: docker-compose logs"
        exit 1
    fi
}

# Show usage information
show_usage() {
    echo "EM340D Docker Deployment"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --setup-only    Only setup configuration files, don't deploy"
    echo "  --no-device-check    Skip serial device check"
    echo "  --help         Show this help message"
    echo ""
    echo "Files created:"
    echo "  config/em340.yaml   - Main configuration file"
    echo "  .env               - Environment variables (MQTT settings)"
    echo "  logs/              - Application logs directory"
    echo ""
    echo "Commands after deployment:"
    echo "  docker-compose logs -f     - View live logs"
    echo "  docker-compose restart     - Restart service"
    echo "  docker-compose down        - Stop and remove container"
    echo "  docker-compose pull        - Update to latest image"
}

# Main execution
main() {
    local setup_only=false
    local skip_device_check=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --setup-only)
                setup_only=true
                shift
                ;;
            --no-device-check)
                skip_device_check=true
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    print_info "Starting EM340D Docker deployment..."
    
    check_docker
    setup_directories
    setup_config

    if [ "$skip_device_check" = false ]; then
        check_device
    fi

    if [ "$setup_only" = false ]; then
        deploy
    else
        print_success "Setup completed. Edit configuration files and run '$0' to deploy."
    fi
}

# Trap errors and cleanup
trap 'print_error "An error occurred. Check the output above for details."' ERR

# Run main function
main "$@"
