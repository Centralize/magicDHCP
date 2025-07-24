# DHCP Server

## Project Overview

This project provides a simple, yet extensible, DHCP (Dynamic Host Configuration Protocol) server implemented in Python 3. It is designed to be highly configurable and runnable in various Linux environments, including containerized deployments using Docker and orchestrated environments with Kubernetes.

## Features

* **Dynamic IP Assignment:** Configurable range for IP address allocation.
* **Lease Management:** Basic lease tracking for assigned IP addresses.
* **Gateway & DNS Configuration:** Ability to specify default gateway and DNS servers.
* **Subnet Mask:** Customizable subnet mask.
* **Logger:** Basic logging for DHCP requests and responses.
* **Containerized Deployment:** Dockerfile for easy containerization.
* **Orchestrated Deployment:** Docker Compose for local multi-service setups and Helm chart for Kubernetes.

## Prerequisites

* **Python 3.x:** For running the DHCP server application.
* **pip:** Python package installer.
* **Docker:** For containerized deployment.
* **Docker Compose:** For local multi-container environments.
* **Kubernetes Cluster:** For Helm chart deployment.
* **Helm:** Kubernetes package manager.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone [https://github.com/your-username/dhcp-server.git](https://github.com/your-username/dhcp-server.git)
cd dhcp-server
````

### 2. Python Environment (Optional, for local development/testing without Docker)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt # Assuming a requirements.txt will be created for dependencies
```

### 3. Configuration

The DHCP server configuration will primarily be handled via environment variables or a configuration file (e.g., `config.ini`). For simplicity in this example, we'll assume environment variables are set or values are hardcoded within `dhcp_server.py`.

**Example Environment Variables:**

  * `DHCP_SERVER_IP`: The IP address of the interface the DHCP server should listen on (e.g., `0.0.0.0` or a specific interface IP).
  * `DHCP_LEASE_START_IP`: The starting IP address for the lease pool (e.g., `192.168.1.100`).
  * `DHCP_LEASE_END_IP`: The ending IP address for the lease pool (e.g., `192.168.1.200`).
  * `DHCP_SUBNET_MASK`: The subnet mask (e.g., `255.255.255.0`).
  * `DHCP_ROUTER_IP`: The default gateway IP address (e.g., `192.168.1.1`).
  * `DHCP_DNS_SERVERS`: Comma-separated list of DNS server IPs (e.g., `8.8.8.8,8.8.4.4`).
  * `DHCP_LEASE_TIME`: Lease time in seconds (e.g., `3600` for 1 hour).

## Running the DHCP Server

### 1. Locally (without Docker)

Ensure all prerequisites are met and environment variables are set.

```bash
# Set environment variables (example)
export DHCP_SERVER_IP="0.0.0.0"
export DHCP_LEASE_START_IP="192.168.1.100"
export DHCP_LEASE_END_IP="192.168.1.200"
export DHCP_SUBNET_MASK="255.255.255.0"
export DHCP_ROUTER_IP="192.168.1.1"
export DHCP_DNS_SERVERS="8.8.8.8,8.8.4.4"
export DHCP_LEASE_TIME="3600"

python3 src/dhcp_server.py
```

*Note: Running a DHCP server requires root privileges to bind to port 67 (BOOTP server).*

### 2. Using Docker

#### Build the Docker Image

```bash
docker build -t dhcp-server .
```

#### Run the Docker Container

When running with Docker, you'll need to pass the configuration as environment variables.

```bash
docker run -d \
  --name dhcp-server \
  --network host \ # Required to bind to host network interface for DHCP
  -e DHCP_SERVER_IP="0.0.0.0" \
  -e DHCP_LEASE_START_IP="192.168.1.100" \
  -e DHCP_LEASE_END_IP="192.168.1.200" \
  -e DHCP_SUBNET_MASK="255.255.255.0" \
  -e DHCP_ROUTER_IP="192.168.1.1" \
  -e DHCP_DNS_SERVERS="8.8.8.8,8.8.4.4" \
  -e DHCP_LEASE_TIME="3600" \
  -e PXE_SERVER_IP="192.168.1.1" \
  -e BOOT_FILE_BIOS="pxelinux.0" \
  -e BOOT_FILE_EFI="bootx64.efi" \
  dhcp-server
```

*Note: The `--network host` flag is crucial for the DHCP server to properly interact with the network at layer 2 for broadcasts. This means the container will share the host's network namespace.*

### 3. Using Docker Compose

Docker Compose can be used to set up and run the DHCP server and potentially other related services (e.g., a logging service or a monitoring tool) for local development or testing.

```bash
docker-compose up -d
```

### 4. Deploying with Helm (Kubernetes)

Hem charts simplify the deployment and management of applications on Kubernetes.

```bash
helm install dhcp-server helm/dhcp-server/ -f helm/dhcp-server/values.yaml
```

Refer to the `helm/dhcp-server/values.yaml` file for configurable parameters.

## Development

### Project Structure

```
dhcp-server/
├── helm/                    # Helm chart for Kubernetes deployment
├── src/                     # Source code for the Python DHCP server
│   └── dhcp_server.py
├── .gitignore               # Git ignore file
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose configuration
├── GEMINI.md                # Information for Gemini AI assistant
├── LICENSE.md               # Project license
└── README.md                # This documentation
```

### Extending the DHCP Server

The `src/dhcp_server.py` file can be extended to support more advanced DHCP options, persistent lease storage (e.g., SQLite, Redis), or integration with external systems.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) License. See the `LICENSE.md` file for details.

````