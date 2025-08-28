# EM340D - Carlo Gavazzi EM340 ModBus to MQTT Gateway

A robust daemon that reads data from Carlo Gavazzi EM340 Smart Meters via RS485/ModBus RTU protocol and publishes the data to MQTT brokers. Designed for reliable deployment on embedded systems including Raspberry Pi.

Data is published to: `{MQTT_TOPIC}/{DEVICE_SERIAL_NUMBER}`

Example: `em340/235411W`

```json
{
  "voltage_l1": 230.5,
  "voltage_l2": 231.2,
  "voltage_l3": 229.8,
  "current_l1": 12.34,
  "current_l2": 11.87,
  "current_l3": 12.56,
  "active_power_sys": 8234.5,
  "total_energy_import": 12345.678,
  "frequency": 50.0,
  "last_seen": "2024-01-15T14:30:25+01:00"
}
```

## 🔧 **Features**

- **ModBus RTU Communication**: Read 30+ sensor values from EM340 meters
- **MQTT Integration**: Publish data to any MQTT broker with automatic reconnection
- **Optimized Performance**: 87% reduction in ModBus calls through intelligent block reading
- **Docker Support**: Easy deployment with Docker Compose
- **Comprehensive Logging**: Timestamped logs with multiple levels and rotation
- **Environment Variables**: Flexible configuration via .env files
- **Health Monitoring**: Built-in health checks and diagnostic tools
- **Serial Port Management**: Automatic detection and permission handling

## 📋 **Quick Start**

### Prerequisites
- Linux system (Ubuntu, Raspberry Pi OS, etc.)
- USB-RS485 converter (e.g., CH340-based)
- Carlo Gavazzi EM340 meter with RS485 connection
- MQTT broker (Mosquitto, Home Assistant, etc.)

### Installation Options

#### 🐳 **Docker Deployment (Recommended)**

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jenicek001/em340d.git
   cd em340d
   ```

2. **Set up configuration**:
   ```bash
   # Create environment file
   cp .env.template .env
   
   # Create configuration directory and file
   mkdir -p config
   cp em340.yaml.template config/em340.yaml
   
   # Note: em340.yaml and .env files are in .gitignore (contain user-specific settings)
   ```

3. **Configure MQTT settings** (edit `.env`):
   ```bash
   nano .env
   ```
   ```bash
   # MQTT Broker Configuration
   MQTT_BROKER=192.168.1.100    # Your MQTT broker IP
   MQTT_PORT=1883
   MQTT_USERNAME=your_username   # Optional
   MQTT_PASSWORD=your_password   # Optional
   MQTT_TOPIC=em340
   
   # Serial Device Configuration  
   SERIAL_DEVICE=/dev/ttyUSB0
# EM340 Device Identification
# Carlo Gavazzi EM340 serial number - used as MQTT subtopic
# Format: 6 digits + 1 letter (e.g., "235411W")
# You can find this on the EM340 device label
DEVICE_SERIAL_NUMBER=235411W

# ModBus Settings
MODBUS_ADDRESS=1              # EM340 ModBus slave address   # Application Configuration
   LOG_LEVEL=INFO
   DELAY_MS=50
   ```

4. **Set up serial port access**:
   ```bash
   # Add current user to dialout group
   sudo usermod -aG dialout $USER
   
   # Create em340 user for container
   sudo useradd -m -G dialout em340
   
   # Or use automated setup
   sudo ./setup-serial-access.sh
   ```

5. **Deploy with Docker**:
   ```bash
   # Automated deployment with diagnostics
   ./quick-rebuild.sh
   
   # Or manual deployment
   docker compose up -d
   ```

6. **Monitor the application**:
   ```bash
   # Real-time logs with colors and filtering
   ./logs.sh -f
   
   # Check system status
   ./troubleshoot.sh
   ```

#### 📦 **Direct Python Installation**

1. **Install system dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3-venv python3-pip git
   ```

2. **Clone and setup**:
   ```bash
   git clone https://github.com/jenicek001/em340d.git
   cd em340d
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Configure the application**:
   ```bash
   # Copy and edit configuration
   cp em340.yaml.template em340.yaml
   nano em340.yaml
   ```
   
   Edit the MQTT section:
   ```yaml
   mqtt:
     broker: 192.168.1.100      # Your MQTT broker IP
     port: 1883
     username: your_username    # Optional
     password: your_password    # Optional
     topic: em340
   ```

4. **Set up serial port access**:
   ```bash
   sudo usermod -aG dialout $USER
   # Log out and back in for group changes to take effect
   ```

5. **Run the application**:
   ```bash
   source venv/bin/activate
   python em340.py
   ```

## 🔗 **Hardware Connection**

### EM340 to USB-RS485 Wiring
```
EM340 Meter    USB-RS485 Converter
-----------    -------------------
A+ (Terminal)  →  A+ or D+
B- (Terminal)  →  B- or D-
GND           →  GND (if available)
```

### Connection Tips
- Connect EM340 terminating resistor jumper
- Check voltages: A+ ≈ 4V, B- ≈ 1V relative to GND
- Use shielded cable for long distances
- Test connectivity with `ls -la /dev/ttyUSB*`

## ⚙️ **Configuration Guide**

### Environment Variables (.env file)
The application supports flexible configuration through environment variables:

```bash
# MQTT Broker Settings
MQTT_BROKER=localhost          # MQTT broker hostname/IP
MQTT_PORT=1883                # MQTT broker port
MQTT_USERNAME=                # MQTT username (optional)
MQTT_PASSWORD=                # MQTT password (optional)
MQTT_TOPIC=em340              # MQTT topic prefix

