# Docker Serial Port Access Fix

## Problem
The EM340D Docker container cannot access `/dev/ttyUSB0` because:
- Container runs as a different user than the host `em340` user
- Host `em340` user has dialout group access, but container doesn't inherit this
- Error: `PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'`

## Root Cause Analysis

### Host System Status ✅
```bash
$ id em340
uid=1001(em340) gid=1001(em340) groups=1001(em340),20(dialout)

$ ls -la /dev/ttyUSB0
crw-rw---- 1 root dialout 188, 0 Aug 28 13:36 /dev/ttyUSB0
```
- ✅ em340 user exists (UID: 1001)
- ✅ em340 user is in dialout group (GID: 20)
- ✅ /dev/ttyUSB0 has dialout group permissions

### Docker Container Issue ❌
- ❌ Container runs as default user (not em340)
- ❌ Container user doesn't have dialout group membership
- ❌ `/dev/ttyUSB0` device mapped but no access permissions

## Solution: User/Group ID Mapping

### Quick Fix
```bash
# Use the enhanced deployment script
./deploy-with-user-mapping.sh
```

### Manual Fix
Update `docker-compose.yml` to include:
```yaml
services:
  em340d:
    # ... other settings ...
    user: "1001:20"  # em340_uid:dialout_gid
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
```

### Verification Steps

1. **Check current user mapping**:
   ```bash
   ./troubleshoot.sh
   ```

2. **Test container access**:
   ```bash
   docker compose exec em340d ls -la /dev/ttyUSB0
   ```

3. **Monitor logs for permission errors**:
   ```bash
   ./logs.sh -f -l ERROR
   ```

## How the Fix Works

### Before Fix
```
Host: em340 (1001:1001) + dialout(20) → can access /dev/ttyUSB0
Container: root or default user → CANNOT access /dev/ttyUSB0
```

### After Fix  
```
Host: em340 (1001:1001) + dialout(20) → can access /dev/ttyUSB0
Container: user 1001 with group 20 → CAN access /dev/ttyUSB0
```

## Alternative Solutions

### Option 1: Privileged Mode (Less Secure)
```yaml
services:
  em340d:
    privileged: true
    # Remove devices section when using privileged
```

### Option 2: Volume Mount /dev
```yaml
services:
  em340d:
    volumes:
      - /dev:/dev
    user: "1001:20"
```

## Troubleshooting

### Issue: User mapping not working
**Check**: Verify IDs are correct
```bash
id em340
getent group dialout
```

### Issue: Container still fails
**Check**: Rebuild container after changes
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Issue: Device not found
**Check**: USB device connection
```bash
ls -la /dev/ttyUSB*
dmesg | tail -10
```

## Security Notes

- ✅ **Recommended**: User mapping (1001:20) - minimal privileges
- ⚠️ **Acceptable**: Privileged mode (for testing only)  
- ❌ **Not recommended**: chmod 666 on device

The user mapping approach maintains security while providing necessary access to the serial device.

## Deployment Commands

```bash
# Enhanced deployment with automatic user detection
./deploy-with-user-mapping.sh

# Manual deployment
docker compose down
docker compose build --no-cache  
docker compose up -d

# Monitor results
./logs.sh -f
```

This fix ensures the Docker container runs with the same permissions as the host `em340` user, allowing proper access to the USB-RS485 adapter.
