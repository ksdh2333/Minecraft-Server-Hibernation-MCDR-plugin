"""
Proxy server implementation for handling player connections when server is hibernating
"""

import socket
import threading
import time
import json
from typing import Dict, Any, Optional

from .minecraft_protocol import MinecraftProtocol

class ProxyServer:
    """Proxy server that handles player connections when main server is hibernating"""
    
    def __init__(self, config: Dict[str, Any], server_interface, wake_up_callback=None):
        self.config = config
        self.server_interface = server_interface
        self.wake_up_callback = wake_up_callback
        self.socket = None
        self.running = False
        self.client_threads = []
        
    def start(self) -> bool:
        """Start the proxy server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((
                self.config["proxy"]["host"], 
                self.config["proxy"]["port"]
            ))
            self.socket.listen(5)
            self.running = True
            
            self.server_interface.logger.info(f"Proxy server started on {self.config['proxy']['host']}:{self.config['proxy']['port']}")
            
            # Start accepting connections in a new thread
            accept_thread = threading.Thread(target=self._accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            
            return True
        except Exception as e:
            self.server_interface.logger.error(f"Failed to start proxy server: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the proxy server"""
        self.running = False
        if self.socket:
            self.socket.close()
        
        # Wait for all client threads to finish
        for thread in self.client_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        
        self.server_interface.logger.info("Proxy server stopped")
    
    def _accept_connections(self) -> None:
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                self.server_interface.logger.info(f"New connection from {address}")
                
                # Handle client in a new thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                self.client_threads.append(client_thread)
                
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    self.server_interface.logger.error(f"Error accepting connection: {e}")
    
    def _handle_client(self, client_socket: socket.socket, address: tuple) -> None:
        """Handle a client connection"""
        try:
            # Read request data
            request_data = self._get_client_packet(client_socket)
            if not request_data:
                client_socket.close()
                return
            
            # Determine request type
            req_type = self._get_request_type(request_data)
            self.server_interface.logger.debug(f"Request from {address}: type={req_type}")
            
            # Handle based on request type
            if req_type == 1:  # INFO request
                self._handle_info_request(client_socket, request_data)
            elif req_type == 2:  # JOIN request
                self._handle_join_request(client_socket, request_data, address)
            else:
                self.server_interface.logger.warning(f"Unknown request type from {address}")
            
        except Exception as e:
            self.server_interface.logger.error(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
    
    def _get_client_packet(self, client_socket: socket.socket) -> Optional[bytes]:
        """Get client packet similar to Go implementation"""
        try:
            # Read first byte to determine packet length
            first_byte = client_socket.recv(1)
            if not first_byte:
                return None
            
            packet_length = first_byte[0]
            # Read remaining bytes
            remaining_data = client_socket.recv(packet_length)
            if len(remaining_data) != packet_length:
                return None
            
            return first_byte + remaining_data
        except Exception as e:
            self.server_interface.logger.error(f"Error reading client packet: {e}")
            return None
    
    def _get_request_type(self, data: bytes) -> int:
        """Determine request type similar to Go implementation"""
        if len(data) < 2:
            return 0
        
        # Get MSH port from config
        msh_port = self.config["proxy"]["port"]
        
        # Generate flags like in Go implementation
        req_flag_info = bytes([msh_port >> 8, msh_port & 0xFF, 1])
        req_flag_join = bytes([msh_port >> 8, msh_port & 0xFF, 2])
        
        # Extract request type key byte
        req_type_key_byte = 0
        if len(data) > data[0]:
            req_type_key_byte = data[data[0]]
        
        # Determine request type
        if req_type_key_byte == 1 or req_flag_info in data:
            return 1  # INFO request
        elif req_type_key_byte == 2 or req_flag_join in data:
            return 2  # JOIN request
        
        return 0  # Unknown
    
    def _handle_info_request(self, client_socket: socket.socket, request_data: bytes) -> None:
        """Handle INFO request similar to Go implementation"""
        try:
            # Build response message
            message = self.config["proxy"]["motd"]
            message = message.replace("&", "§")  # Convert & to §
            message = message.replace("\\n", "\n")  # Convert \n to actual newline
            
            # Create response data structure
            response_data = {
                "description": {"text": message},
                "players": {"max": 0, "online": 0},
                "version": {
                    "name": self.config["proxy"]["version"],
                    "protocol": self.config["proxy"]["protocol"]
                },
                "favicon": "data:image/png;base64,"  # Can add favicon later
            }
            
            # Convert to JSON
            import json
            response_json = json.dumps(response_data).encode('utf-8')
            
            # Build message using Go-style format
            response = self._build_message(1, response_json)
            
            # Send response
            client_socket.send(response)
            
            # Handle ping if present
            ping_data = self._get_client_packet(client_socket)
            if ping_data:
                # Echo ping response
                client_socket.send(ping_data)
            
        except Exception as e:
            self.server_interface.logger.error(f"Error handling info request: {e}")
    
    def _handle_join_request(self, client_socket: socket.socket, request_data: bytes, address: tuple) -> None:
        """Handle JOIN request similar to Go implementation"""
        try:
            # Extract username from request (simplified)
            username = "Unknown"  # Could parse from request_data if needed
            
            self.server_interface.logger.info(f"Player {username} from {address} is trying to join hibernating server")
            
            # Send wake up message
            message = self.config["hibernation"]["wake_message"]
            response = self._build_message(2, json.dumps({"text": message}).encode('utf-8'))
            
            client_socket.send(response)
            
            # Trigger server wake up
            self._trigger_wake_up(username, address)
            
        except Exception as e:
            self.server_interface.logger.error(f"Error handling join request: {e}")
    
    def _build_message(self, req_type: int, data: bytes) -> bytes:
        """Build message in Go-style format"""
        def mount_header(message: bytes) -> bytes:
            def add_sub_header(msg: bytes) -> bytes:
                first_byte = len(msg) % 128 + 128
                second_byte = len(msg) // 128
                return bytes([first_byte, second_byte]) + msg
            
            # Add sub-headers
            result = add_sub_header(message)
            result = bytes([0]) + result
            result = add_sub_header(result)
            
            return result
        
        return mount_header(data)
    
    def _trigger_wake_up(self, username: str, address: tuple) -> None:
        """Trigger server wake up"""
        self.server_interface.logger.info(f"Triggering server wake up for player {username}")
        
        # Call the wake up callback if available
        if self.wake_up_callback:
            self.wake_up_callback(username, address)
    
    @staticmethod
    def read_string_from_bytes(data: bytes, offset: int = 0) -> Optional[str]:
        """Read string from bytes"""
        try:
            length = MinecraftProtocol.read_varint_from_bytes(data[offset:])
            if not length:
                return None
            
            start = offset + length['bytes_read']
            end = start + length['value']
            
            if end > len(data):
                return None
            
            return data[start:end].decode('utf-8')
        except Exception:
            return None