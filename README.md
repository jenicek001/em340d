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
- **Remote Configuration**: Configure EM340 parameters via MQTT topics with validation
- **Optimized Performance**: 87% reduction in ModBus calls through intelligent block reading
- **Docker Support**: Easy deployment with Docker Compose
- **Comprehensive Logging**: Timestamped logs with multiple levels and rotation
- **Environment Variables**: Flexible configuration via .env files
- **Health Monitoring**: Built-in health checks and diagnostic tools
- **Serial Port Management**: Automatic detection and permission handling
- **Configuration Management**: Backup, restore, and factory reset capabilities

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
   MODBUS_ADDRESS=1              # EM340 ModBus slave address
   
   # Application Configuration
   LOG_LEVEL=INFO
   DELAY_MS=50
   ```

4. **Set up serial port access**:
   ```bash
   # Automated setup: configures user IDs and serial access
   ./setup-docker-user.sh
   
   # This script will:
   # - Add your current user to dialout group
   # - Update .env with your user ID/group ID  
   # - Configure proper container permissions
   # - Detect dialout group ID automatically
   
   # Manual alternative (if you prefer):
   # sudo usermod -aG dialout $USER
   # # Then update .env with: USER_ID=$(id -u), GROUP_ID=$(id -g)
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

#### 🔄 **Auto-Start on Boot (Optional)**

To make EM340D start automatically when your Raspberry Pi reboots:

```bash
# Run the auto-start installation script
./install-autostart.sh

# Or manually enable Docker auto-start (simple method)
sudo systemctl enable docker
docker compose up -d  # Container will restart automatically
```

**Service Management:**
```bash
# Control the service easily
./em340d-service.sh start    # Start service
./em340d-service.sh stop     # Stop service  
./em340d-service.sh status   # Check status
./em340d-service.sh logs     # View logs
./em340d-service.sh test     # Test MQTT connectivity
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

### Serial Device Path Configuration
- **Test connectivity**: `ls -la /dev/ttyUSB* /dev/ttyACM*`
- **Find stable device ID**: `ls -la /dev/serial/by-id/`
- **Use stable path in .env**:
  ```bash
  # Recommended (stable across reboots):
  SERIAL_DEVICE=/dev/serial/by-id/usb-1a86_USB_Single_Serial_56EC017080-if00
  
  # Alternative (may change on reboot):
  SERIAL_DEVICE=/dev/ttyACM0
  ```

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

### Sensor Data Publishing
The application publishes JSON sensor data to the topic: `{MQTT_TOPIC}/{DEVICE_NAME}`

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

### Remote Configuration via MQTT 🆕
The application also supports remote configuration of EM340 parameters via MQTT:

**Configuration Topics:**
- `{MQTT_TOPIC}/{DEVICE_ID}/config/{parameter}/set` - Set parameter value
- `{MQTT_TOPIC}/{DEVICE_ID}/config/{parameter}/get` - Get parameter value  
- `{MQTT_TOPIC}/{DEVICE_ID}/config/batch/set` - Batch configuration
- `{MQTT_TOPIC}/{DEVICE_ID}/config/backup` - Create configuration backup
- `{MQTT_TOPIC}/{DEVICE_ID}/config/restore` - Restore configuration

**Example Configuration Commands:**
```bash
# Set measurement mode to bidirectional (B)
mosquitto_pub -h localhost -t "em340/235411W/config/measurement_mode/set" -m "1"

# Set measuring system to 3-phase without neutral  
mosquitto_pub -h localhost -t "em340/235411W/config/measuring_system/set" -m "1"