# Serial/ModBus Settings
SERIAL_DEVICE=/dev/ttyUSB0    # Serial device path
MODBUS_ADDRESS=1              # EM340 ModBus slave address

# Device Identification
# Carlo Gavazzi EM340 serial number - used as MQTT subtopic identifier
# Format: 6 digits + 1 letter (e.g., "235411W")
# You can find this on the EM340 device label
DEVICE_SERIAL_NUMBER=235411W

# Application Settings
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR, CRITICAL
DELAY_MS=50                   # Delay between ModBus reads (ms)
TZ=UTC                        # Timezone for timestamps
```

### YAML Configuration (config/em340.yaml or em340.yaml)
The application uses a template-based configuration system. The `em340.yaml.template` file contains placeholders that are replaced with environment variables:

```yaml
mqtt:
  broker: ${MQTT_BROKER:localhost}     # Uses MQTT_BROKER env var, defaults to localhost
  port: ${MQTT_PORT:1883}              # Uses MQTT_PORT env var, defaults to 1883
  username: ${MQTT_USERNAME:}          # Optional username
  password: ${MQTT_PASSWORD:}          # Optional password
  topic: ${MQTT_TOPIC:em340}          # Topic prefix
```

### Docker vs Direct Installation Configuration

| Installation Type | Configuration File | Environment Variables |
|-------------------|--------------------|--------------------|
| **Docker** | `config/em340.yaml` (template) | `.env` file |
| **Direct Python** | `em340.yaml` (static) | System environment |

## 📊 **MQTT Data Format**

The application publishes JSON data to the topic: `{MQTT_TOPIC}/{DEVICE_NAME}`

Example: `em340/EM340_Main`

```json
{
  "voltage_l1": 230.5,
  "voltage_l2": 231.2,
  "voltage_l3": 229.8,
  "current_l1": 12.34,
  "current_l2": 11.87,
  "current_l3": 12.56,
  "active_power_sys": 8234.5,
  "total_energy_import": 12345.678,
  "frequency": 50.0,
  "last_seen": "2024-01-15T14:30:25+01:00"
}
```

## 🛠️ **Troubleshooting**

### Quick Diagnostics
```bash
# Run comprehensive system check
./troubleshoot.sh

# Check real-time logs
./logs.sh -f

# Show only errors from last hour  
./logs.sh -s "1h" -l ERROR
```

### Common Issues

#### 1. **MQTT Connection Failed**
```
ERROR: Initial MQTT connection failed: [Errno 111] Connection refused
```

**Solutions**:
- ✅ Check MQTT broker is running: `mosquitto_pub -h YOUR_BROKER_IP -t test -m "test"`
- ✅ Verify MQTT_BROKER IP address in `.env` file
- ✅ Check firewall settings on broker
- ✅ Test with simple MQTT client: `mosquitto_sub -h YOUR_BROKER_IP -t em340/+`

#### 2. **Serial Port Permission Denied**
```
PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'
```

**Solutions**:
```bash
# Check device exists and permissions
ls -la /dev/ttyUSB*

# Add user to dialout group
sudo usermod -aG dialout $USER
sudo usermod -aG dialout em340  # For Docker

# Log out and back in, then test
groups $USER  # Should show dialout

# For Docker, rebuild container
./quick-rebuild.sh
```

#### 3. **ModBus Communication Timeout**
```
ERROR: Failed to read from ModBus device: Timeout
```

**Solutions**:
- ✅ Check physical connections (A+/B-, terminating resistor)
- ✅ Verify EM340 ModBus address: `MODBUS_ADDRESS=1` or `2`
- ✅ Test with different baud rates
- ✅ Check cable length and shielding

#### 4. **Container Log Permission Issues**
```
PermissionError: Permission denied: '/app/logs/em340d.log'
```

**Solution**:
```bash
# Rebuild container with proper permissions
./quick-rebuild.sh
```

#### 5. **Docker Compose Version Issues**
```
WARN: the attribute `version` is obsolete
```

**Solution**: Already fixed in current version. Update your `docker-compose.yml`.

### Log Analysis

#### Monitor Application Startup
```bash
./logs.sh -t 20 -l INFO  # Last 20 lines, INFO level and above
```

#### Track MQTT Issues
```bash
./logs.sh -f | grep -i mqtt  # Follow logs, filter for MQTT
```

#### Monitor ModBus Performance
```bash
./logs.sh -f | grep -i "organized.*blocks"  # Watch block optimization
```

## 📈 **Performance Monitoring**

### ModBus Optimization
The application uses intelligent block reading:
- **Before**: 30 individual ModBus calls per reading cycle
- **After**: 4 block reads (87% reduction)
- **Efficiency**: 98.2% register utilization

### Monitor Performance
```bash
# Check block organization
./logs.sh | grep "Organized.*blocks"

