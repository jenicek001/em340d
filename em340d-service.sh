#!/bin/bash

# EM340D Service Management Script
# Provides easy control over the EM340D service

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

show_usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|enable|disable|test}"
    echo ""
    echo "Commands:"
    echo "  start    - Start the EM340D service"
    echo "  stop     - Stop the EM340D service"  
    echo "  restart  - Restart the EM340D service"
    echo "  status   - Show service status"
    echo "  logs     - Show recent logs"
    echo "  enable   - Enable auto-start on boot"
    echo "  disable  - Disable auto-start on boot"
    echo "  test     - Test MQTT connectivity"
}

# Check if systemd service exists
check_systemd_service() {
    if systemctl list-unit-files | grep -q "em340d.service"; then
        return 0
    else
        return 1
    fi
}

case "$1" in
    start)
        print_info "Starting EM340D service..."
        if check_systemd_service; then
            sudo systemctl start em340d.service
            docker compose ps
        else
            docker compose up -d
        fi
        ;;
    
    stop)
        print_info "Stopping EM340D service..."
        if check_systemd_service; then
            sudo systemctl stop em340d.service
        else
            docker compose down
        fi
        ;;
    
    restart)
        print_info "Restarting EM340D service..."
        if check_systemd_service; then
            sudo systemctl restart em340d.service
        else
            docker compose restart
        fi
        docker compose ps
        ;;
    
    status)
        print_info "EM340D Service Status:"
        echo "======================"
        
        if check_systemd_service; then
            print_info "Systemd service status:"
            sudo systemctl status em340d.service --no-pager -l
            echo ""
        fi
        
        print_info "Docker container status:"
        docker compose ps
        
        echo ""
        print_info "Recent application logs:"
        ./logs.sh -t 10
        ;;
    
    logs)
        print_info "Showing EM340D logs..."
        if check_systemd_service; then
            print_info "Choose log source:"
            print_info "1. Application logs (Docker)"
            print_info "2. System logs (journalctl)"
            read -p "Enter choice (1-2): " choice
            case $choice in
                1)
                    ./logs.sh -f
                    ;;
                2)
                    sudo journalctl -u em340d.service -f
                    ;;
                *)
                    print_warning "Invalid choice, showing application logs"
                    ./logs.sh -f
                    ;;
            esac
        else
            ./logs.sh -f
        fi
        ;;
    
    enable)
        print_info "Enabling auto-start on boot..."
        if check_systemd_service; then
            sudo systemctl enable em340d.service
            print_success "EM340D will start automatically on boot"
        else
            print_warning "Systemd service not found"
            print_info "Run './install-autostart.sh' to set up auto-start"
        fi
        ;;
    
    disable)
        print_info "Disabling auto-start on boot..."
        if check_systemd_service; then
            sudo systemctl disable em340d.service
            print_success "EM340D auto-start disabled"
        else
            print_warning "Systemd service not found, checking Docker restart policy"
            if grep -q "restart.*unless-stopped" docker-compose.yml; then
                print_warning "Docker container has 'restart: unless-stopped' policy"
                print_info "Container will still restart automatically with Docker daemon"
                print_info "To fully disable: change 'restart: unless-stopped' to 'restart: no' in docker-compose.yml"
            fi
        fi
        ;;
    
    test)
        print_info "Running MQTT connectivity test..."
        ./test-mqtt-connectivity.sh
        ;;
    
    *)
        print_error "Invalid command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
