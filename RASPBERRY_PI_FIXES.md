# EM340D Docker Deployment - Quick Fix Guide

## Recent Fixes Applied

### 1. Docker Compose V2 Compatibility
- **Issue**: Warning about obsolete `version` attribute in docker-compose.yml
- **Fix**: Removed the `version: '3.8'` line from docker-compose.yml
- **Status**: ✅ Fixed

### 2. Python Module Import Error
- **Issue**: `ModuleNotFoundError: No module named 'minimalmodbus'`
- **Fix**: Simplified Dockerfile from multi-stage to single-stage build
- **Status**: ✅ Fixed

### 3. Enhanced Deployment Script
- **Improvement**: Added dependency testing and smart Docker Compose detection
- **Status**: ✅ Implemented

## Quick Deployment Steps

1. **Run troubleshooting script** (recommended first):
   ```bash
   chmod +x troubleshoot.sh
   ./troubleshoot.sh
   ```

2. **Clean rebuild** (if you've been testing):
   ```bash
   docker compose down
   docker system prune -f
   docker compose build --no-cache
   ```

3. **Deploy**:
   ```bash
   chmod +x docker-deploy.sh
   ./docker-deploy.sh
   ```

## Common Issues & Solutions

### Issue: "permission denied while trying to connect to the Docker daemon"
**Solution**:
```bash
sudo usermod -aG docker $USER
# Then log out and back in
```

### Issue: Container can't access USB device
**Solution**: Check your device path in docker-compose.yml:
```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0  # Adjust as needed
```

### Issue: MQTT connection fails
**Solution**: Check your .env file configuration:
```bash
MQTT_BROKER=your_mqtt_broker_ip
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=em340
```

### Issue: ModBus communication timeout
**Solution**: Verify your device configuration in config/em340.yaml:
```yaml
devices:
  - device_id: 1
    name: "EM340_Main"
    port: "/dev/ttyUSB0"
    baudrate: 9600
    parity: "N"
    timeout: 1.0
```

## Testing Your Deployment

1. **Check container status**:
   ```bash
   docker compose ps
   ```

2. **View logs**:
   ```bash
   docker compose logs -f
   ```

3. **Test inside container**:
   ```bash
   docker compose exec em340d python -c "import minimalmodbus; print('ModBus module loaded')"
   ```

## Hardware Requirements

- **Raspberry Pi**: 3B+ or newer recommended
- **Memory**: 512MB+ available
- **Storage**: 2GB+ free space
- **USB-RS485 adapter**: Connected to ModBus device

## Next Steps

After successful deployment, monitor the logs to ensure:
1. ModBus communication is working
2. MQTT messages are being published
3. No error messages in the logs

If you encounter any issues not covered here, run the troubleshooting script for detailed diagnostics.