# Batch configuration
mosquitto_pub -h localhost -t "em340/235411W/config/batch/set" -m '{
  "measurement_mode": 0,
  "measuring_system": 0,
  "pt_primary": 400
}'
```

**Supported Parameters:**
- `measuring_system` (0=3P+N, 1=3P, 2=2P+N) - Electrical connection type
- `measurement_mode` (0=Easy/A, 1=Bidirectional/B) - Energy measurement mode
- `pt_primary`/`pt_secondary` - Potential transformer ratios
- `ct_primary`/`ct_secondary` - Current transformer ratios

For complete configuration documentation, see **[MQTT_CONFIGURATION.md](MQTT_CONFIGURATION.md)**.

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
- ✅ **Check MQTT broker is running**: `mosquitto_pub -h localhost -t test -m "test"`
- ✅ **For Docker deployment**: Container uses host networking - broker should be on `localhost`
- ✅ **Verify .env configuration**:
  ```bash
  # With host networking (recommended):
  MQTT_BROKER=localhost
  
  # Or use Raspberry Pi's IP address:  
  MQTT_BROKER=192.168.1.100  # Replace with your Pi's IP
  ```
- ✅ **Test MQTT connectivity**: `mosquitto_sub -h localhost -t em340/+`
- ✅ **Check firewall settings** on MQTT broker host

#### 2. **Serial Port Permission Denied**
```
PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'
```

**Solutions**:
```bash
# Use automated setup (recommended)
./setup-docker-user.sh

# Or manual setup:
# 1. Check device exists and permissions
ls -la /dev/ttyUSB*

# 2. Add current user to dialout group  
sudo usermod -aG dialout $USER

# 3. Update .env with your user IDs
echo "USER_ID=$(id -u)" >> .env
echo "GROUP_ID=$(id -g)" >> .env
echo "DIALOUT_GID=$(getent group dialout | cut -d: -f3)" >> .env

# 4. Log out and back in, then rebuild container
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

#### 6. **Configuration File Errors**
```
Error loading YAML file: 'config'
KeyError: 'mqtt'
KeyError: 'broker' 
```

**Solutions**:
```bash
# Check configuration file exists
ls -la config/em340.yaml em340.yaml

# Validate YAML syntax
python -c "import yaml; yaml.load(open('config/em340.yaml'), Loader=yaml.FullLoader)"

# Check for missing sections
grep -A5 "^config:" config/em340.yaml
grep -A5 "^mqtt:" config/em340.yaml  
grep -A5 "^sensor:" config/em340.yaml

# Verify environment variables
env | grep -E "(MQTT_|SERIAL_|MODBUS_|DEVICE_)"

# Reset configuration from template
cp .env.template .env.new
cp em340.yaml.template em340.yaml.new
# Compare and merge: diff .env .env.new
```

**Required Configuration Sections:**
```yaml
# Minimum required structure
config:
  device: /dev/ttyUSB0         # Required
  modbus_address: 1            # Required  
  t_delay_ms: 50              # Required
  serial_number: EM340_TEST   # Required

mqtt:
  broker: localhost           # Required
  port: 1883                  # Required
  username: ""                # Optional (can be empty)
  password: ""                # Optional (can be empty)  
  topic: em340               # Required

sensor: []                    # Required (array, can be empty for testing)
```

#### 7. **Environment Variable Issues**
```
Required environment variable 'MQTT_BROKER' is not set
```

**Solutions**:
```bash
# Check .env file exists and has values
cat .env | grep MQTT_BROKER

# Verify environment variable loading
docker compose config  # Shows resolved configuration

# Test without Docker
export MQTT_BROKER=localhost
python -c "import os; print(os.getenv('MQTT_BROKER'))"

# Fix missing required variables
echo "MQTT_BROKER=localhost" >> .env
echo "SERIAL_DEVICE=/dev/ttyUSB0" >> .env  
echo "DEVICE_SERIAL_NUMBER=TEST123A" >> .env
```

#### 8. **MQTT Configuration Issues** 🆕
```
Configuration command not applied
No response from configuration service
```

**Solutions**:
```bash
# Check configuration service status
./logs.sh -f | grep -i config

# Test MQTT configuration connectivity
./demo_mqtt_config.sh

# Monitor configuration activity
mosquitto_sub -h localhost -t "em340/+/config/+/+" -v

# Check available parameters
mosquitto_pub -h localhost -t "em340/235411W/config/available/get" -m ""

# Verify parameter ranges and values
# See MQTT_CONFIGURATION.md for valid values
```

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

#### 🔄 **Updating EM340D**

