#!/bin/bash

# EM340D Update Script
# Safely updates the application with backup and verification

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --check         Check for available updates only"
    echo "  --force         Force update even if no changes detected"
    echo "  --no-backup     Skip configuration backup"
    echo "  --no-cache      Force Docker rebuild without cache"
    echo "  --dry-run       Show what would be updated without applying changes"
    echo "  -h, --help      Show this help message"
}

# Default options
CHECK_ONLY=false
FORCE_UPDATE=false
NO_BACKUP=false
NO_CACHE=false
DRY_RUN=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --check)
            CHECK_ONLY=true
            shift
            ;;
        --force)
            FORCE_UPDATE=true
            shift
            ;;
        --no-backup)
            NO_BACKUP=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

print_info "EM340D Update Tool"
print_info "=================="

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ] || [ ! -f "em340.py" ]; then
    print_error "This doesn't appear to be the EM340D directory"
    print_info "Please run this script from the EM340D project directory"
    exit 1
fi

# Get current version info
print_step "Checking current version..."
CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
print_info "Current version: $CURRENT_COMMIT on branch $CURRENT_BRANCH"

# Check for local changes
if git diff-index --quiet HEAD -- 2>/dev/null; then
    print_success "Working directory is clean"
else
    print_warning "You have uncommitted local changes"
    if [ "$DRY_RUN" = false ] && [ "$FORCE_UPDATE" = false ]; then
        print_info "Local changes detected:"
        git status --porcelain
        echo ""
        read -p "Continue with update? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Update cancelled by user"
            exit 0
        fi
    fi
fi

# Fetch latest changes
print_step "Fetching latest changes from GitHub..."
if ! git fetch origin; then
    print_error "Failed to fetch changes from GitHub"
    print_info "Check your internet connection and GitHub access"
    exit 1
fi

# Check if updates are available
print_step "Checking for available updates..."
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/main)

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ] && [ "$FORCE_UPDATE" = false ]; then
    print_success "You are already up to date!"
    if [ "$CHECK_ONLY" = true ]; then
        exit 0
    fi
    read -p "Force rebuild anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "No update needed"
        exit 0
    fi
    FORCE_UPDATE=true
else
    print_info "Updates available:"
    git log --oneline $LOCAL_COMMIT..$REMOTE_COMMIT | head -10
    
    if [ "$(git log --oneline $LOCAL_COMMIT..$REMOTE_COMMIT | wc -l)" -gt 10 ]; then
        print_info "... and $(( $(git log --oneline $LOCAL_COMMIT..$REMOTE_COMMIT | wc -l) - 10 )) more commits"
    fi
    
    # Check for breaking changes
    if git log --grep="BREAKING" --oneline $LOCAL_COMMIT..$REMOTE_COMMIT | grep -q "BREAKING"; then
        print_warning "⚠️  BREAKING CHANGES detected in this update!"
        print_info "Please review the changes carefully before proceeding"
        git log --grep="BREAKING" --oneline $LOCAL_COMMIT..$REMOTE_COMMIT
        echo ""
    fi
fi

if [ "$CHECK_ONLY" = true ]; then
    print_info "Use './update.sh' to apply the updates"
    exit 0
fi

if [ "$DRY_RUN" = true ]; then
    print_info "DRY RUN - Would perform the following actions:"
    print_info "1. Stop EM340D service"
    print_info "2. Backup configuration files"
    print_info "3. Update to commit: $(git rev-parse --short origin/main)"
    print_info "4. Rebuild Docker container"
    print_info "5. Restart service"
    print_info "6. Run post-update tests"
    exit 0
fi

# Confirm update
if [ "$FORCE_UPDATE" = false ]; then
    echo ""
    read -p "Proceed with update? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Update cancelled by user"
        exit 0
    fi
fi

# Backup configuration files
if [ "$NO_BACKUP" = false ]; then
    print_step "Backing up configuration files..."
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    for file in .env em340.yaml config/em340.yaml; do
        if [ -f "$file" ]; then
            cp "$file" "$BACKUP_DIR/" 2>/dev/null
            print_info "Backed up: $file"
        fi
    done
    print_success "Configuration backed up to: $BACKUP_DIR"
fi

# Stop the service
print_step "Stopping EM340D service..."
if [ -x "./em340d-service.sh" ]; then
    ./em340d-service.sh stop
else
    docker compose down
fi

