#!/bin/bash

# MQTT Connectivity Test Script for EM340D
# Tests MQTT broker connectivity from both host and Docker container

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

print_info "EM340D MQTT Connectivity Test"
print_info "============================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found"
    print_info "Run: cp .env.template .env"
    exit 1
fi

# Get MQTT broker from .env
MQTT_BROKER=$(grep "^MQTT_BROKER=" .env | cut -d'=' -f2)
MQTT_PORT=$(grep "^MQTT_PORT=" .env | cut -d'=' -f2 | head -1)
MQTT_TOPIC=$(grep "^MQTT_TOPIC=" .env | cut -d'=' -f2 | head -1)
DEVICE_SERIAL_NUMBER=$(grep "^DEVICE_SERIAL_NUMBER=" .env | cut -d'=' -f2)

# Set defaults if empty
MQTT_BROKER=${MQTT_BROKER:-localhost}
MQTT_PORT=${MQTT_PORT:-1883}
MQTT_TOPIC=${MQTT_TOPIC:-em340}
DEVICE_SERIAL_NUMBER=${DEVICE_SERIAL_NUMBER:-235411W}

print_info "Configuration from .env:"
print_info "  MQTT_BROKER: $MQTT_BROKER"
print_info "  MQTT_PORT: $MQTT_PORT"
print_info "  MQTT_TOPIC: $MQTT_TOPIC"
print_info "  DEVICE_SERIAL_NUMBER: $DEVICE_SERIAL_NUMBER"
print_info ""

# Test 1: Check if mosquitto clients are installed
print_info "Test 1: Checking mosquitto client tools..."
if command -v mosquitto_pub >/dev/null 2>&1 && command -v mosquitto_sub >/dev/null 2>&1; then
    print_success "Mosquitto client tools are available"
else
    print_warning "Mosquitto client tools not found"
    print_info "Install with: sudo apt install mosquitto-clients"
    print_info "Skipping direct MQTT tests..."
    SKIP_MQTT_TESTS=true
fi

if [ "$SKIP_MQTT_TESTS" != true ]; then
    # Test 2: Host connectivity
    print_info ""
    print_info "Test 2: Testing MQTT broker connectivity from host..."
    
    # Test connection with timeout
    if timeout 5 mosquitto_pub -h "$MQTT_BROKER" -p "$MQTT_PORT" -t "test/connectivity" -m "host_test" >/dev/null 2>&1; then
        print_success "Host can connect to MQTT broker at $MQTT_BROKER:$MQTT_PORT"
        HOST_MQTT_OK=true
    else
        print_error "Host cannot connect to MQTT broker at $MQTT_BROKER:$MQTT_PORT"
        print_info "Check if MQTT broker is running and accessible"
        HOST_MQTT_OK=false
    fi

    # Test 3: Subscribe test
    if [ "$HOST_MQTT_OK" = true ]; then
        print_info ""
        print_info "Test 3: Testing MQTT publish/subscribe from host..."
        
        # Start subscriber in background
        timeout 3 mosquitto_sub -h "$MQTT_BROKER" -p "$MQTT_PORT" -t "${MQTT_TOPIC}/test" -C 1 >/tmp/mqtt_test_result 2>&1 &
        SUB_PID=$!
        
        sleep 1
        
        # Publish test message
        if mosquitto_pub -h "$MQTT_BROKER" -p "$MQTT_PORT" -t "${MQTT_TOPIC}/test" -m "em340d_connectivity_test" >/dev/null 2>&1; then
            wait $SUB_PID
            if grep -q "em340d_connectivity_test" /tmp/mqtt_test_result 2>/dev/null; then
                print_success "MQTT publish/subscribe working correctly"
                MQTT_PUBSUB_OK=true
            else
                print_warning "MQTT publish successful but subscribe failed"
                MQTT_PUBSUB_OK=false
            fi
        else
            print_error "MQTT publish failed"
            kill $SUB_PID 2>/dev/null
            MQTT_PUBSUB_OK=false
        fi
        
        rm -f /tmp/mqtt_test_result
    fi
fi

# Test 4: Docker container connectivity
print_info ""
print_info "Test 4: Testing MQTT connectivity from Docker container..."

# Check if container is running
if docker compose ps | grep -q "em340d.*Up"; then
    print_info "EM340D container is running, testing connectivity..."
    
    # Test MQTT from inside container
    if docker compose exec em340d python3 -c "
import socket
import sys
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('$MQTT_BROKER', $MQTT_PORT))
    sock.close()
    if result == 0:
        print('SUCCESS: Container can reach MQTT broker')
        sys.exit(0)
    else:
        print('ERROR: Container cannot reach MQTT broker')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" >/tmp/container_test 2>&1; then
        print_success "Container can reach MQTT broker at $MQTT_BROKER:$MQTT_PORT"
        CONTAINER_MQTT_OK=true
    else
        print_error "Container cannot reach MQTT broker"
        print_info "Container test output:"
        cat /tmp/container_test | sed 's/^/  /'
        CONTAINER_MQTT_OK=false
    fi
    
    rm -f /tmp/container_test
else
    print_warning "EM340D container is not running"
    print_info "Start it with: docker compose up -d"
    CONTAINER_MQTT_OK=false
fi

# Summary and recommendations
print_info ""
print_info "Test Results Summary:"
print_info "===================="

if [ "$SKIP_MQTT_TESTS" != true ]; then
    if [ "$HOST_MQTT_OK" = true ]; then
        print_success "✅ Host MQTT connectivity: WORKING"
    else
        print_error "❌ Host MQTT connectivity: FAILED"
    fi
    
    if [ "$MQTT_PUBSUB_OK" = true ]; then
        print_success "✅ MQTT publish/subscribe: WORKING"
    else
        print_warning "⚠️  MQTT publish/subscribe: ISSUES"
    fi
else
    print_warning "⚠️  MQTT client tools: NOT AVAILABLE"
fi

if [ "$CONTAINER_MQTT_OK" = true ]; then
    print_success "✅ Container MQTT connectivity: WORKING"
else
    print_error "❌ Container MQTT connectivity: FAILED"
fi

print_info ""
print_info "Recommendations:"
print_info "==============="

if [ "$SKIP_MQTT_TESTS" = true ]; then
    print_info "1. Install mosquitto clients: sudo apt install mosquitto-clients"
fi

if [ "$HOST_MQTT_OK" = false ]; then
    print_info "2. Check MQTT broker status:"
    print_info "   - sudo systemctl status mosquitto"
    print_info "   - Or install: sudo apt install mosquitto mosquitto-clients"
fi

if [ "$CONTAINER_MQTT_OK" = false ]; then
    print_info "3. For Docker connectivity issues:"
    print_info "   - Current setup uses host networking (network_mode: host)"
    print_info "   - MQTT broker should be accessible on localhost inside container"
    print_info "   - Check docker-compose.yml has: network_mode: \"host\""
    print_info "   - Rebuild container: ./quick-rebuild.sh"
fi

if [ "$MQTT_PUBSUB_OK" = false ] && [ "$HOST_MQTT_OK" = true ]; then
    print_info "4. Check MQTT broker configuration:"
    print_info "   - Verify topic permissions"
    print_info "   - Check authentication settings"
fi

print_info ""
if [ "$HOST_MQTT_OK" = true ] && [ "$CONTAINER_MQTT_OK" = true ]; then
    print_success "All connectivity tests passed! EM340D should work correctly."
    print_info "Monitor logs: ./logs.sh -f"
else
    print_warning "Some connectivity tests failed. Fix the issues above and retest."
fi
