#!/bin/bash
# Quick test script to verify USB reconnection works
# This script helps you test the USB device reconnection feature

echo "=========================================="
echo "USB Reconnection Test Guide"
echo "=========================================="
echo
echo "This will help you verify that the USB reconnection works correctly."
echo

# Check if container is running
if ! docker ps | grep -q em340d; then
    echo "Error: Container em340d is not running"
    echo "Start it with: docker compose up -d"
    exit 1
fi

echo "Container is running. Current status:"
docker compose ps
echo

echo "=========================================="
echo "Test Instructions:"
echo "=========================================="
echo
echo "1. In this terminal, start watching logs:"
echo "   docker compose logs -f em340d"
echo
echo "2. In another terminal, check the device:"
echo "   ls -l /dev/serial/by-id/"
echo
echo "3. Physically unplug the USB-Serial device"
echo "   OR simulate disconnection with:"
echo "   sudo modprobe -r ch341  # For CH341 USB-Serial"
echo "   sudo modprobe -r ftdi_sio  # For FTDI devices"
echo
echo "4. Watch the logs - you should see:"
echo "   - 'Failed to read from ModBus device...'"
echo "   - 'Serial device disconnected. Attempting reconnection...'"
echo "   - 'Waiting X.Xs before reconnection attempt...'"
echo
echo "5. Plug the device back in"
echo "   OR reload the module:"
echo "   sudo modprobe ch341  # or ftdi_sio"
echo
echo "6. Watch for successful reconnection:"
echo "   - 'Connection successful! Measurement mode: ...'"
echo "   - 'Successfully reconnected to serial device. Resuming operations.'"
echo
echo "7. Verify data continues flowing to MQTT"
echo
echo "=========================================="
echo "Automated Log Monitoring"
echo "=========================================="
echo
echo "Press Ctrl+C to stop monitoring"
echo

# Start log monitoring
docker compose logs -f em340d
