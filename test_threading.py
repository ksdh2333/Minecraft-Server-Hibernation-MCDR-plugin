#!/usr/bin/env python3
"""
Test script to verify threading fixes
"""

import threading
import time

def test_thread_join():
    """Test that thread joining works correctly"""
    print("Testing thread joining...")
    
    def worker():
        time.sleep(0.1)
        print("Worker thread completed")
    
    # Create and start worker thread
    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    
    # Try to join from main thread (should work)
    worker_thread.join()
    print("Main thread successfully joined worker thread")
    
    # Try to join from worker thread (should fail)
    def self_join_worker():
        try:
            # This should raise an exception
            threading.current_thread().join()
            print("ERROR: Self-join succeeded (should fail)")
        except RuntimeError as e:
            print(f"Self-join correctly failed: {e}")
    
    self_join_thread = threading.Thread(target=self_join_worker)
    self_join_thread.start()
    self_join_thread.join()
    
    print("Thread joining test completed")

def test_proxy_stop_simulation():
    """Test simulation of proxy server stop"""
    print("\nTesting proxy server stop simulation...")
    
    class MockProxyServer:
        def __init__(self):
            self.running = True
            self.client_threads = []
        
        def stop(self):
            print("Stopping proxy server...")
            self.running = False
            
            # Simulate stopping client threads
            for thread in self.client_threads:
                if thread.is_alive():
                    print(f"Waiting for thread {thread.name} to finish...")
                    thread.join(timeout=1.0)
            
            print("Proxy server stopped")
    
    class MockPlugin:
        def __init__(self):
            self.proxy_server = MockProxyServer()
            self.is_hibernating = True
        
        def wake_up_server_old(self, player=None):
            """Old implementation that might cause issues"""
            print("Old wake_up_server implementation...")
            
            # Stop proxy server (this might cause issues if called from client thread)
            if self.proxy_server:
                self.proxy_server.stop()
            
            self.is_hibernating = False
            print("Server is now awake")
        
        def wake_up_server_new(self, player=None):
            """New implementation with threading fix"""
            print("New wake_up_server implementation...")
            
            # Mark as not hibernating first
            self.is_hibernating = False
            
            # Stop proxy server in a separate thread
            def stop_proxy():
                if self.proxy_server:
                    self.proxy_server.stop()
            
            proxy_stop_thread = threading.Thread(target=stop_proxy, daemon=True)
            proxy_stop_thread.start()
            
            print("Server is now awake")
    
    # Test old implementation
    print("\nTesting old implementation...")
    plugin_old = MockPlugin()
    
    # Simulate client thread
    def client_thread_old():
        print("Client thread calling wake_up_server...")
        plugin_old.wake_up_server_old("TestPlayer")
    
    client_thread = threading.Thread(target=client_thread_old, name="ClientThread-Old")
    client_thread.start()
    client_thread.join()
    
    # Test new implementation
    print("\nTesting new implementation...")
    plugin_new = MockPlugin()
    
    # Simulate client thread
    def client_thread_new():
        print("Client thread calling wake_up_server...")
        plugin_new.wake_up_server_new("TestPlayer")
    
    client_thread = threading.Thread(target=client_thread_new, name="ClientThread-New")
    client_thread.start()
    client_thread.join()
    
    print("Proxy server stop simulation completed")

if __name__ == "__main__":
    print("Threading Fix Verification")
    print("=" * 40)
    
    test_thread_join()
    test_proxy_stop_simulation()
    
    print("\nAll tests completed!")