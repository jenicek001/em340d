# GitHub Copilot Instructions for EM340D Project

## Project Overview
EM340D is a ModBus to MQTT gateway application for Carlo Gavazzi EM340 smart meters. It reads data via RS485/ModBus RTU protocol and publishes to MQTT brokers. The application is designed for reliable embedded deployment (especially Raspberry Pi) with Docker support.

## Repository Structure

The repository is organized into the following directories:

### Core Application (`/` root)
- **em340.py** - Main application with automatic USB device reconnection
- **config_loader.py** - Configuration loader with environment variable substitution
- **logger.py** - Centralized logging configuration
- **em340config.py** - EM340 meter configuration utility
- **em340monitor.py** - ModBus traffic monitoring tool
- **em340_config_manager.py** - MQTT-based remote configuration service

### Configuration (`/config`)
- **em340.yaml** - Runtime configuration (used by Docker deployment)
- Template files in root: `.env.template`, `em340.yaml.template`

### Scripts (`/scripts`)
All bash scripts for deployment, setup, testing, and maintenance:
- **Deployment**: `quick-rebuild.sh`, `docker-deploy.sh`, `deploy-usb-reconnection-fix.sh`
- **Setup**: `install-autostart.sh`, `setup-docker-user.sh`, `setup-serial-access.sh`
- **Testing**: `test-mqtt-connectivity.sh`, `test-serial-docker.sh`, `test-usb-reconnection.sh`
- **Monitoring**: `logs.sh`, `troubleshoot.sh`, `em340d-service.sh`
- **Configuration**: `demo_mqtt_config.sh`, `setup-config.sh`

### Documentation (`/docs`)
All markdown documentation files:
- **USB_RECONNECTION.md** - USB device reconnection guide (NEW)
- **MQTT_CONFIGURATION.md** - Remote configuration via MQTT
- **LOGGING_GUIDE.md** - Comprehensive logging documentation
- **DOCKER_SERIAL_FIX.md** - Docker serial port access solutions
- **MODBUS_OPTIMIZATION.md** - Performance tuning guide
- **RASPBERRY_PI_FIXES.md** - Platform-specific solutions
- Plus deployment, implementation, and troubleshooting guides

### Tests (`/tests`)
Python test files and test utilities:
- `test_em340.py`, `test_em340config.py`, `test_mqtt_config.py`
- `test_blocks.py`, `test_logger.py`, etc.

### Tools (`/tools`)
Monitoring and health check utilities:
- **health_check.py** - Device health verification script
- **watchdog.sh** - External monitoring with auto-restart capability

## Important File Conventions

### When Creating or Modifying Scripts
- **Shell scripts** → Always place in `/scripts` directory
- **Python test files** → Always place in `/tests` directory
- **Monitoring/diagnostic tools** → Place in `/tools` directory
- **Documentation** → Always place in `/docs` directory

### When Referencing Files in Code
Always use the correct path structure:
- Scripts: `./scripts/script-name.sh`
- Documentation: `docs/DOCUMENT_NAME.md`
- Tools: `./tools/tool-name.py` or `docker exec em340d python tools/tool-name.py`
- Tests: `./tests/test_name.py`

### Configuration Files
- **Docker deployment**: Uses `config/em340.yaml` (generated from template + .env)
- **Direct Python**: Uses `em340.yaml` in root
- **Templates**: `em340.yaml.template`, `.env.template` in root
- **Runtime config**: `.env` file in root (not in repo, .gitignored)

## Key Features to Maintain

### 1. USB Device Reconnection (NEW - Nov 2025)
The application automatically handles USB-Serial device disconnections:
- Implemented in `em340.py` with `_reconnect_serial_device()` method
- Exponential backoff: 2s → 60s max retry delay
- Tests connection before resuming
- No container restart needed
- Docker uses privileged mode + full /dev mount for device resilience

**When modifying**: Ensure IOError and SerialException handling is preserved.

### 2. ModBus Block Optimization
- Reads 30+ sensors in 4 optimized blocks (87% reduction in ModBus calls)
- Implemented in `read_sensors()` method with intelligent grouping
- 50ms delay between blocks configurable via `t_delay_ms`

**When modifying**: Preserve block reading logic for performance.

### 3. MQTT Auto-Reconnection
- Background thread with 2-30s exponential backoff
- Handles broker downtime gracefully
- Never blocks application operation

**When modifying**: Preserve async MQTT loop and reconnect logic.

### 4. Remote Configuration via MQTT
- Allows runtime EM340 meter configuration via MQTT topics
- Managed by `em340_config_manager.py`
- Topics: `{topic}/{device_id}/config/{parameter}/set|get`

**When modifying**: Maintain backward compatibility with MQTT topic structure.

## Coding Guidelines

### Python Code Style
- Use descriptive variable names (e.g., `measurement_mode`, not `mm`)
- Log important operations with appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Handle exceptions gracefully with specific error messages
- Use type hints where appropriate
- Follow existing patterns for consistency

### Shell Script Style
- Use `set -euo pipefail` for robust error handling
- Provide clear usage/help messages
- Log operations with timestamps
- Make scripts idempotent where possible
- Use meaningful variable names in UPPERCASE for environment vars

### Documentation Style
- Keep README.md as the main entry point
- Use detailed docs in `/docs` for specific topics
- Include code examples in documentation
- Maintain table of contents for long documents
- Cross-reference related documentation

## Docker Considerations

### Container Architecture
- Based on `python:3.12-slim`
- Runs as non-root user (em340_container)
- User ID/Group ID matches host for permission alignment
- Uses privileged mode + /dev mount for USB device resilience
- Host networking for local MQTT broker access