**Standard Update Process:**
```bash
# Stop the service (if using systemd)
./em340d-service.sh stop

# Or stop Docker manually
docker compose down

# Pull latest changes from GitHub
git pull origin main

# Rebuild and restart with new version
./quick-rebuild.sh

# Verify the update
./em340d-service.sh status
```

**Check for Updates:**
```bash
# Check if updates are available
git fetch origin
git status

# Show what's changed since your version
git log HEAD..origin/main --oneline

# Show differences in files
git diff HEAD..origin/main
```

#### 🚨 **Update Scenarios**

**1. Configuration File Changes:**
```bash
# If configuration templates change
cp .env.template .env.new
cp em340.yaml.template em340.yaml.new

# Compare with your current settings
diff .env .env.new
diff em340.yaml em340.yaml.new

# Merge changes manually, then cleanup
rm .env.new em340.yaml.new
```

**2. Breaking Changes:**
```bash
# For major updates, backup your configuration
cp .env .env.backup
cp em340.yaml em340.yaml.backup

# Follow migration guide in release notes
git log --grep="BREAKING" --oneline

# Test with backup configuration if needed
```

**3. Docker Image Updates:**
```bash
# Force rebuild with no cache (for system dependencies)
./quick-rebuild.sh --no-cache

# Or manually:
docker compose build --no-cache
docker compose up -d
```

#### 📋 **Update Checklist**

**Before Updating:**
- [ ] Check current version: `git log --oneline -1`
- [ ] Backup configuration: `cp .env .env.backup`
- [ ] Note current container status: `docker compose ps`
- [ ] Check application logs for issues: `./logs.sh -t 20`

**After Updating:**
- [ ] Verify service starts: `./em340d-service.sh status`
- [ ] Test MQTT connectivity: `./test-mqtt-connectivity.sh`
- [ ] Check for errors: `./logs.sh -t 10 -l ERROR`
- [ ] Verify data publishing: `mosquitto_sub -h localhost -t em340/+`
- [ ] Test serial device access: `./test-serial-docker.sh`

#### 🔧 **Maintenance Tasks**

**Regular Maintenance (Monthly):**
```bash
# Clean up Docker resources
docker system prune -f

# Check log sizes
du -sh logs/
docker system df

# Update system packages (Raspberry Pi)
sudo apt update && sudo apt upgrade -y

# Check for EM340D updates
git fetch && git status
```

**Log Management:**
```bash
# View disk usage
df -h
docker system df

# Clean old logs (Docker handles rotation)
# Manual log cleanup if needed:
docker compose down
docker volume ls | grep logs
# docker volume rm em340d_em340d_logs  # Only if needed
```

**Reset Everything (Nuclear Option):**
```bash
# WARNING: This deletes all data and logs!
./em340d-service.sh stop
docker compose down -v
docker system prune -a -f
rm -f .env em340.yaml  # Remove local config
git pull
cp .env.template .env  # Reconfigure from scratch
cp em340.yaml.template em340.yaml
```

#### 📝 **Version Information**

**Check Current Version:**
```bash
# Git information
git log --oneline -5
git describe --tags --always

# Docker image information  
docker compose images
docker inspect em340d | grep -i created
```

**Release Notes:**
- Check GitHub releases: https://github.com/jenicek001/em340d/releases
- Review CHANGELOG.md for version-specific changes
- Monitor for security updates and bug fixes

## 🧪 **Testing and Validation**

### Test MQTT Connectivity
```bash
# Subscribe to your EM340D topic
mosquitto_sub -h YOUR_BROKER_IP -t "em340/+" -v

# Should see data like:
# em340/235411W {"voltage_l1": 230.5, "current_l1": 12.34, ...}
```

