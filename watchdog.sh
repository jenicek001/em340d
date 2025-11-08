#!/bin/bash
# Watchdog script for EM340D Docker container
# Monitors USB device availability and container health
# Can be run as a systemd service or cron job

set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-em340d}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
LOG_FILE="${LOG_FILE:-/var/log/em340d-watchdog.log}"
MAX_FAILED_CHECKS="${MAX_FAILED_CHECKS:-3}"

# Counter for consecutive failed checks
failed_checks=0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

check_container_running() {
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        return 0
    else
        return 1
    fi
}

check_container_health() {
    # Check if container is running
    if ! check_container_running; then
        log "WARNING: Container ${CONTAINER_NAME} is not running"
        return 1
    fi
    
    # Check container health status
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "none")
    
    if [ "$health_status" = "healthy" ]; then
        return 0
    elif [ "$health_status" = "none" ]; then
        # No health check configured, assume OK if running
        return 0
    else
        log "WARNING: Container health status: $health_status"
        return 1
    fi
}

check_usb_device() {
    # Get device path from container environment
    device_path=$(docker inspect --format='{{range .Config.Env}}{{println .}}{{end}}' "${CONTAINER_NAME}" | grep SERIAL_DEVICE | cut -d= -f2 || echo "/dev/ttyUSB0")
    
    # Check if device exists on host
    if [ -e "$device_path" ]; then
        return 0
    else
        log "WARNING: USB device $device_path not found on host"
        return 1
    fi
}

restart_container() {
    log "Restarting container ${CONTAINER_NAME}..."
    
    if docker restart "${CONTAINER_NAME}"; then
        log "Container ${CONTAINER_NAME} restarted successfully"
        failed_checks=0
        return 0
    else
        log "ERROR: Failed to restart container ${CONTAINER_NAME}"
        return 1
    fi
}

send_alert() {
    local message="$1"
    log "ALERT: $message"
    
    # Add your alerting mechanism here (email, webhook, etc.)
    # Example: curl -X POST https://your-webhook-url -d "message=$message"
}

main() {
    log "Starting EM340D watchdog (check interval: ${CHECK_INTERVAL}s)"
    
    while true; do
        if check_container_health && check_usb_device; then
            # All checks passed
            if [ $failed_checks -gt 0 ]; then
                log "Health checks passed after previous failures"
            fi
            failed_checks=0
        else
            # At least one check failed
            ((failed_checks++))
            log "Health check failed (attempt $failed_checks/$MAX_FAILED_CHECKS)"
            
            if [ $failed_checks -ge $MAX_FAILED_CHECKS ]; then
                log "Maximum failed checks reached, attempting restart"
                if restart_container; then
                    send_alert "EM340D container restarted after $failed_checks failed health checks"
                else
                    send_alert "Failed to restart EM340D container after $failed_checks failed health checks"
                fi
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Handle signals for clean shutdown
trap 'log "Watchdog stopped"; exit 0' SIGTERM SIGINT

main
