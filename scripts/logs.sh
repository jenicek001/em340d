#!/bin/bash

# Enhanced log monitoring script for EM340D Docker container
# Provides better timestamp visibility and filtering options

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}ERROR: No Docker Compose found${NC}"
    exit 1
fi

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -f, --follow     Follow log output (like tail -f)"
    echo "  -t, --tail N     Show last N lines (default: 100)"
    echo "  -s, --since TIME Show logs since timestamp (e.g., '2h', '30m', '2023-12-25T10:00:00')"
    echo "  -l, --level LEVEL Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    echo "  -r, --raw        Show raw Docker logs without formatting"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -f                    # Follow logs in real-time"
    echo "  $0 -t 50                 # Show last 50 lines"
    echo "  $0 -s '1h'              # Show logs from last hour"
    echo "  $0 -l ERROR             # Show only ERROR level logs"
    echo "  $0 -f -l INFO           # Follow logs, show INFO and above"
}

# Default values
FOLLOW=false
TAIL_LINES=100
SINCE=""
LEVEL_FILTER=""
RAW=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -t|--tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        -s|--since)
            SINCE="$2"
            shift 2
            ;;
        -l|--level)
            LEVEL_FILTER="$2"
            shift 2
            ;;
        -r|--raw)
            RAW=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Build Docker Compose logs command
LOGS_CMD="$COMPOSE_CMD logs"

if [ "$RAW" = true ]; then
    # Raw mode - just show Docker logs as-is with timestamps
    if [ "$FOLLOW" = true ]; then
        LOGS_CMD="$LOGS_CMD -f"
    fi
    LOGS_CMD="$LOGS_CMD --tail=$TAIL_LINES"
    if [ -n "$SINCE" ]; then
        LOGS_CMD="$LOGS_CMD --since $SINCE"
    fi
    echo -e "${CYAN}Showing raw Docker logs...${NC}"
    exec $LOGS_CMD
fi

# Enhanced mode with formatting and filtering
build_logs_cmd() {
    local cmd="$COMPOSE_CMD logs --timestamps"
    
    if [ "$FOLLOW" = true ]; then
        cmd="$cmd -f"
    fi
    
    cmd="$cmd --tail=$TAIL_LINES"
    
    if [ -n "$SINCE" ]; then
        cmd="$cmd --since $SINCE"
    fi
    
    echo "$cmd"
}

format_log_line() {
    local line="$1"
    
    # Extract timestamp, container name, and message
    if [[ $line =~ ^([^\ ]+)\ +([^\ ]+)\ +\|\ (.+)$ ]]; then
        local timestamp="${BASH_REMATCH[1]}"
        local container="${BASH_REMATCH[2]}"
        local message="${BASH_REMATCH[3]}"
        
        # Convert ISO timestamp to readable format
        if command -v date >/dev/null 2>&1; then
            # Try to parse and format timestamp
            readable_time=$(date -d "$timestamp" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$timestamp")
        else
            readable_time="$timestamp"
        fi
        
        # Apply level-based coloring
        if [[ $message =~ \[DEBUG\] ]]; then
            if [ -z "$LEVEL_FILTER" ] || [ "$LEVEL_FILTER" = "DEBUG" ]; then
                echo -e "${PURPLE}$readable_time${NC} ${CYAN}[$container]${NC} $message"
            fi
        elif [[ $message =~ \[INFO\] ]]; then
            if [ -z "$LEVEL_FILTER" ] || [[ "$LEVEL_FILTER" =~ ^(DEBUG|INFO)$ ]]; then
                echo -e "${GREEN}$readable_time${NC} ${CYAN}[$container]${NC} $message"
            fi
        elif [[ $message =~ \[WARNING\] ]]; then
            if [ -z "$LEVEL_FILTER" ] || [[ "$LEVEL_FILTER" =~ ^(DEBUG|INFO|WARNING)$ ]]; then
                echo -e "${YELLOW}$readable_time${NC} ${CYAN}[$container]${NC} $message"
            fi
        elif [[ $message =~ \[ERROR\] ]]; then
            if [ -z "$LEVEL_FILTER" ] || [[ "$LEVEL_FILTER" =~ ^(DEBUG|INFO|WARNING|ERROR)$ ]]; then
                echo -e "${RED}$readable_time${NC} ${CYAN}[$container]${NC} $message"
            fi
        elif [[ $message =~ \[CRITICAL\] ]]; then
            echo -e "${RED}$readable_time${NC} ${CYAN}[$container]${NC} ${RED}$message${NC}"
        else
            # No specific log level detected, show if no filter or if it might be important
            if [ -z "$LEVEL_FILTER" ]; then
                echo -e "${BLUE}$readable_time${NC} ${CYAN}[$container]${NC} $message"
            fi
        fi
    else
        # Fallback for lines that don't match expected format
        if [ -z "$LEVEL_FILTER" ]; then
            echo "$line"
        fi
    fi
}

# Check if container is running
if ! $COMPOSE_CMD ps | grep -q em340d; then
    echo -e "${YELLOW}WARNING: em340d container is not running${NC}"
    echo "Start it with: $COMPOSE_CMD up -d"
    echo ""
fi

# Show header
echo -e "${CYAN}=== EM340D Docker Logs ===${NC}"
if [ -n "$LEVEL_FILTER" ]; then
    echo -e "${YELLOW}Filtering for log level: $LEVEL_FILTER${NC}"
fi
if [ -n "$SINCE" ]; then
    echo -e "${YELLOW}Showing logs since: $SINCE${NC}"
fi
echo -e "${CYAN}=========================${NC}"
echo ""

# Execute logs command and format output
LOGS_CMD=$(build_logs_cmd)

if [ "$FOLLOW" = true ]; then
    echo -e "${GREEN}Following logs... (Press Ctrl+C to stop)${NC}"
    $LOGS_CMD | while IFS= read -r line; do
        format_log_line "$line"
    done
else
    $LOGS_CMD | while IFS= read -r line; do
        format_log_line "$line"
    done
fi