### Test MQTT Configuration 🆕
```bash
# Run interactive configuration tool
./test_mqtt_config.py

# Run configuration demo
./test_mqtt_config.py demo

# Manual configuration test
mosquitto_pub -h localhost -t "em340/235411W/config/measurement_mode/get" -m ""
mosquitto_sub -h localhost -t "em340/235411W/config/+/+" -v
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

## � **Reliability and Retry Mechanisms**

### MQTT Resilience ✅
The application has robust MQTT reconnection capabilities:

- **Automatic Reconnection**: 2-30 seconds with exponential backoff
- **Background Monitoring**: Connection managed in separate thread  
- **Publish Resilience**: Failed publishes logged but don't crash application
- **Network Recovery**: Automatically resumes when MQTT broker returns

```python
# MQTT reconnection settings (built-in)
min_delay: 2 seconds     # Initial retry delay
max_delay: 30 seconds    # Maximum retry delay  
automatic: yes           # Background reconnection
```

### ModBus Connection ⚠️
Current ModBus handling has some limitations:

**What Works:**
- **Timeout Protection**: 500ms timeout per operation prevents hanging
- **Block-Level Recovery**: Failed blocks skipped, other sensors continue
- **Rate Limiting**: 50ms delay between operations prevents device overload

**Limitations:**
- **No USB reconnection**: Device disconnect requires container restart
- **No automatic retry**: Failed reads are skipped until next cycle
- **Fixed timeout**: Not configurable per sensor type

```yaml
# Current ModBus settings
config:
  t_delay_ms: 50           # Delay between ModBus operations
  # Serial timeout: 500ms  # Hard-coded in application
```

**Improvement Suggestions:**
1. Add configurable ModBus timeouts
2. Implement USB device reconnection detection
3. Add configurable retry counts for failed reads

### Container-Level Recovery ✅
Multiple layers ensure service availability:

```yaml
# Docker auto-restart
restart: unless-stopped

# Health monitoring  
healthcheck:
  interval: 30s
  retries: 3
  
# Systemd integration
Restart: always
```

### Configuration Error Handling ✅
The application has comprehensive configuration validation:

**Application Startup:**
- **Missing config file**: Application exits with clear error message
- **Missing YAML sections**: Application exits immediately with KeyError details
- **Missing required keys**: Application exits with specific missing parameter name
- **Invalid environment variables**: Application exits with validation error

**Runtime Configuration Errors:**
- **Missing sensor parameters**: Application exits during sensor processing with KeyError
- **Invalid sensor configuration**: Application logs error and exits gracefully

```python
# Configuration validation examples:
try:
    config = load_yaml_with_env('em340.yaml')
    device = config['config']['device']       # Required - will exit if missing
    broker = config['mqtt']['broker']         # Required - will exit if missing
except KeyError as e:
    log.error(f'Error in yaml config file: {e}')
    sys.exit()  # Clean application exit
```

**Environment Variable Validation:**
```yaml
# Required variables (no default) - will exit if missing
device: ${SERIAL_DEVICE}

# Variables with defaults - will use default if missing  
broker: ${MQTT_BROKER:localhost}
port: ${MQTT_PORT:1883}
```

**Behavior Summary:**
- **Startup errors**: Application exits immediately with descriptive error
- **Runtime sensor errors**: Application exits during sensor initialization
- **Docker auto-restart**: Container automatically restarts after configuration fix
- **Log visibility**: All configuration errors clearly logged before exit

## �🔧 **Advanced Configuration**

### Reliability Tuning
```yaml
# Adjust for your network conditions
config:
  t_delay_ms: 100         # Increase for unreliable serial connections
  
# MQTT settings for poor connectivity  
mqtt:
  broker: 192.168.1.100   # Use IP instead of hostname for faster resolution
  port: 1883              # Standard port
  
# Enhanced logging for troubleshooting
logger:
  log_level: DEBUG        # Detailed connection information
```

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
- **`test_mqtt_config.py`** 🆕 - Interactive MQTT configuration tool
- **`update.sh`** 🆕 - Automated update script with backup and verification

### Documentation
- **`LOGGING_GUIDE.md`** - Comprehensive logging documentation
- **`DOCKER_SERIAL_FIX.md`** - Docker serial port access solutions
- **`SERIAL_ACCESS_SOLUTIONS.md`** - Serial port permission solutions
- **`MQTT_CONFIGURATION.md`** 🆕 - Complete MQTT configuration guide

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
| Configuration not working | Run `./demo_mqtt_config.sh` |
| Config service not responding | Check logs: `./logs.sh -f | grep -i config` |

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


