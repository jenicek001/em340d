# EM340D MQTT Configuration Feature

## Overview

The EM340D gateway now supports remote configuration of EM340 SmartMeter parameters via MQTT topics. This allows you to change meter settings, create backups, and manage configurations remotely without physical access to the device.

## Supported Configuration Parameters

Based on the EM340 ModBus register specification, the following parameters can be configured:

### System Configuration
| Parameter | ModBus Address | Type | Description | Values |
|-----------|----------------|------|-------------|---------|
| `measuring_system` | 0x1002 | UINT16 | Electrical connection type | 0=3P+N, 1=3P, 2=2P+N |
| `measurement_mode` | 0x1103 | UINT16 | Measurement mode | 0=Easy (A), 1=Bidirectional (B) |
| `display_mode` | 0x1101 | UINT16 | Display configuration | Device specific |
| `wrong_connection_help` | 0x1104 | UINT16 | Installation help | 0=Disabled, 1=Enabled |

### Transformer Configuration
| Parameter | ModBus Address | Type | Description | Range |
|-----------|----------------|------|-------------|--------|
| `pt_primary` | 0x1200 | UINT16 | PT primary voltage | 1-65535V |
| `pt_secondary` | 0x1201 | UINT16 | PT secondary voltage | 1-65535V |
| `ct_primary` | 0x1202 | UINT16 | CT primary current | 1-65535A |
| `ct_secondary` | 0x1203 | UINT16 | CT secondary current | 1A or 5A |

## MQTT Topic Structure

Configuration topics follow this structure:
```
{MQTT_TOPIC}/{DEVICE_SERIAL_NUMBER}/config/{action}
```

Example for device `235411W`:
```
em340/235411W/config/measurement_mode/set
em340/235411W/config/measurement_mode/get
em340/235411W/config/batch/set
```

## Configuration Operations

### 1. Get Available Parameters
**Topic:** `em340/{device_id}/config/available/get`  
**Payload:** Empty  
**Response:** `em340/{device_id}/config/available`

### 2. Get Single Parameter
**Topic:** `em340/{device_id}/config/{parameter}/get`  
**Payload:** Empty  
**Response:** `em340/{device_id}/config/{parameter}/value`

Example:
```bash
mosquitto_pub -h localhost -t "em340/235411W/config/measurement_mode/get" -m ""
```

### 3. Set Single Parameter
**Topic:** `em340/{device_id}/config/{parameter}/set`  
**Payload:** Parameter value  
**Response:** `em340/{device_id}/config/{parameter}/status`

Example:
```bash
# Set measurement mode to bidirectional (B)
mosquitto_pub -h localhost -t "em340/235411W/config/measurement_mode/set" -m "1"

# Set measuring system to 3-phase without neutral
mosquitto_pub -h localhost -t "em340/235411W/config/measuring_system/set" -m "1"
```

### 4. Batch Configuration
**Topic:** `em340/{device_id}/config/batch/set`  
**Payload:** JSON object with multiple parameters  
**Response:** `em340/{device_id}/config/batch/result`

Example:
```bash
mosquitto_pub -h localhost -t "em340/235411W/config/batch/set" -m '{
  "measurement_mode": 0,
  "measuring_system": 0,
  "pt_primary": 400,
  "ct_primary": 5
}'
```

### 5. Configuration Backup
**Topic:** `em340/{device_id}/config/backup`  
**Payload:** Empty  
**Response:** `em340/{device_id}/config/backup/data`

### 6. Configuration Restore
**Topic:** `em340/{device_id}/config/restore`  
**Payload:** JSON backup data  
**Response:** `em340/{device_id}/config/status`

### 7. Factory Reset
**Topic:** `em340/{device_id}/config/reset`  
**Payload:** Empty  
**Response:** `em340/{device_id}/config/status`

## Response Topics

### Parameter Status
**Topic:** `em340/{device_id}/config/{parameter}/status`
```json
{
  "parameter": "measurement_mode",
  "value": 1,
  "status": "success",
  "timestamp": 1692345678.123
}
```

### Parameter Value
**Topic:** `em340/{device_id}/config/{parameter}/value`
```json
{
  "parameter": "measurement_mode",
  "value": 1,
  "display_value": "1 (Bidirectional mode (B))",
  "timestamp": 1692345678.123
}
```

### Error Messages
**Topic:** `em340/{device_id}/config/error`
```json
{
  "error": "Parameter measurement_mode value 5 above maximum 1",
  "timestamp": 1692345678.123
}
```

## Parameter Value Reference

