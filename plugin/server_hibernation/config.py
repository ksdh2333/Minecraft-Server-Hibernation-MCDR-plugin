"""
Configuration management for Server Hibernation plugin
"""

import os
import json
from typing import Dict, Any

DEFAULT_CONFIG = {
    "server": {
        "host": "localhost",
        "port": 25565
    },
    "proxy": {
        "host": "0.0.0.0",
        "port": 25566,  # Different port from server
        "motd": "§6Server is hibernating\n§eJoin to wake it up!",
        "version": "1.19.2",
        "protocol": 760,
        "max_players": 20
    },
    "hibernation": {
        "check_interval": 30,  # seconds
        "hibernation_delay": 60,  # seconds after last player leaves
        "stop_server": True,  # True to stop server, False to suspend server process
        "wake_message": "§aServer is waking up, please wait..."
    }
}

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from file"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Merge with default config to ensure all keys exist
            return merge_config(DEFAULT_CONFIG, config)
        except Exception as e:
            print(f"Failed to load config: {e}, using default config")
            return DEFAULT_CONFIG.copy()
    else:
        # Create default config file
        save_config(config_path, DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config_path: str, config: Dict[str, Any]) -> None:
    """Save configuration to file"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

def merge_config(default: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
    """Merge custom config with default config"""
    result = default.copy()
    for key, value in custom.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result