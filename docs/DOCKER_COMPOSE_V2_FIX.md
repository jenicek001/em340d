# Docker Compose V2 Compatibility Fix for Raspberry Pi OS

## Issue Identified

The original `docker-deploy.sh` script used the legacy `docker-compose` command (with hyphen), which is Docker Compose V1. Modern Docker installations, especially on Raspberry Pi OS, use Docker Compose V2 with the `docker compose` command (without hyphen).

## Root Cause Analysis

According to the official Docker documentation from Context7 MCP server:

- **Docker Compose V2**: Uses `docker compose` command (space-separated)
- **Docker Compose V1**: Uses `docker-compose` command (hyphen-separated) - **LEGACY**

Raspberry Pi OS with modern Docker installations includes Docker Compose V2 by default, causing the deployment script to fail when checking for the `docker-compose` command.

## Solution Implemented

### 1. Enhanced Docker Detection Logic

Updated the `check_docker()` function in `docker-deploy.sh` to:

```bash
# Check for Docker Compose V2 (docker compose) first, then legacy (docker-compose)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    print_success "Docker Compose V2 (docker compose) is available"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    print_success "Docker Compose V1 (docker-compose) is available"
    print_warning "Consider upgrading to Docker Compose V2 for better performance"
else
    print_error "Docker Compose is not installed."
    # Provide Raspberry Pi specific installation instructions
fi
```

### 2. Dynamic Command Usage

Replaced all hardcoded `docker-compose` commands with the dynamic `$COMPOSE_CMD` variable:

```bash
# Before (fixed)
docker-compose build
docker-compose up -d
docker-compose logs -f

# After (dynamic)
$COMPOSE_CMD build
$COMPOSE_CMD up -d  
$COMPOSE_CMD logs -f
```

### 3. Raspberry Pi Specific Installation Guidance

Added specific instructions for Raspberry Pi OS users:

```bash
print_info "For Raspberry Pi OS, run: curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
print_info "Then add your user to docker group: sudo usermod -aG docker $USER"
print_info "If Docker Compose V2 not available: sudo apt-get install docker-compose-plugin"
```

### 4. Backward Compatibility

The solution maintains full backward compatibility:
- ✅ Works with Docker Compose V2 (`docker compose`)
- ✅ Works with Docker Compose V1 (`docker-compose`)
- ✅ Provides appropriate warnings for legacy versions
- ✅ Clear error messages with installation instructions

### 5. Documentation Updates

Updated all documentation files to use the modern `docker compose` syntax:

#### Files Updated:
- **`docker-deploy.sh`** - Core deployment script with dynamic detection
- **`DOCKER_README.md`** - All examples updated to `docker compose`
- **`docker-compose.yml`** - Removed deploy resources (compatibility)

## Command Comparison

| Operation | Docker Compose V1 (Legacy) | Docker Compose V2 (Modern) |
|-----------|----------------------------|----------------------------|
| Start services | `docker-compose up -d` | `docker compose up -d` |
| View logs | `docker-compose logs -f` | `docker compose logs -f` |
| Stop services | `docker-compose down` | `docker compose down` |
| Build images | `docker-compose build` | `docker compose build` |
| Check status | `docker-compose ps` | `docker compose ps` |

## Benefits of Docker Compose V2

1. **Better Performance** - Faster command execution
2. **Improved UX** - Better error messages and output formatting  
3. **Active Development** - V1 is in maintenance mode only
4. **Integrated with Docker CLI** - Part of the Docker CLI itself
5. **Enhanced Features** - Support for profiles, better dependency handling

## Raspberry Pi OS Compatibility

### Installation Methods:

#### Option 1: Official Docker Installation (Recommended)
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in
```

#### Option 2: Docker Compose Plugin
```bash
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

#### Option 3: Legacy V1 (Not Recommended)
```bash
sudo pip3 install docker-compose
```

## Testing Results

The updated script now:

✅ **Detects** both V1 and V2 automatically  
✅ **Uses** the appropriate command syntax  
✅ **Provides** helpful installation guidance  
✅ **Maintains** backward compatibility  
✅ **Works** on Raspberry Pi OS out of the box  

## Migration Path

For existing users:

1. **No changes needed** if using modern Docker installation
2. **Script auto-detects** the available version
3. **Graceful fallback** to V1 if V2 unavailable
4. **Clear upgrade path** with warnings and instructions

## Error Prevention

The fix prevents these common errors:

```bash
# Before (V1 assumed)
$ ./docker-deploy.sh
[ERROR] Docker Compose is not installed.

# After (V2 detected)
$ ./docker-deploy.sh  
[SUCCESS] Docker Compose V2 (docker compose) is available
[SUCCESS] Container started successfully
```

## Conclusion

This fix ensures the EM340D Docker deployment works seamlessly on:

- ✅ **Raspberry Pi OS** with modern Docker
- ✅ **Ubuntu/Debian** with Docker Desktop
- ✅ **Any Linux distribution** with Docker Compose V2
- ✅ **Legacy systems** with Docker Compose V1

The solution is robust, backward-compatible, and provides clear guidance for users regardless of their Docker Compose version.
