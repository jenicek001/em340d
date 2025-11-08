#!/bin/bash

# Docker User ID Setup Script for EM340D
# Automatically configures user IDs for proper serial port access

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_info "EM340D Docker User Configuration Setup"
print_info "====================================="

# Get current user info
CURRENT_USER=$(whoami)
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

print_info "Current user: $CURRENT_USER (UID: $CURRENT_UID, GID: $CURRENT_GID)"

# Check if user is in dialout group
if groups "$CURRENT_USER" | grep -q "\bdialout\b"; then
    print_success "User '$CURRENT_USER' is in dialout group"
    USER_IN_DIALOUT=true
else
    print_warning "User '$CURRENT_USER' is NOT in dialout group"
    USER_IN_DIALOUT=false
fi

# Get dialout group ID
DIALOUT_GID=$(getent group dialout | cut -d: -f3)
if [ -z "$DIALOUT_GID" ]; then
    print_error "Could not find dialout group ID"
    DIALOUT_GID=20  # Default fallback
    print_warning "Using default dialout GID: $DIALOUT_GID"
else
    print_success "Dialout group ID: $DIALOUT_GID"
fi

# Check if .env file exists
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env.template" ]; then
        print_info "Creating .env from template..."
        cp .env.template "$ENV_FILE"
        print_success "Created $ENV_FILE from template"
    else
        print_error ".env.template not found"
        exit 1
    fi
fi

# Update .env file with current user IDs
print_info "Updating $ENV_FILE with current user IDs..."

# Function to update or add environment variable
update_env_var() {
    local var_name="$1"
    local var_value="$2"
    local env_file="$3"
    
    if grep -q "^${var_name}=" "$env_file"; then
        # Variable exists, update it
        sed -i "s/^${var_name}=.*/${var_name}=${var_value}/" "$env_file"
        print_info "Updated ${var_name}=${var_value}"
    else
        # Variable doesn't exist, add it
        echo "${var_name}=${var_value}" >> "$env_file"
        print_info "Added ${var_name}=${var_value}"
    fi
}

# Update user IDs in .env file
update_env_var "USER_ID" "$CURRENT_UID" "$ENV_FILE"
update_env_var "GROUP_ID" "$CURRENT_GID" "$ENV_FILE"
update_env_var "DIALOUT_GID" "$DIALOUT_GID" "$ENV_FILE"

print_success "Environment file updated with user IDs"

# Add user to dialout group if needed
if [ "$USER_IN_DIALOUT" = false ]; then
    print_warning "Adding user '$CURRENT_USER' to dialout group..."
    print_info "This requires sudo privileges and you may need to log out/in after"
    
    if sudo usermod -aG dialout "$CURRENT_USER"; then
        print_success "User added to dialout group"
        print_warning "You may need to log out and back in for group changes to take effect"
        print_info "Or run: newgrp dialout"
    else
        print_error "Failed to add user to dialout group"
        print_info "You can manually run: sudo usermod -aG dialout $CURRENT_USER"
    fi
fi

# Check for serial devices
print_info "Checking for USB serial devices..."
if ls /dev/ttyUSB* >/dev/null 2>&1; then
    print_success "Found USB serial devices:"
    ls -la /dev/ttyUSB*
else
    print_warning "No /dev/ttyUSB* devices found"
    print_info "Connect your USB-RS485 adapter and run this script again"
fi

# Provide next steps
print_info ""
print_info "Next Steps:"
print_info "==========="
print_info "1. Review the updated .env file: cat .env"
print_info "2. Connect your USB-RS485 adapter if not already connected"
print_info "3. Build and run the Docker container: ./quick-rebuild.sh"
print_info "4. Monitor logs: ./logs.sh -f"

if [ "$USER_IN_DIALOUT" = false ]; then
    print_info ""
    print_warning "Important: Since you were just added to dialout group:"
    print_info "- Log out and back in, OR"
    print_info "- Run: newgrp dialout"
    print_info "- Then rebuild the container: ./quick-rebuild.sh"
fi

print_info ""
print_success "Docker user configuration completed!"
print_info "Container will now run with UID:GID ${CURRENT_UID}:${CURRENT_GID}"
