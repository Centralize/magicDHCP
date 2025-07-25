import socket
import struct
import time
import os
import logging
import json
from ipaddress import IPv4Address, IPv4Network

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DHCPServer:
    LEASES_FILE = "/home/mkaas/Development/magicDNS_Python3/magicDHCP/dhcp-server/leases.json"

    def __init__(self):
        self.server_ip = os.getenv('DHCP_SERVER_IP', '0.0.0.0')
        self.lease_start_ip_str = os.getenv('DHCP_LEASE_START_IP', '192.168.1.100')
        self.lease_end_ip_str = os.getenv('DHCP_LEASE_END_IP', '192.168.1.200')
        self.subnet_mask_str = os.getenv('DHCP_SUBNET_MASK', '255.255.255.0')
        self.router_ip_str = os.getenv('DHCP_ROUTER_IP', '192.168.1.1')
        self.dns_servers_str = os.getenv('DHCP_DNS_SERVERS', '8.8.8.8')
        self.lease_time = int(os.getenv('DHCP_LEASE_TIME', '3600')) # seconds

        # NIS Configuration (RFC 2132, Options 64 and 65)
        self.nis_domain_name = os.getenv('DHCP_NIS_DOMAIN', '')
        self.nis_server_ips_str = os.getenv('DHCP_NIS_SERVERS', '')

        # PXE Boot Configuration
        self.pxe_server_ip_str = os.getenv('PXE_SERVER_IP', '')
        self.boot_file_bios = os.getenv('BOOT_FILE_BIOS', '')
        self.boot_file_efi = os.getenv('BOOT_FILE_EFI', '')

        self.pxe_server_ip = None
        if self.pxe_server_ip_str:
            self.pxe_server_ip = IPv4Address(self.pxe_server_ip_str)

        try:
            self.lease_start_ip = IPv4Address(self.lease_start_ip_str)
            self.lease_end_ip = IPv4Address(self.lease_end_ip_str)
            self.subnet_mask = IPv4Address(self.subnet_mask_str)
            self.router_ip = IPv4Address(self.router_ip_str)
            self.dns_servers = [IPv4Address(ip.strip()) for ip in self.dns_servers_str.split(',')]
            
            self.nis_server_ips = []
            if self.nis_server_ips_str:
                self.nis_server_ips = [IPv4Address(ip.strip()) for ip in self.nis_server_ips_str.split(',')]

            self.lease_pool = self._load_leases()
            self.available_ips = set()
            current_ip = self.lease_start_ip
            while current_ip <= self.lease_end_ip:
                ip_str = str(current_ip)
                # Check if the IP is currently leased and if the lease is still active
                is_leased_and_active = False
                for mac, lease_info in self.lease_pool.items():
                    if lease_info['ip_address'] == ip_str and lease_info['lease_time_end'] > time.time():
                        is_leased_and_active = True
                        break
                
                if not is_leased_and_active:
                    self.available_ips.add(ip_str)
                current_ip += 1

            logger.info(f"DHCP Server initialized.")
            logger.info(f"Listening on: {self.server_ip}")
            logger.info(f"Lease Pool: {self.lease_start_ip} - {self.lease_end_ip}")
            logger.info(f"Subnet Mask: {self.subnet_mask}")
            logger.info(f"Router: {self.router_ip}")
            logger.info(f"DNS Servers: {', '.join(map(str, self.dns_servers))}")
            logger.info(f"Lease Time: {self.lease_time} seconds")

        except Exception as e:
            logger.error(f"Error initializing DHCP server with provided environment variables: {e}")
            raise

    def _load_leases(self):
        if os.path.exists(self.LEASES_FILE):
            with open(self.LEASES_FILE, 'r') as f:
                try:
                    leases = json.load(f)
                    # Convert IP addresses back to IPv4Address objects if needed, or keep as strings
                    # For simplicity, we'll keep them as strings in the lease_pool for now
                    # Ensure 'is_static' flag is loaded correctly
                    for mac, lease_info in leases.items():
                        if 'is_static' not in lease_info:
                            lease_info['is_static'] = False
                    return leases
                except json.JSONDecodeError:
                    logger.warning(f"Leases file {self.LEASES_FILE} is empty or malformed. Starting with empty lease pool.")
                    return {}
        return {}

    def _save_leases(self):
        with open(self.LEASES_FILE, 'w') as f:
            # Convert IPv4Address objects to strings for JSON serialization
            serializable_lease_pool = {
                mac: {
                    'ip_address': str(lease_info['ip_address']),
                    'lease_time_end': lease_info['lease_time_end'],
                    'is_static': lease_info.get('is_static', False) # Add is_static flag
                }
                for mac, lease_info in self.lease_pool.items()
            }
            json.dump(serializable_lease_pool, f, indent=4)

    def start(self):
        # DHCP servers listen on port 67 (BOOTP server)
        # Clients send requests from port 68 (BOOTP client)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) # Allow broadcasting
        try:
            self.sock.bind((self.server_ip, 67))
            logger.info(f"DHCP server listening on {self.server_ip}:67")
        except PermissionError:
            logger.error("Permission denied. DHCP server requires root privileges to bind to port 67.")
            logger.error("Please run the script with sudo or as root (e.g., sudo python3 src/dhcp_server.py).")
            exit(1)
        except Exception as e:
            logger.error(f"Failed to bind socket: {e}")
            exit(1)

        while True:
            try:
                data, addr = self.sock.recvfrom(2048) # DHCP messages are typically small
                self.handle_dhcp_packet(data, addr)
            except Exception as e:
                logger.error(f"Error receiving/handling packet: {e}")

    def handle_dhcp_packet(self, data, addr):
        # Unpack DHCP header - Simplified, assumes standard BOOTP/DHCP structure
        # See RFC 2131 for full DHCP packet format
        # https://www.rfc-editor.org/rfc/rfc2131.html Section 2
        # op, htype, hlen, hops, xid, secs, flags, ciaddr, yiaddr, siaddr, giaddr, chaddr (6 bytes)
        try:
            # We'll parse only the crucial parts for this example
            op, htype, hlen, hops, xid, secs, flags = struct.unpack('!BBBBHHI', data[0:8])
            # ciaddr (client IP address), yiaddr (your IP address), siaddr (server IP address), giaddr (gateway IP address)
            ciaddr, yiaddr, siaddr, giaddr = struct.unpack('!IIII', data[8:24])
            chaddr = data[28:34] # Client hardware address (MAC)
            
            # DHCP magic cookie: 99.130.83.99 (RFC 2131, Section 2)
            magic_cookie = data[236:240] 

            if magic_cookie != b'\x63\x82\x53\x63':
                logger.warning(f"Received non-DHCP packet from {addr[0]}:{addr[1]}. Magic cookie mismatch.")
                return

            options_offset = 240
            options = self.parse_dhcp_options(data[options_offset:])

            message_type = options.get(53) # DHCP Message Type option

            if message_type == 1: # DHCPDISCOVER
                self.handle_discover(xid, chaddr, giaddr, addr[0], options)
            elif message_type == 3: # DHCPREQUEST
                self.handle_request(xid, chaddr, ciaddr, giaddr, addr[0], options)
            elif message_type == 7: # DHCPRELEASE
                self.handle_release(chaddr)
            # Add more handlers as needed (e.g., DHCPDECLINE, DHCPINFORM)
            else:
                logger.info(f"Received unknown DHCP message type {message_type} from {self.mac_to_str(chaddr)}")

        except struct.error as e:
            logger.warning(f"Malformed DHCP packet from {addr[0]}:{addr[1]}: {e}")
        except Exception as e:
            logger.error(f"Error handling DHCP packet from {addr[0]}:{addr[1]}: {e}")

    def parse_dhcp_options(self, options_data):
        options = {}
        idx = 0
        while idx < len(options_data):
            option_code = options_data[idx]
            if option_code == 255: # End option
                break
            elif option_code == 0: # Pad option
                idx += 1
                continue
            
            length = options_data[idx + 1]
            value = options_data[idx + 2 : idx + 2 + length]
            options[option_code] = self.parse_option_value(option_code, value)
            idx += 2 + length
        return options

    def parse_option_value(self, code, value):
        if code == 53: # DHCP Message Type
            return int.from_bytes(value, 'big')
        elif code == 50: # Requested IP Address
            return IPv4Address(value)
        elif code == 54: # Server Identifier
            return IPv4Address(value)
        elif code == 61: # Client Identifier (often MAC address)
            return value # Return as bytes
        elif code == 93: # Client System Architecture
            # See RFC 4578 for details on Option 93
            # https://www.rfc-editor.org/rfc/rfc4578.html
            # Value is a list of 16-bit unsigned integers
            architectures = []
            for i in range(0, len(value), 2):
                architectures.append(struct.unpack('!H', value[i:i+2])[0])
            return architectures
        return value # Return raw bytes for other options

    def mac_to_str(self, mac_bytes):
        return ':'.join(f'{b:02x}' for b in mac_bytes)

    def str_to_mac(self, mac_str):
        return bytes.fromhex(mac_str.replace(':', ''))

    def handle_discover(self, xid, chaddr, giaddr, client_ip, options):
        mac_str = self.mac_to_str(chaddr)
        logger.info(f"Received DHCPDISCOVER from {mac_str}")

        assigned_ip = None
        # Check if MAC already has a lease
        if mac_str in self.lease_pool:
            assigned_ip = self.lease_pool[mac_str]['ip_address']
            logger.info(f"Re-offering existing IP {assigned_ip} to {mac_str}")
        else:
            # Find an available IP
            for ip_str in sorted(list(self.available_ips)): # Sort for consistent assignment
                if ip_str not in [self.lease_pool[mac]['ip_address'] for mac in self.lease_pool]:
                    assigned_ip = IPv4Address(ip_str)
                    break
            
            if not assigned_ip:
                logger.warning(f"No available IP addresses in pool for {mac_str}.")
                return # Cannot offer an IP

            self.lease_pool[mac_str] = {
                'ip_address': assigned_ip,
                'lease_time_end': time.time() + self.lease_time
            }
            self.available_ips.discard(str(assigned_ip)) # Remove from available pool
            logger.info(f"Offering new IP {assigned_ip} to {mac_str}")
        
        # Build DHCPOFFER packet
        offer_options = {
            1: self.subnet_mask.packed, # Subnet Mask
            3: self.router_ip.packed, # Router (Gateway)
            6: b''.join([dns.packed for dns in self.dns_servers]), # DNS Servers
            51: struct.pack('!I', self.lease_time), # IP Address Lease Time
            54: IPv4Address(self.server_ip).packed # Server Identifier
        }

        if self.nis_domain_name:
            offer_options[64] = self.nis_domain_name.encode() # Option 64: NIS Domain Name
        if self.nis_server_ips:
            offer_options[65] = b''.join([ip.packed for ip in self.nis_server_ips]) # Option 65: NIS Server Addresses

        boot_file = b''
        if self.pxe_server_ip and (self.boot_file_bios or self.boot_file_efi):
            # Option 93: Client System Architecture
            client_arch = options.get(93)
            if client_arch and (4 in client_arch or 6 in client_arch or 7 in client_arch or 9 in client_arch): # EFI architectures
                if self.boot_file_efi:
                    boot_file = self.boot_file_efi.encode()
                    logger.info(f"Client {mac_str} is EFI, offering bootfile: {self.boot_file_efi}")
            elif self.boot_file_bios: # Assume BIOS if no EFI arch or no EFI bootfile
                boot_file = self.boot_file_bios.encode()
                logger.info(f"Client {mac_str} is BIOS or unknown, offering bootfile: {self.boot_file_bios}")
            
            if boot_file:
                offer_options[67] = boot_file # Option 67: Bootfile Name

        offer_packet = self.build_dhcp_packet(
            op=2, # BOOTREPLY
            xid=xid,
            ciaddr=0, # Client IP is 0.0.0.0 in discover
            yiaddr=int(assigned_ip), # Your IP address
            siaddr=int(self.pxe_server_ip) if self.pxe_server_ip else int(IPv4Address(self.server_ip)), # Next server IP address (TFTP server)
            giaddr=giaddr, # Gateway IP address (from client)
            chaddr=chaddr,
            message_type=2, # DHCPOFFER
            file=boot_file, # Boot file name in fixed field
            options=offer_options
        )
        self.sock.sendto(offer_packet, ('<broadcast>', 68)) # Send to broadcast, client listens on 68

    def handle_request(self, xid, chaddr, ciaddr, giaddr, client_ip_from_packet, options):
        mac_str = self.mac_to_str(chaddr)
        requested_ip = options.get(50) # Requested IP Address option
        server_identifier = options.get(54) # Server Identifier option

        logger.info(f"Received DHCPREQUEST from {mac_str}. Requested IP: {requested_ip}, Server ID: {server_identifier}")

        assigned_ip = None
        ack_nack_type = 6 # DHCPACK by default
        
        # Scenario 1: Client requesting a specific IP (from DHCPDISCOVER)
        if requested_ip:
            # Check if the requested IP is a static lease for this MAC
            if mac_str in self.lease_pool and self.lease_pool[mac_str].get('is_static', False) and self.lease_pool[mac_str]['ip_address'] == str(requested_ip):
                assigned_ip = requested_ip
                self.lease_pool[mac_str]['lease_time_end'] = time.time() + (365 * 24 * 3600) # 1 year for static
                self._save_leases()
                logger.info(f"Acknowledging static lease for {mac_str} with IP {assigned_ip}")
            elif str(requested_ip) in self.available_ips or (mac_str in self.lease_pool and self.lease_pool[mac_str]['ip_address'] == str(requested_ip)):
                # Ensure the request is for *this* server if Server Identifier is present
                if server_identifier and server_identifier != IPv4Address(self.server_ip):
                    logger.warning(f"Client {mac_str} requested IP {requested_ip} from another server {server_identifier}. Ignoring.")
                    return # Ignore request meant for another server
                
                assigned_ip = requested_ip
                if mac_str not in self.lease_pool: # New dynamic lease
                    self.lease_pool[mac_str] = {
                        'ip_address': str(assigned_ip),
                        'lease_time_end': time.time() + self.lease_time,
                        'is_static': False
                    }
                    self.available_ips.discard(str(assigned_ip))
                    self._save_leases() # Save leases after modification
                    logger.info(f"Acknowledging new dynamic lease for {mac_str} with IP {assigned_ip}")
                else: # Renewing existing dynamic lease
                    self.lease_pool[mac_str]['lease_time_end'] = time.time() + self.lease_time
                    self._save_leases() # Save leases after modification
                    logger.info(f"Renewing dynamic lease for {mac_str} with IP {assigned_ip}")
            else:
                logger.warning(f"Client {mac_str} requested unavailable or invalid IP {requested_ip}. Sending DHCPNAK.")
                ack_nack_type = 4 # DHCPNAK
                assigned_ip = IPv4Address('0.0.0.0') # For NAK, yiaddr is 0
        # Scenario 2: Client re-booting after successful lease (no requested_ip)
        elif mac_str in self.lease_pool:
            lease_info = self.lease_pool[mac_str]
            assigned_ip = IPv4Address(lease_info['ip_address'])
            if lease_info.get('is_static', False):
                lease_info['lease_time_end'] = time.time() + (365 * 24 * 3600) # 1 year for static
                logger.info(f"Client {mac_str} re-booting, acknowledging static lease for IP {assigned_ip}")
            else:
                lease_info['lease_time_end'] = time.time() + self.lease_time
                logger.info(f"Client {mac_str} re-booting, acknowledging existing dynamic lease for IP {assigned_ip}")
            self._save_leases() # Save leases after modification
        else:
            logger.warning(f"Client {mac_str} sent DHCPREQUEST without requested IP and no existing lease. Sending DHCPNAK.")
            ack_nack_type = 4 # DHCPNAK
            assigned_ip = IPv4Address('0.0.0.0')

        # Build DHCPACK or DHCPNAK packet
        ack_options = {
            1: self.subnet_mask.packed, # Subnet Mask
            3: self.router_ip.packed, # Router (Gateway)
            6: b''.join([dns.packed for dns in self.dns_servers]), # DNS Servers
            51: struct.pack('!I', self.lease_time), # IP Address Lease Time
            54: IPv4Address(self.server_ip).packed # Server Identifier
        }

        if self.nis_domain_name:
            ack_options[64] = self.nis_domain_name.encode() # Option 64: NIS Domain Name
        if self.nis_server_ips:
            ack_options[65] = b''.join([ip.packed for ip in self.nis_server_ips]) # Option 65: NIS Server Addresses

        boot_file = b''
        if self.pxe_server_ip and (self.boot_file_bios or self.boot_file_efi):
            client_arch = options.get(93)
            if client_arch and (4 in client_arch or 6 in client_arch or 7 in client_arch or 9 in client_arch): # EFI architectures
                if self.boot_file_efi:
                    boot_file = self.boot_file_efi.encode()
            elif self.boot_file_bios:
                boot_file = self.boot_file_bios.encode()
            
            if boot_file:
                ack_options[67] = boot_file # Option 67: Bootfile Name

        ack_packet = self.build_dhcp_packet(
            op=2, # BOOTREPLY
            xid=xid,
            ciaddr=int(ciaddr) if ciaddr != 0 else 0, # Client IP if known, else 0
            yiaddr=int(assigned_ip),
            siaddr=int(self.pxe_server_ip) if self.pxe_server_ip else int(IPv4Address(self.server_ip)),
            giaddr=giaddr,
            chaddr=chaddr,
            message_type=ack_nack_type,
            file=boot_file, # Boot file name in fixed field
            options=ack_options
        )
        self.sock.sendto(ack_packet, ('<broadcast>', 68)) # Send to broadcast

    def handle_release(self, chaddr):
        mac_str = self.mac_to_str(chaddr)
        logger.info(f"Received DHCPRELEASE from {mac_str}")
        if mac_str in self.lease_pool:
            released_ip = self.lease_pool[mac_str]['ip_address']
            self.available_ips.add(str(released_ip)) # Return IP to available pool
            del self.lease_pool[mac_str]
            self._save_leases() # Save leases after modification
            logger.info(f"Released IP {released_ip} for {mac_str}.")
        else:
            logger.warning(f"Received DHCPRELEASE from {mac_str} but no active lease found.")


    def build_dhcp_packet(self, op, xid, ciaddr, yiaddr, siaddr, giaddr, chaddr, message_type, options={}):
        # DHCP fixed-format fields (236 bytes)
        # op (1), htype (1), hlen (1), hops (1), xid (4), secs (2), flags (2)
        # ciaddr (4), yiaddr (4), siaddr (4), giaddr (4)
        # chaddr (16), sname (64), file (128)
        
        # Fixed BOOTP/DHCP header
        packet = struct.pack('!BBBBHHI', 
                            op,    # op: 1=BOOTREQUEST, 2=BOOTREPLY
                            1,     # htype: 1=Ethernet
                            6,     # hlen: hardware address length (Ethernet is 6 bytes)
                            0,     # hops: typically 0
                            xid,   # xid: transaction ID
                            0,     # secs: seconds elapsed
                            0x8000 # flags: 0x8000 for broadcast, 0x0000 for unicast (we usually broadcast replies to DISCOVER/REQUEST)
                           )
        
        packet += struct.pack('!IIII', 
                              ciaddr, # Client IP address (usually 0.0.0.0 in DISCOVER)
                              yiaddr, # Your (client) IP address
                              siaddr, # Next server IP address
                              giaddr  # Relay agent IP address
                             )
        
        packet += chaddr.ljust(16, b'\x00') # Client hardware address (16 bytes, padded)
        packet += b'\x00' * 64 # Server host name (sname) - 64 bytes, all zeros
        packet += file.ljust(128, b'\x00') # Boot file name (file) - 128 bytes, padded

        # DHCP Magic Cookie
        packet += b'\x63\x82\x53\x63' # 99.130.83.99

        # DHCP Options
        # Option 53: DHCP Message Type
        packet += struct.pack('!BB', 53, 1) + struct.pack('!B', message_type) # Type: 1=DISCOVER, 2=OFFER, 3=REQUEST, 4=DECLINE, 5=ACK, 6=NAK, 7=RELEASE

        # Add PXE options if configured
        if self.pxe_server_ip_str and (message_type == 2 or message_type == 5): # DHCPOFFER or DHCPACK
            # Option 66: TFTP Server Name
            packet += struct.pack('!BB', 66, len(self.pxe_server_ip_str)) + self.pxe_server_ip_str.encode()
            # Option 67: Bootfile Name (handled in handle_discover/request based on client arch)
            # This will be added dynamically in handle_discover/request

        for code, value in options.items():
            if code == 53 or code == 66 or code == 67: # Already handled or will be handled dynamically
                continue
            packet += struct.pack('!BB', code, len(value)) + value
        
        packet += b'\xff' # End Option

        return packet

if __name__ == "__main__":
    server = DHCPServer()
    server.start()

