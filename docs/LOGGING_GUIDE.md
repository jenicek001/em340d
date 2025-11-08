# EM340D Enhanced Logging Guide

## Quick Commands

### Real-time Log Monitoring
```bash
# Follow logs in real-time with timestamps and color coding
./logs.sh -f

# Follow only ERROR level logs
./logs.sh -f -l ERROR

# Show logs from last 30 minutes
./logs.sh -s "30m" -f
```

### Historical Log Analysis
```bash
# Show last 50 lines with formatting
./logs.sh -t 50

# Show logs from last 2 hours
./logs.sh -s "2h"

# Show only WARNING and ERROR logs from last hour
./logs.sh -s "1h" -l WARNING
```

### Raw Docker Logs
```bash
# Show raw Docker logs with timestamps (no formatting)
./logs.sh -r

# Follow raw logs
./logs.sh -r -f
```

## New Logging Features

### 1. **Timestamped Console Output**
- All console logs now include timestamps: `2024-01-15 14:30:25 [INFO] Message`
- Both file and console logs have consistent formatting

### 2. **Enhanced Log Viewer (`logs.sh`)**
- **Color-coded log levels**: 
  - 🟣 DEBUG (Purple)
  - 🟢 INFO (Green) 
  - 🟡 WARNING (Yellow)
  - 🔴 ERROR/CRITICAL (Red)
- **Timestamp formatting**: Converts ISO timestamps to readable format
- **Level filtering**: Show only specific log levels
- **Time-based filtering**: Show logs from specific time periods
- **Follow mode**: Real-time log monitoring

### 3. **Better Docker Integration**
- Docker logs now include proper timestamps
- Container name clearly visible in logs
- Log rotation configured (10MB max, 3 files)

### 4. **Improved Application Startup Logging**
- Clear application startup sequence
- Configuration validation messages  
- MQTT connection status tracking
- ModBus initialization details

## Log Level Filtering Examples

```bash
# Show only errors and critical issues
./logs.sh -l ERROR

# Show info, warning, error, and critical (no debug)
./logs.sh -l INFO

# Show all levels (default behavior)
./logs.sh
```

## Time-based Filtering Examples

```bash
# Last 30 minutes
./logs.sh -s "30m"

# Last 2 hours
./logs.sh -s "2h"

# Since specific timestamp
./logs.sh -s "2024-01-15T10:00:00"

# Today's logs (from midnight)
./logs.sh -s "$(date '+%Y-%m-%d')T00:00:00"
```

## Troubleshooting with Logs

### 1. **Application Startup Issues**
```bash
# Check recent startup logs
./logs.sh -t 20 -l INFO

# Follow startup in real-time
./logs.sh -f
```

### 2. **MQTT Connection Problems**
```bash
# Filter for MQTT-related messages
./logs.sh | grep -i mqtt

# Show only errors that might be MQTT related
./logs.sh -l ERROR | grep -i mqtt
```

### 3. **ModBus Communication Issues**
```bash
# Look for ModBus errors
./logs.sh -l ERROR | grep -i modbus

# Monitor ModBus communication in real-time
./logs.sh -f | grep -i "reading\|modbus\|block"
```

### 4. **Performance Monitoring**
```bash
# Monitor block reading efficiency
./logs.sh -f | grep -i "organized.*blocks"

# Check sensor reading timing
./logs.sh | grep -i "reading.*registers"
```

## Traditional Docker Commands Still Work

```bash
# Standard Docker Compose logs (with timestamps now!)
docker compose logs -f --timestamps

# Container-specific logs
docker logs em340d -f --timestamps

# Last 100 lines
docker compose logs --tail=100 --timestamps
```

## Log File Locations

- **Inside container**: `/app/logs/` (if file logging is enabled)
- **Host volume**: `em340d_logs` Docker volume
- **Access container logs**: `docker compose logs`

## Quick Status Check

```bash
# Check if everything is running and healthy
./troubleshoot.sh

# Quick log check for recent issues
./logs.sh -t 20 -l WARNING
```

The enhanced logging system makes it much easier to:
- 🕒 **Track when issues occurred** with precise timestamps
- 🎯 **Filter relevant information** by log level or time
- 🔍 **Identify patterns** in ModBus communication or MQTT connectivity
- 🚀 **Monitor performance** of the optimized block reading system
- 🐛 **Debug issues** with color-coded, formatted output