# Example output:
# Organized 30 sensors into 4 blocks:
#   Block 1: 0x0000-0x0033 (52 regs) - Voltage L1-N, Voltage L2-N, ...
#   Block 2: 0x0034-0x0035 (2 regs) - Total Energy Import
```

## 🐳 **Docker Management**

### Essential Commands
```bash
# Start services
docker compose up -d

# Stop services  
docker compose down

# View logs
./logs.sh -f                    # Enhanced viewer
docker compose logs -f          # Standard Docker logs

# Rebuild after changes
./quick-rebuild.sh              # Automated rebuild
docker compose build --no-cache # Manual rebuild

# Check container status
docker compose ps

# Execute commands in container
docker compose exec em340d ls -la /dev/ttyUSB0
```

### Updates and Maintenance
```bash
# Update application
git pull
./quick-rebuild.sh

# Clean up Docker resources
docker system prune -f

# Reset everything (deletes data!)
docker compose down -v
docker system prune -a -f
```

## 🧪 **Testing and Validation**

### Test MQTT Connectivity
```bash
# Subscribe to your EM340D topic
mosquitto_sub -h YOUR_BROKER_IP -t "em340/+" -v

# Should see data like:
# em340/EM340_Main {"voltage_l1": 230.5, "current_l1": 12.34, ...}
```

### Test Serial Device Access
```bash
# Check device permissions
ls -la /dev/ttyUSB0

# Test basic serial communication
sudo stty -F /dev/ttyUSB0 9600 raw -echo
```

### Test ModBus Communication
```bash
# Use the included configuration tool
python em340config.py  # Configure EM340 meter settings
```

## 🔧 **Advanced Configuration**

### Custom Sensor Selection
Edit `config/em340.yaml` to skip unwanted sensors:

```yaml
sensor:
  - id: voltage_l1
    name: "Voltage L1-N"
    # ... other settings ...
    skip: false    # Set to true to disable this sensor
```

### Performance Tuning
```yaml
config:
  t_delay_ms: 50    # Reduce for faster polling (min ~20ms)
  
logger:
  log_level: INFO   # Use DEBUG for detailed troubleshooting
```

### MQTT Topics Customization
Data is published to: `{MQTT_TOPIC}/{DEVICE_NAME}`

For multiple meters:
```bash
# Device 1
DEVICE_SERIAL_NUMBER=235411W
MODBUS_ADDRESS=1

# Device 2  
DEVICE_SERIAL_NUMBER=567892X
MODBUS_ADDRESS=2
```

## 📚 **File Reference**

### Key Files
- **`.env`** - Environment variables (Docker)
- **`config/em340.yaml`** - Configuration file (Docker)
- **`em340.yaml`** - Configuration file (Direct installation)
- **`docker-compose.yml`** - Docker services definition
- **`requirements.txt`** - Python dependencies

### Scripts
- **`quick-rebuild.sh`** - Fast Docker rebuild and deployment
- **`logs.sh`** - Enhanced log viewer with filtering
- **`troubleshoot.sh`** - System diagnostic tool
- **`setup-serial-access.sh`** - Serial port permissions setup

### Documentation
- **`LOGGING_GUIDE.md`** - Comprehensive logging documentation
- **`DOCKER_SERIAL_FIX.md`** - Docker serial port access solutions
- **`SERIAL_ACCESS_SOLUTIONS.md`** - Serial port permission solutions

## 📞 **Support**

### Getting Help
1. **Run diagnostics**: `./troubleshoot.sh`
2. **Check logs**: `./logs.sh -f -l ERROR`
3. **Verify configuration**: Check `.env` and `config/em340.yaml`
4. **Test hardware**: Verify USB-RS485 connection and EM340 wiring

### Common Solutions Summary
| Issue | Quick Fix |
|-------|-----------|
| MQTT connection failed | Check `MQTT_BROKER` in `.env` |
| Serial permission denied | Run `sudo ./setup-serial-access.sh` |
| Container won't start | Run `./quick-rebuild.sh` |
| No data published | Check ModBus address and wiring |
| Log permission errors | Rebuild container: `./quick-rebuild.sh` |

---

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🙏 **Acknowledgments**

- Carlo Gavazzi EM340 configuration heavily reused from [esphome-modbus](https://github.com/martgras/esphome-modbus)
- ModBus RTU protocol implementation using [MinimalModbus](https://pypi.org/project/MinimalModbus/)
- MQTT client based on [paho-mqtt](https://pypi.org/project/paho-mqtt/)


