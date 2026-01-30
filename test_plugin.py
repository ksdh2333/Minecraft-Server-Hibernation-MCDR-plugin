#!/usr/bin/env python3
"""
Simple test script to verify the plugin structure and imports
"""

import sys
import os

# Add the plugin directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server_hibernation'))

def test_imports():
    """Test that all modules can be imported"""
    try:
        from server_hibernation import config
        print("✓ config module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config module: {e}")
        return False
    
    try:
        from server_hibernation import minecraft_protocol
        print("✓ minecraft_protocol module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import minecraft_protocol module: {e}")
        return False
    
    try:
        from server_hibernation import process_manager
        print("✓ process_manager module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import process_manager module: {e}")
        return False
    
    try:
        from server_hibernation import proxy_server
        print("✓ proxy_server module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import proxy_server module: {e}")
        return False
    
    try:
        from server_hibernation import commands
        print("✓ commands module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import commands module: {e}")
        return False
    
    try:
        from server_hibernation import main
        print("✓ main module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import main module: {e}")
        return False
    
    return True

def test_config():
    """Test configuration loading"""
    try:
        from server_hibernation.config import DEFAULT_CONFIG
        print("✓ Default configuration loaded successfully")
        
        # Check that proxy port is different from server port
        server_port = DEFAULT_CONFIG["server"]["port"]
        proxy_port = DEFAULT_CONFIG["proxy"]["port"]
        
        if server_port != proxy_port:
            print(f"✓ Server port ({server_port}) and proxy port ({proxy_port}) are different")
        else:
            print(f"✗ Server port ({server_port}) and proxy port ({proxy_port}) are the same")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Failed to test configuration: {e}")
        return False

def test_plugin_metadata():
    """Test plugin metadata"""
    try:
        import json
        
        with open("mcdreforged.plugin.json", "r") as f:
            metadata = json.load(f)
        
        print("✓ Plugin metadata loaded successfully")
        
        # Check required fields
        required_fields = ["name", "version", "entrypoint"]
        for field in required_fields:
            if field in metadata:
                print(f"✓ Field '{field}' found in metadata")
            else:
                print(f"✗ Field '{field}' missing from metadata")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Failed to test plugin metadata: {e}")
        return False

if __name__ == "__main__":
    print("Testing Server Hibernation Plugin...")
    print("=" * 50)
    
    all_passed = True
    
    # Test plugin metadata
    if not test_plugin_metadata():
        all_passed = False
    
    print()
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    print()
    
    # Test configuration
    if not test_config():
        all_passed = False
    
    print()
    print("=" * 50)
    
    if all_passed:
        print("✓ All tests passed! Plugin structure is correct.")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)