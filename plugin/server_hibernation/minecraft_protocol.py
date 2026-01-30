"""
Minecraft protocol implementation for the proxy server
"""

import json
import socket
import struct
from typing import Optional, Tuple, Dict, Any

class MinecraftProtocol:
    """Handles Minecraft protocol for the proxy server"""
    
    @staticmethod
    def read_varint(sock: socket.socket) -> Optional[int]:
        """Read a varint from socket"""
        result = 0
        num_read = 0
        
        while True:
            data = sock.recv(1)
            if not data:
                return None
            
            byte = data[0]
            result |= (byte & 0x7F) << (7 * num_read)
            num_read += 1
            
            if num_read > 5:
                return None  # Varint too long
            
            if (byte & 0x80) != 0x80:
                break
        
        return result
    
    @staticmethod
    def write_varint(value: int) -> bytes:
        """Write a varint to bytes"""
        result = b""
        while True:
            temp = value & 0x7F
            value >>= 7
            if value != 0:
                temp |= 0x80
            result += struct.pack('!B', temp)
            if value == 0:
                break
        return result
    
    @staticmethod
    def read_string(sock: socket.socket) -> Optional[str]:
        """Read a string from socket"""
        length = MinecraftProtocol.read_varint(sock)
        if length is None:
            return None
        
        data = b""
        remaining = length
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                return None
            data += chunk
            remaining -= len(chunk)
        
        return data.decode('utf-8')
    
    @staticmethod
    def write_string(value: str) -> bytes:
        """Write a string to bytes"""
        data = value.encode('utf-8')
        return MinecraftProtocol.write_varint(len(data)) + data
    
    @staticmethod
    def read_packet(sock: socket.socket) -> Optional[bytes]:
        """Read a packet from socket"""
        length = MinecraftProtocol.read_varint(sock)
        if length is None:
            return None
        
        data = b""
        remaining = length
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                return None
            data += chunk
            remaining -= len(chunk)
        
        return data
    
    @staticmethod
    def write_packet(packet_id: int, data: bytes) -> bytes:
        """Write a packet to bytes"""
        packet_data = MinecraftProtocol.write_varint(packet_id) + data
        return MinecraftProtocol.write_varint(len(packet_data)) + packet_data
    
    @staticmethod
    def parse_handshake(data: bytes) -> Optional[Dict[str, Any]]:
        """Parse handshake packet"""
        try:
            offset = 0
            
            # Read protocol version
            protocol = MinecraftProtocol.read_varint_from_bytes(data[offset:])
            if protocol is None:
                return None
            offset += protocol['bytes_read']
            
            # Read address length and address
            address_length = MinecraftProtocol.read_varint_from_bytes(data[offset:])
            if address_length is None:
                return None
            offset += address_length['bytes_read']
            
            address = data[offset:offset+address_length['value']].decode('utf-8')
            offset += address_length['value']
            
            # Read port
            port = struct.unpack('!H', data[offset:offset+2])[0]
            offset += 2
            
            # Read next state
            next_state = MinecraftProtocol.read_varint_from_bytes(data[offset:])
            if next_state is None:
                return None
            
            return {
                'protocol': protocol['value'],
                'address': address,
                'port': port,
                'next_state': next_state['value']
            }
        except Exception:
            return None
    
    @staticmethod
    def read_varint_from_bytes(data: bytes) -> Optional[Dict[str, int]]:
        """Read varint from bytes"""
        result = 0
        num_read = 0
        
        for byte in data:
            result |= (byte & 0x7F) << (7 * num_read)
            num_read += 1
            
            if num_read > 5:
                return None  # Varint too long
            
            if (byte & 0x80) != 0x80:
                break
        
        return {'value': result, 'bytes_read': num_read}
    
    @staticmethod
    def create_status_response(config: Dict[str, Any]) -> bytes:
        """Create status response packet"""
        response = {
            "version": {
                "name": config["proxy"]["version"],
                "protocol": config["proxy"]["protocol"]
            },
            "players": {
                "max": config["proxy"]["max_players"],
                "online": 0,
                "sample": []
            },
            "description": {
                "text": config["proxy"]["motd"]
            }
        }
        
        response_json = json.dumps(response).encode('utf-8')
        return MinecraftProtocol.write_packet(0x00, MinecraftProtocol.write_varint(len(response_json)) + response_json)
    
    @staticmethod
    def create_disconnect_message(message: str) -> bytes:
        """Create disconnect message packet"""
        message_json = json.dumps({"text": message}).encode('utf-8')
        return MinecraftProtocol.write_packet(0x00, MinecraftProtocol.write_varint(len(message_json)) + message_json)