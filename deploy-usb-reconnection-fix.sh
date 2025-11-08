#!/bin/bash
# Quick deployment script for USB reconnection fix
# Run this script to apply the USB device reconnection improvements

set -e

echo "=========================================="
echo "EM340D USB Reconnection Fix - Deployment"
echo "=========================================="
echo

# Check if running as root for Docker operations
if [ "$EUID" -eq 0 ]; then 
    echo "Warning: Running as root. Consider using regular user with Docker permissions."
fi

# Verify Docker is installed and accessible
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo "Error: Cannot access Docker. Check permissions or Docker daemon status."
    exit 1
fi

echo "Step 1: Stopping current container..."
docker compose down

echo
echo "Step 2: Rebuilding container with new changes..."
docker compose build --no-cache

echo
echo "Step 3: Starting container with USB reconnection support..."
docker compose up -d

echo
echo "Step 4: Waiting for container to stabilize..."
sleep 5

echo
echo "Step 5: Checking container status..."
if docker ps | grep -q em340d; then
    echo "✓ Container is running"
else
    echo "✗ Container failed to start"
    echo "Check logs with: docker compose logs em340d"
    exit 1
fi

echo
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo
echo "The EM340D service now includes:"
echo "  ✓ Automatic USB device reconnection"
echo "  ✓ Exponential backoff retry logic"
echo "  ✓ Privileged mode for dynamic device access"
echo "  ✓ Full /dev mount for device resilience"
echo
echo "Next steps:"
echo "  1. Monitor logs:    docker compose logs -f em340d"
echo "  2. Test reconnection: Unplug/replug USB device"
echo "  3. Check health:    docker exec em340d python health_check.py"
echo "  4. Optional: Setup watchdog with: sudo systemctl enable em340d-watchdog"
echo
echo "For more information, see: USB_RECONNECTION.md"
echo
