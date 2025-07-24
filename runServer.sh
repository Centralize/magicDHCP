#!/bin/bash

# Define environment variables for the DHCP server
# These should match the values expected by dhcp_server.py
export DHCP_SERVER_IP="0.0.0.0"
export DHCP_LEASE_START_IP="192.168.1.100"
export DHCP_LEASE_END_IP="192.168.1.200"
export DHCP_SUBNET_MASK="255.255.255.0"
export DHCP_ROUTER_IP="192.168.1.1"
export DHCP_DNS_SERVERS="8.8.8.8,8.8.4.4"
export DHCP_LEASE_TIME="3600" # seconds

# Path to the Python DHCP server script
DHCP_SERVER_SCRIPT="/home/mkaas/Development/magicDNS_Python3/magicDHCP/dhcp-server/src/dhcp_server.py"
LOG_FILE="/var/log/dhcp-server.log" # Log file for the server output

start_server() {
    echo "Starting DHCP server..."
    # Check if the server is already running
    if pgrep -f "python3 $DHCP_SERVER_SCRIPT" > /dev/null; then
        echo "DHCP server is already running."
        exit 1
    fi

    # Start the server in the background, redirecting output to a log file
    # Requires sudo to bind to port 67
    sudo python3 "$DHCP_SERVER_SCRIPT" > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo "DHCP server started with PID: $SERVER_PID. Logs are in $LOG_FILE"
    echo "Remember to configure your network interface to use this DHCP server."
}

stop_server() {
    echo "Stopping DHCP server..."
    # Find the PID of the running server
    SERVER_PID=$(pgrep -f "python3 $DHCP_SERVER_SCRIPT")

    if [ -z "$SERVER_PID" ]; then
        echo "DHCP server is not running."
    else
        # Kill the process
        sudo kill "$SERVER_PID"
        echo "DHCP server (PID: $SERVER_PID) stopped."
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
        if pgrep -f "python3 $DHCP_SERVER_SCRIPT" > /dev/null; then
            echo "DHCP server is running."
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