### When Modifying docker-compose.yml
- Preserve privileged mode and /dev volume for USB reconnection
- Keep restart: unless-stopped for reliability
- Maintain environment variable structure
- Preserve health check configuration

### When Modifying Dockerfile
- Keep slim base image for embedded systems
- Maintain user/group creation logic for permissions
- Preserve udev installation for device management
- Keep Python dependencies minimal

## Testing Approach

### Before Committing Changes
1. Test in Docker: `./scripts/quick-rebuild.sh`
2. Check logs: `./scripts/logs.sh -t 20 -l ERROR`
3. Verify MQTT publishing: `mosquitto_sub -h localhost -t em340/+`
4. If serial/USB changes: Test reconnection with `./scripts/test-usb-reconnection.sh`
5. If config changes: Test with `./tests/test_mqtt_config.py`

### When Adding New Features
- Add corresponding test in `/tests`
- Update relevant documentation in `/docs`
- Add script helpers in `/scripts` if needed
- Update README.md feature list
- Document in appropriate troubleshooting section

## Common Patterns

### Environment Variable Loading
Use `config_loader.py` for YAML files with env var substitution:
```python
from config_loader import load_yaml_with_env
config = load_yaml_with_env('em340.yaml')
```

### Logging Pattern
Use the centralized logger:
```python
from logger import log
log.info('Operation completed')
log.error(f'Failed with error: {e}')
```

### Serial Device Access
Always handle IOError and SerialException:
```python
try:
    data = self.em340.read_registers(...)
except IOError as err:
    log.error(f'ModBus communication error: {err}')
    # Trigger reconnection logic
except serial.SerialException as err:
    log.error(f'Serial device error: {err}')
    # Trigger reconnection logic
```

### Error Handling Philosophy
- Log errors with context
- Fail gracefully when possible
- Retry with backoff for transient errors
- Exit cleanly on fatal configuration errors
- Never leave application in undefined state

## Deployment Workflow

### Standard Deployment
1. Update code/configuration
2. Run `./scripts/quick-rebuild.sh`
3. Check logs: `./scripts/logs.sh -f`
4. Verify health: `docker exec em340d python tools/health_check.py`

### Production Updates
1. Stop service: `./scripts/em340d-service.sh stop`
2. Pull changes: `git pull origin main`
3. Rebuild: `./scripts/quick-rebuild.sh`
4. Start service: `./scripts/em340d-service.sh start`
5. Verify: `./scripts/em340d-service.sh status`

## Troubleshooting Integration

When adding new features:
1. Add diagnostic checks to `./scripts/troubleshoot.sh`
2. Document common issues in README.md troubleshooting section
3. Create dedicated doc in `/docs` if complex
4. Add relevant test script in `/scripts` if testable

## Git Commit Messages

Follow this format:
```
Short description (50 chars or less)

Detailed explanation of changes:
- What was changed
- Why it was changed
- How it affects the system

Testing performed:
- List of tests executed
- Verification steps

Related: Issue #123, Related feature xyz
```

## Security Considerations

- Never commit `.env` or `em340.yaml` with real credentials
- Use templates (`.env.template`, `em340.yaml.template`) for examples
- Keep sensitive data in environment variables
- Use minimal Docker privileges where possible (but privileged mode is needed for USB)
- Validate all MQTT configuration inputs
- Sanitize all user-provided values before writing to ModBus

## Performance Considerations

- ModBus operations are blocking - keep them efficient
- Use block reading instead of individual register reads
- Respect `t_delay_ms` between ModBus operations
- MQTT publishes are async - don't block on them
- Log at appropriate levels (DEBUG for verbose, INFO for important events)

## Future Development Notes

### Potential Improvements
- Make ModBus timeout configurable per sensor
- Add metrics/statistics collection
- Support multiple EM340 meters in single container
- Add Prometheus exporter endpoint
- Implement circuit breaker pattern for extended outages
- Add udev rules integration for USB event triggers

### Maintaining Backwards Compatibility
- Keep existing MQTT topic structure
- Preserve environment variable names
- Maintain configuration file structure
- Support both `/dev/ttyUSB*` and `/dev/serial/by-id/` paths

## Quick Reference

### Key Commands
- Deploy: `./scripts/quick-rebuild.sh`
- Logs: `./scripts/logs.sh -f`
- Troubleshoot: `./scripts/troubleshoot.sh`
- Test USB: `./scripts/test-usb-reconnection.sh`
- Test MQTT: `./scripts/test-mqtt-connectivity.sh`
- Health check: `docker exec em340d python tools/health_check.py`

### Key Files
- Main app: `em340.py`
- Config loader: `config_loader.py`
- USB reconnection: `em340.py:_reconnect_serial_device()`
- MQTT config: `em340_config_manager.py`
- Health check: `tools/health_check.py`
- Watchdog: `tools/watchdog.sh`

### Key Documentation
- Main: `README.md`
- USB reconnection: `docs/USB_RECONNECTION.md`
- MQTT config: `docs/MQTT_CONFIGURATION.md`
- Logging: `docs/LOGGING_GUIDE.md`
- Docker serial: `docs/DOCKER_SERIAL_FIX.md`

## Repository Organization Philosophy

The goal is maintainability and clarity:
- **Root directory**: Only core application code and Docker files
- **Scripts**: All automation, deployment, and utility scripts
- **Docs**: All documentation and guides
- **Tests**: All test files
- **Tools**: Monitoring and diagnostic utilities
- **Config**: Runtime configuration (Docker)

This structure keeps the repository clean, makes it easy to find files, and separates concerns logically.

When in doubt, ask yourself: "Would a new developer easily find this file based on its purpose?" If not, it's probably in the wrong place.
