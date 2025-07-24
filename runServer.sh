#!/bin/bash

# Source the configuration file for environment variables
CONFIG_FILE="config"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Error: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

# Path to the Python DHCP server script
DHCP_SERVER_SCRIPT="src/dhcp_server.py"
LOG_FILE="/var/log/dhcp-server.log" # Log file for the server output
PID_FILE="/var/run/dhcp-server.pid" # PID file for the server process

start_server() {
    echo "Starting DHCP server..."
    # Check if the server is already running using PID file
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
        echo "DHCP server is already running (PID: $(cat "$PID_FILE"))."
        exit 1
    fi

    # Start the server in the background, redirecting output to a log file
    # Requires sudo to bind to port 67
    sudo python3 "$DHCP_SERVER_SCRIPT" > "$LOG_FILE" 2>&1 &
    sleep 1 # Give the process a moment to start
    
    # Find the actual PID of the python script
    SERVER_PID=$(pgrep -f "python3 $DHCP_SERVER_SCRIPT")
    if [ -z "$SERVER_PID" ]; then
        echo "Error: Could not find PID of DHCP server after starting. Check logs for errors."
        exit 1
    fi
    echo "$SERVER_PID" > "$PID_FILE" # Store actual python PID in file
    echo "DHCP server started with PID: $SERVER_PID. Logs are in $LOG_FILE"
    echo "Remember to configure your network interface to use this DHCP server."
}

stop_server() {
    echo "Stopping DHCP server..."
    # Find the PID from the PID file
    if [ -f "$PID_FILE" ]; then
        SERVER_PID=$(cat "$PID_FILE")
        if ps -p "$SERVER_PID" > /dev/null; then
            # Kill the process
            sudo kill "$SERVER_PID"
            rm "$PID_FILE" # Remove PID file
            echo "DHCP server (PID: $SERVER_PID) stopped."
        else
            echo "DHCP server process (PID: $SERVER_PID) not found, removing stale PID file."
            rm "$PID_FILE"
        fi
    else
        echo "DHCP server is not running (PID file not found). Looking for process..."
        # Fallback: try to find and kill the process if PID file is missing but process is running
        SERVER_PID=$(pgrep -f "python3 $DHCP_SERVER_SCRIPT")
        if [ -z "$SERVER_PID" ]; then
            echo "DHCP server is not running."
        else
            sudo kill "$SERVER_PID"
            echo "DHCP server (PID: $SERVER_PID) stopped (found via pgrep)."
        fi
    fi
}

case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        start_server
        ;;
    status)
        if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
            echo "DHCP server is running (PID: $(cat "$PID_FILE"))."
        else
            echo "DHCP server is not running."
        fi
        ;;
    logs)
        echo "Displaying logs from $LOG_FILE (tail -f):"
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit 0
