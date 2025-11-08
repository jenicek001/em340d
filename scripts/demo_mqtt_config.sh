#!/bin/bash

# EM340 MQTT Configuration Demo Script
# Demonstrates remote configuration via MQTT

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

print_header() {
    echo -e "${CYAN}$1${NC}"
}

# Default configuration
MQTT_BROKER=${MQTT_BROKER:-localhost}
MQTT_PORT=${MQTT_PORT:-1883}
DEVICE_ID=${DEVICE_SERIAL_NUMBER:-235411W}
MQTT_TOPIC=${MQTT_TOPIC:-em340}

print_header "======================================="
print_header "  EM340D MQTT Configuration Demo"
print_header "======================================="
print_info "MQTT Broker: ${MQTT_BROKER}:${MQTT_PORT}"
print_info "Device ID: ${DEVICE_ID}"
print_info "Configuration Topic Base: ${MQTT_TOPIC}/${DEVICE_ID}/config"

# Check if mosquitto tools are available
if ! command -v mosquitto_pub &> /dev/null; then
    print_warning "mosquitto_pub not found. Installing..."
    sudo apt update && sudo apt install -y mosquitto-clients
fi

print_header "\n--- Step 1: Get Available Parameters ---"
print_info "Requesting list of configurable parameters..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/available/get" -m ""

print_info "Listening for response (5 seconds)..."
timeout 5 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/available" -C 1 || print_warning "No response received"

print_header "\n--- Step 2: Get Current Measurement Mode ---"
print_info "Getting current measurement mode..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measurement_mode/get" -m ""

print_info "Listening for response (5 seconds)..."
timeout 5 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measurement_mode/value" -C 1 || print_warning "No response received"

print_header "\n--- Step 3: Get Current Measuring System ---"
print_info "Getting current measuring system..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measuring_system/get" -m ""

print_info "Listening for response (5 seconds)..."
timeout 5 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measuring_system/value" -C 1 || print_warning "No response received"

print_header "\n--- Step 4: Set Measurement Mode to Bidirectional (B) ---"
print_info "Setting measurement mode to bidirectional (value=1)..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measurement_mode/set" -m "1"

print_info "Listening for status response (5 seconds)..."
timeout 5 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measurement_mode/status" -C 1 || print_warning "No status response"

print_header "\n--- Step 5: Verify Change ---"
print_info "Verifying measurement mode change..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measurement_mode/get" -m ""

print_info "Listening for response (5 seconds)..."
timeout 5 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/measurement_mode/value" -C 1 || print_warning "No response received"

print_header "\n--- Step 6: Batch Configuration Example ---"
print_info "Applying batch configuration..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/batch/set" -m '{
  "measurement_mode": 0,
  "measuring_system": 0,
  "pt_primary": 400,
  "ct_primary": 5
}'

print_info "Listening for batch result (10 seconds)..."
timeout 10 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/batch/result" -C 1 || print_warning "No batch result received"

print_header "\n--- Step 7: Create Configuration Backup ---"
print_info "Creating configuration backup..."
mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/backup" -m ""

print_info "Listening for backup data (10 seconds)..."
timeout 10 mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t "${MQTT_TOPIC}/${DEVICE_ID}/config/backup/data" -C 1 || print_warning "No backup data received"

print_header "\n--- Configuration Demo Complete ---"
print_success "Demo completed! Check responses above for configuration results."
print_info "For interactive configuration, run: ./test_mqtt_config.py"
print_info "For complete documentation, see: MQTT_CONFIGURATION.md"

print_header "\n--- Monitor All Configuration Activity ---"
print_info "To monitor all configuration activity in real-time:"
echo "mosquitto_sub -h $MQTT_BROKER -p $MQTT_PORT -t \"${MQTT_TOPIC}/+/config/+/+\" -v"

print_info "To get available parameters:"
echo "mosquitto_pub -h $MQTT_BROKER -p $MQTT_PORT -t \"${MQTT_TOPIC}/${DEVICE_ID}/config/available/get\" -m \"\""
