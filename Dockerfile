# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# If you have external dependencies, list them in requirements.txt
# COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY src/dhcp_server.py .

# Expose the DHCP server ports
# UDP port 67 (DHCP server) and 68 (DHCP client)
# Note: When using host network mode, EXPOSE is informational.
EXPOSE 67/udp
EXPOSE 68/udp

# Run the Python script when the container starts
# The DHCP server needs to listen on the host's network interface directly
# so it can receive broadcast DHCP DISCOVER messages.
# This typically requires --network host, which bypasses Docker's bridge network.
# Running with --network host also means the container shares the host's
# network namespace, making EXPOSE ports redundant for actual binding.
# The command runs with 'python', assuming the script will handle privileges.
# For production, consider using capabilities to drop root after binding.
CMD ["python", "dhcp_server.py"]