# Update the code
print_step "Updating to latest version..."
if git merge origin/main; then
    NEW_COMMIT=$(git rev-parse --short HEAD)
    print_success "Updated from $CURRENT_COMMIT to $NEW_COMMIT"
else
    print_error "Failed to merge updates"
    print_info "You may have merge conflicts that need manual resolution"
    exit 1
fi

# Check for new configuration templates
print_step "Checking for configuration updates..."
if [ -f ".env" ] && [ -f ".env.template" ]; then
    if ! diff -q .env .env.template >/dev/null 2>&1; then
        print_warning "Configuration template has changed"
        print_info "Please review .env.template for new options"
        print_info "Your current .env has been preserved"
    fi
fi

if [ -f "em340.yaml" ] && [ -f "em340.yaml.template" ]; then
    if ! diff -q em340.yaml em340.yaml.template >/dev/null 2>&1; then
        print_warning "YAML configuration template has changed"
        print_info "Please review em340.yaml.template for new options"
        print_info "Your current em340.yaml has been preserved"
    fi
fi

# Rebuild Docker container
print_step "Rebuilding Docker container..."
if [ "$NO_CACHE" = true ]; then
    if ! ./quick-rebuild.sh --no-cache; then
        print_error "Failed to rebuild Docker container"
        exit 1
    fi
else
    if ! ./quick-rebuild.sh; then
        print_error "Failed to rebuild Docker container"
        exit 1
    fi
fi

# Wait a moment for services to start
sleep 3

# Verify the update
print_step "Verifying update..."
if [ -x "./em340d-service.sh" ]; then
    ./em340d-service.sh status
else
    docker compose ps
fi

# Run tests
print_step "Running post-update tests..."
TEST_RESULTS=""

# Test serial device access
if [ -x "./test-serial-docker.sh" ]; then
    print_info "Testing serial device access..."
    if ./test-serial-docker.sh >/dev/null 2>&1; then
        print_success "✅ Serial device access: OK"
        TEST_RESULTS="$TEST_RESULTS✅ Serial: OK\n"
    else
        print_warning "⚠️  Serial device access: Issues detected"
        TEST_RESULTS="$TEST_RESULTS⚠️  Serial: Issues\n"
    fi
fi

# Test MQTT connectivity
if [ -x "./test-mqtt-connectivity.sh" ]; then
    print_info "Testing MQTT connectivity..."
    if timeout 30 ./test-mqtt-connectivity.sh >/dev/null 2>&1; then
        print_success "✅ MQTT connectivity: OK"
        TEST_RESULTS="$TEST_RESULTS✅ MQTT: OK\n"
    else
        print_warning "⚠️  MQTT connectivity: Issues detected"
        TEST_RESULTS="$TEST_RESULTS⚠️  MQTT: Issues\n"
    fi
fi

# Check application logs for errors
print_info "Checking for recent errors..."
if [ -x "./logs.sh" ]; then
    ERROR_COUNT=$(./logs.sh -t 10 -l ERROR 2>/dev/null | wc -l)
    if [ "$ERROR_COUNT" -eq 0 ]; then
        print_success "✅ No recent errors detected"
        TEST_RESULTS="$TEST_RESULTS✅ No errors\n"
    else
        print_warning "⚠️  $ERROR_COUNT recent errors detected"
        TEST_RESULTS="$TEST_RESULTS⚠️  $ERROR_COUNT errors\n"
        print_info "Check logs with: ./logs.sh -l ERROR"
    fi
fi

# Summary
print_info ""
print_success "==================="
print_success "UPDATE COMPLETED!"
print_success "==================="
print_info "Updated from: $CURRENT_COMMIT"
print_info "Updated to:   $NEW_COMMIT"
print_info ""
print_info "Test Results:"
echo -e "$TEST_RESULTS"

if [ "$NO_BACKUP" = false ] && [ -d "$BACKUP_DIR" ]; then
    print_info "Configuration backup: $BACKUP_DIR"
fi

print_info ""
print_info "Next Steps:"
print_info "- Monitor logs: ./logs.sh -f"
print_info "- Check status: ./em340d-service.sh status"
print_info "- Run tests: ./test-mqtt-connectivity.sh"

if [ "$TEST_RESULTS" = *"Issues"* ] || [ "$TEST_RESULTS" = *"errors"* ]; then
    print_warning ""
    print_warning "Some issues were detected during testing"
    print_info "Please review the logs and configuration"
    print_info "Restore backup if needed: cp $BACKUP_DIR/.env ./"
fi
