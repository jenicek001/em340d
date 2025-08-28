# EM340D Docker Deployment Guide

This guide covers deploying EM340D using Docker containers, which significantly simplifies installation and management compared to the traditional systemd approach.

## Prerequisites

- Docker and Docker Compose installed
- USB-RS485 adapter connected to EM340 meter
- MQTT broker accessible from the container

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jenicek001/em340d.git
   cd em340d
   ```

2. **Run the deployment script**:
   ```bash
   ./docker-deploy.sh
   ```

3. **Edit configuration files** (when prompted):
   - `config/em340.yaml` - Device and sensor configuration
   - `.env` - MQTT broker credentials and settings

4. **Deploy the container**:
   ```bash
   ./docker-deploy.sh
   ```

## Manual Setup

If you prefer manual setup or need custom configurations:

### 1. Create Configuration Files

```bash
# Create directories
mkdir -p config logs

# Copy configuration template
cp em340.yaml.template config/em340.yaml
cp .env.template .env

# Edit with your settings
nano config/em340.yaml
nano .env
```

### 2. Configure Environment Variables

Edit `.env` file with your MQTT settings:

```bash
MQTT_BROKER=your-mqtt-broker.local
MQTT_PORT=1883
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password
MQTT_TOPIC=em340

SERIAL_DEVICE=/dev/ttyUSB0
MODBUS_ADDRESS=1
DEVICE_NAME=EM340

LOG_LEVEL=INFO
DELAY_MS=50
```

### 3. Update Device Configuration

Edit `config/em340.yaml` to match your setup. The template uses environment variables:

```yaml
config:
  device: ${SERIAL_DEVICE:/dev/ttyUSB0}
  modbus_address: ${MODBUS_ADDRESS:0x0001}
  
mqtt:
  broker: ${MQTT_BROKER:localhost}
  username: ${MQTT_USERNAME:}
  password: ${MQTT_PASSWORD:}
```

### 4. Deploy with Docker Compose

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## USB Device Access

### Single USB-RS485 Adapter

The default configuration maps `/dev/ttyUSB0` to the container:

```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```

### Multiple USB Devices

For multiple adapters or unknown device paths, use privileged mode:

```yaml
# In docker-compose.yml
privileged: true
volumes:
  - /dev:/dev
```

### Device Permissions

Ensure your user can access the USB device:

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, then check
groups | grep dialout
```

## Management Commands

### View Logs
```bash
# Live logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service logs
docker logs em340d
```

### Control Container
```bash
# Stop
docker-compose down

# Start
docker-compose up -d

# Restart
docker-compose restart

# Update to latest image
docker-compose pull && docker-compose up -d
```

### Debug Container
```bash
# Execute shell in running container
docker-compose exec em340d /bin/bash

# Run one-off commands
docker-compose run --rm em340d python -c "import yaml; print('OK')"
```

## Configuration Examples

### Home Assistant Integration

```yaml
# .env
MQTT_BROKER=homeassistant.local
MQTT_PORT=1883
MQTT_USERNAME=mqtt-user
MQTT_PASSWORD=your-password
MQTT_TOPIC=homeassistant/sensor/em340
```

### Multiple EM340 Meters

Create separate directories for each meter:

```bash
# Meter 1
mkdir -p meter1/config
cp .env.template meter1/.env
cp em340.yaml.template meter1/config/em340.yaml
cp docker-compose.yml meter1/

# Meter 2  
mkdir -p meter2/config
cp .env.template meter2/.env
cp em340.yaml.template meter2/config/em340.yaml
cp docker-compose.yml meter2/

# Edit configurations for each meter
cd meter1 && docker-compose up -d
cd ../meter2 && docker-compose up -d
```

### Remote MQTT Broker with TLS

```yaml
# .env
MQTT_BROKER=mqtt.example.com
MQTT_PORT=8883
MQTT_USE_TLS=true
MQTT_USERNAME=device123
MQTT_PASSWORD=secure-password
```

