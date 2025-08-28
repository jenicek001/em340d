# Configuration Parameter Update: `name` → `serial_number`

## Summary
Updated the configuration parameter from generic `name` to more descriptive `serial_number` to properly identify Carlo Gavazzi EM340 meters.

## Changes Made

### 1. **Code Changes**
- **File**: `em340.py`
- **Change**: Updated MQTT topic construction to use `serial_number` instead of `name`
- **Line**: `self.topic = self.em340_config['mqtt']['topic'] + '/' + self.em340_config['config']['serial_number']`

### 2. **Configuration File Updates**

#### **em340.yaml** (Direct installation)
```yaml
config:
  # OLD
  name: XXXXXXX
  
  # NEW  
  # Carlo Gavazzi EM340 serial number - used as MQTT subtopic identifier
  # Format: 6 digits + 1 letter (e.g., "235411W")
  # You can find this on the EM340 device label
  serial_number: "235411W"
```

#### **em340.yaml.template** (Docker template)
```yaml
config:
  # OLD
  name: ${DEVICE_NAME:EM340}
  
  # NEW
  # Carlo Gavazzi EM340 serial number - used as MQTT subtopic identifier
  # Can be set via DEVICE_SERIAL_NUMBER environment variable
  serial_number: ${DEVICE_SERIAL_NUMBER:EM340_UNKNOWN}
```

#### **.env.template** (Docker environment)
```bash
# OLD
DEVICE_NAME=EM340

# NEW
# EM340 Device Identification
# Carlo Gavazzi EM340 serial number - used as MQTT subtopic
# Format: 6 digits + 1 letter (e.g., "235411W")
# You can find this on the EM340 device label
DEVICE_SERIAL_NUMBER=235411W

# Legacy parameter (kept for backward compatibility)
DEVICE_NAME=EM340
```

### 3. **Docker Integration**
- **docker-compose.yml**: Added `DEVICE_SERIAL_NUMBER` environment variable
- **Backward Compatibility**: Maintained `DEVICE_NAME` for existing deployments

### 4. **Documentation Updates**
- **README.md**: Updated MQTT topic examples and configuration instructions
- **Comments**: Added detailed format explanation and examples

## Usage Examples

### **Serial Number Format**
Carlo Gavazzi EM340 serial numbers follow the format:
- **6 digits + 1 letter**
- **Example**: `235411W`, `567892X`, `123456A`
- **Location**: Physical label on the EM340 meter

### **Example Serial Numbers**
- `235411W` - 6 digits (235411) + letter (W)
- `567892X` - 6 digits (567892) + letter (X)  
- `123456A` - 6 digits (123456) + letter (A)

### **MQTT Topic Structure**
- **Before**: `em340/EM340_Main`
- **After**: `em340/235411W`

This provides unique identification for each physical meter based on its actual serial number.

## Migration Guide

### **For Docker Users**
1. Update `.env` file:
   ```bash
   # Add this line with your actual EM340 serial number
   DEVICE_SERIAL_NUMBER=235411W
   
   # Keep existing DEVICE_NAME for compatibility (optional)
   DEVICE_NAME=EM340
   ```

2. Rebuild container:
   ```bash
   ./quick-rebuild.sh
   ```

### **For Direct Python Users**
1. Update `em340.yaml`:
   ```yaml
   config:
     # Replace this
     name: XXXXXXX
     
     # With this (use your actual EM340 serial number)
     serial_number: "235411W"
   ```

2. Restart the application

### **Finding Your EM340 Serial Number**
- **Physical Label**: Check the device label on your EM340 meter
- **Format**: 6 digits + 1 letter (e.g., `235411W`)
- **Location**: Usually on the front or side panel of the meter

## Benefits

1. **Unique Identification**: Each meter has a unique serial number
2. **Traceability**: Easy to identify which physical meter is sending data
3. **Multi-Meter Support**: No naming conflicts when using multiple meters
4. **Professional**: Follows industrial naming conventions
5. **MQTT Organization**: Clear topic structure for monitoring systems

## Backward Compatibility

- **Docker**: `DEVICE_NAME` environment variable still supported
- **Legacy Systems**: Existing installations will continue to work
- **Migration**: Can be done gradually, no breaking changes

This change improves the professionalism and clarity of the EM340D system while maintaining compatibility with existing installations.