### Measuring System (0x1002)
- `0` or `"3-phase 4-wire with neutral"` - Standard 3-phase + neutral connection
- `1` or `"3-phase 3-wire without neutral"` - 3-phase delta connection  
- `2` or `"2-phase 3-wire"` - Split-phase connection

### Measurement Mode (0x1103)
- `0` or `"Easy connection mode (A)"` - Simplified mode with always positive values
- `1` or `"Bidirectional mode (B)"` - Full bidirectional energy measurement

### CT Secondary (0x1203)
- `1` - 1 Amp secondary
- `5` - 5 Amp secondary

## Safety and Validation

### Automatic Validation
- **Range checking**: Values are validated against min/max limits
- **Type validation**: Only valid integer values accepted
- **Write verification**: Configuration changes are read back to verify success
- **Error reporting**: Invalid operations return detailed error messages

### Best Practices
1. **Backup before changes**: Always create a backup before major configuration changes
2. **Test in non-production**: Verify configuration changes in a test environment first
3. **Monitor responses**: Always check status/error topics after configuration commands
4. **Use batch operations**: For multiple changes, use batch configuration to ensure consistency

## Usage Examples

### Complete Configuration Workflow

1. **Check available parameters:**
```bash
mosquitto_pub -h localhost -t "em340/235411W/config/available/get" -m ""
mosquitto_sub -h localhost -t "em340/235411W/config/available" -C 1
```

2. **Get current configuration:**
```bash
mosquitto_pub -h localhost -t "em340/235411W/config/measurement_mode/get" -m ""
mosquitto_pub -h localhost -t "em340/235411W/config/measuring_system/get" -m ""
```

3. **Create backup:**
```bash
mosquitto_pub -h localhost -t "em340/235411W/config/backup" -m ""
mosquitto_sub -h localhost -t "em340/235411W/config/backup/data" -C 1
```

4. **Apply new configuration:**
```bash
mosquitto_pub -h localhost -t "em340/235411W/config/batch/set" -m '{
  "measurement_mode": 1,
  "measuring_system": 0,
  "pt_primary": 400,
  "pt_secondary": 400,
  "ct_primary": 100,
  "ct_secondary": 5
}'
```

5. **Monitor for responses:**
```bash
mosquitto_sub -h localhost -t "em340/235411W/config/+/status" -t "em340/235411W/config/error"
```

## Integration with Home Assistant

### MQTT Discovery Configuration
```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "EM340 Measurement Mode"
      state_topic: "em340/235411W/config/measurement_mode/value"
      value_template: "{{ value_json.display_value }}"
      
  number:
    - name: "EM340 PT Primary"
      state_topic: "em340/235411W/config/pt_primary/value"
      command_topic: "em340/235411W/config/pt_primary/set"
      value_template: "{{ value_json.value }}"
      min: 1
      max: 65535
      
  select:
    - name: "EM340 Measuring System"
      state_topic: "em340/235411W/config/measuring_system/value"
      command_topic: "em340/235411W/config/measuring_system/set"
      value_template: "{{ value_json.value }}"
      options:
        - "0"
        - "1" 
        - "2"
```

## Troubleshooting

### Common Issues

1. **Configuration not applied:**
   - Check MQTT broker connectivity
   - Verify topic structure and device ID
   - Check ModBus communication to EM340 device

2. **Parameter value rejected:**
   - Verify value is within allowed range
   - Check parameter name spelling
   - Ensure parameter is writable

3. **No response to configuration commands:**
   - Check that configuration service started successfully
   - Verify MQTT broker supports retained messages
   - Check device logs for errors

### Debugging Commands
```bash
# Monitor all configuration activity
mosquitto_sub -h localhost -t "em340/+/config/+/+" -v

# Check configuration service status
./logs.sh -f | grep -i config

# Test MQTT connectivity
./test-mqtt-connectivity.sh
```

## Integration with Node-RED

Example Node-RED flow for EM340 configuration:

```json
[
  {
    "id": "config_inject",
    "type": "inject",
    "name": "Set Bidirectional Mode",
    "props": [
      {
        "p": "payload"
      },
      {
        "p": "topic",
        "vt": "str"
      }
    ],
    "repeat": "",
    "crontab": "",
    "once": false,
    "onceDelay": 0.1,
    "topic": "em340/235411W/config/measurement_mode/set",
    "payload": "1",
    "payloadType": "str"
  }
]
```

This comprehensive MQTT configuration feature provides a robust, safe, and user-friendly way to manage EM340 SmartMeter settings remotely.