## Monitoring and Health Checks

### Container Health

Docker Compose includes health checks:

```bash
# Check health status
docker-compose ps

# Health check logs
docker inspect em340d | grep -A 10 Health
```

### Application Metrics

Monitor via MQTT messages or container logs:

```bash
# Monitor MQTT messages
mosquitto_sub -h your-broker -t "em340/+/+"

# Monitor performance
docker stats em340d
```

## Troubleshooting

### Container Won't Start

1. **Check logs**:
   ```bash
   docker-compose logs
   ```

2. **Verify configuration**:
   ```bash
   docker-compose config
   ```

3. **Test configuration**:
   ```bash
   docker-compose run --rm em340d python -c "
   from config_loader import load_yaml_with_env
   config = load_yaml_with_env('em340.yaml')
   print('Config loaded successfully')
   "
   ```

### Serial Device Issues

1. **Check device exists**:
   ```bash
   ls -la /dev/ttyUSB*
   ```

2. **Check permissions**:
   ```bash
   # Should be readable/writable by dialout group
   ls -la /dev/ttyUSB0
   
   # Check your user is in dialout group
   groups $USER | grep dialout
   ```

3. **Test serial communication**:
   ```bash
   # In container
   docker-compose exec em340d python -c "
   import serial
   ser = serial.Serial('/dev/ttyUSB0', 9600)
   print('Serial device opened successfully')
   ser.close()
   "
   ```

### MQTT Connection Issues

1. **Test MQTT connectivity**:
   ```bash
   # From host
   mosquitto_pub -h your-broker -u username -P password -t test -m "hello"
   
   # From container
   docker-compose exec em340d python -c "
   import paho.mqtt.client as mqtt
   client = mqtt.Client()
   client.connect('your-broker', 1883)
   print('MQTT connection successful')
   "
   ```

### Performance Issues

1. **Check resource usage**:
   ```bash
   docker stats em340d
   ```

2. **Adjust resource limits** in `docker-compose.yml`:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 256M
         cpus: '1.0'
   ```

## Advanced Configuration

### Custom Network

```yaml
# docker-compose.yml
networks:
  em340d_net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24

services:
  em340d:
    networks:
      - em340d_net
```

### Persistent Data

```yaml
# docker-compose.yml
volumes:
  em340d_config:
    driver: local
  em340d_logs:
    driver: local

services:
  em340d:
    volumes:
      - em340d_config:/app/config
      - em340d_logs:/app/logs
```

### Development Mode

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  em340d:
    volumes:
      - .:/app
      - /app/venv  # Exclude venv from bind mount
    environment:
      - LOG_LEVEL=DEBUG
    command: python em340.py
```

## Migration from Traditional Installation

1. **Stop existing service**:
   ```bash
   sudo systemctl stop em340d.service
   sudo systemctl disable em340d.service
   ```

2. **Backup existing configuration**:
   ```bash
   sudo cp /opt/em340d/em340.yaml ~/em340d-backup.yaml
   ```

3. **Deploy Docker version**:
   ```bash
   git pull  # Get latest Docker files
   cp ~/em340d-backup.yaml config/em340.yaml
   ./docker-deploy.sh
   ```

4. **Verify operation**:
   ```bash
   docker-compose logs -f
   ```

5. **Clean up old installation** (optional):
   ```bash
   sudo rm -rf /opt/em340d
   sudo rm /etc/systemd/system/em340d.service
   sudo systemctl daemon-reload
   ```

## Benefits of Docker Deployment

| Aspect | Traditional | Docker |
|--------|------------|--------|
| Installation | Complex (15+ steps) | Simple (3 steps) |
| Root access | Required | Not required |
| Dependencies | System-wide | Isolated |
| Updates | Manual/complex | Automated |
| Rollback | Difficult | Easy |
| Multiple instances | Complex | Simple |
| Portability | Limited | High |

The Docker approach provides a much cleaner, more maintainable deployment while preserving all functionality.
