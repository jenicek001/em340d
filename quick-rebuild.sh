#!/bin/bash

# Quick rebuild and test script for permission fixes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== EM340D Quick Rebuild ===${NC}"

# Detect Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo -e "${BLUE}Stopping containers...${NC}"
$COMPOSE_CMD down

echo -e "${BLUE}Cleaning up old volumes (this will reset logs)...${NC}"
docker volume rm em340d_em340d_logs 2>/dev/null || true

echo -e "${BLUE}Rebuilding image with permission fixes...${NC}"
$COMPOSE_CMD build --no-cache

echo -e "${BLUE}Starting container...${NC}"
$COMPOSE_CMD up -d

echo -e "${BLUE}Waiting for startup...${NC}"
sleep 5

echo -e "${BLUE}Container status:${NC}"
$COMPOSE_CMD ps

echo -e "${BLUE}Recent logs:${NC}"
echo "=================================="
$COMPOSE_CMD logs --tail=20 --timestamps
echo "=================================="

echo -e "${GREEN}Test complete! Monitor with: ./logs.sh -f${NC}"
