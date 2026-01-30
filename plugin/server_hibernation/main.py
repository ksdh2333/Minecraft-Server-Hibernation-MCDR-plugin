"""
Main plugin logic for Server Hibernation
"""

import threading
import time
import os
from typing import Dict, Any, Optional

import mcdreforged as mcdr

from .config import load_config, save_config, DEFAULT_CONFIG
from .proxy_server import ProxyServer
from .process_manager import ProcessManager

class ServerHibernationPlugin:
    """Main plugin class"""
    
    def __init__(self, server_interface: mcdr.PluginServerInterface):
        self.server = server_interface
        self.config = {}
        self.proxy_server = None
        self.process_manager = None
        self.is_hibernating = False
        self.player_count = 0
        self.hibernation_timer = None
        self.check_timer = None
        
    def load(self):
        """Load the plugin"""
        # Load configuration using MCDReforged's built-in method
        default_config = {
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
                "check_interval": 30,
                "hibernation_delay": 60,
                "stop_server": True,  # True to stop server, False to suspend server process
                "wake_message": "§aServer is waking up, please wait..."
            }
        }
        
        # Load existing config
        self.config = self.server.load_config_simple(
            default_config=default_config,
            in_data_folder=True
        )
        
        # Migrate old config options to new format
        config_updated = False
        if "enable_process_suspension" in self.config["hibernation"] or "stop_server_instead_of_hibernate" in self.config["hibernation"]:
            # Get old values
            enable_suspension = self.config["hibernation"].get("enable_process_suspension", False)
            stop_server = self.config["hibernation"].get("stop_server_instead_of_hibernate", True)
            
            # Remove old options
            self.config["hibernation"].pop("enable_process_suspension", None)
            self.config["hibernation"].pop("stop_server_instead_of_hibernate", None)
            
            # Set new option based on old values
            # If process suspension is enabled, don't stop server
            self.config["hibernation"]["stop_server"] = not enable_suspension and stop_server
            
            self.server.logger.info(f"Migrated config: stop_server = {self.config['hibernation']['stop_server']}")
            config_updated = True
        elif "stop_server" not in self.config["hibernation"]:
            # Add new option if not present
            self.config["hibernation"]["stop_server"] = True
            self.server.logger.info("Added new config option: stop_server")
            config_updated = True
        
        if config_updated:
            # Save the updated config
            self.server.save_config_simple(self.config, in_data_folder=True)
        
        # Initialize components
        self.process_manager = ProcessManager(self.server, self.config)
        self.proxy_server = ProxyServer(self.config, self.server, self.on_wake_up_request)
        
        # Register event listeners
        # Note: Custom events will be handled directly
        
        # Start periodic check
        self.start_periodic_check()
        
        self.server.logger.info("Server Hibernation plugin loaded")
    
    def unload(self):
        """Unload the plugin"""
        # Stop timers
        if self.hibernation_timer:
            self.hibernation_timer.cancel()
        if self.check_timer:
            self.check_timer.cancel()
        
        # Stop proxy server
        if self.proxy_server:
            self.proxy_server.stop()
        
        self.server.logger.info("Server Hibernation plugin unloaded")
    
    def on_player_joined(self, player: str, info):
        """Handle player join event"""
        self.player_count += 1
        self.server.logger.info(f"Player {player} joined. Current players: {self.player_count}")
        
        # Cancel hibernation timer if running
        if self.hibernation_timer:
            self.hibernation_timer.cancel()
            self.hibernation_timer = None
        
        # If server is hibernating, wake it up
        if self.is_hibernating:
            self.wake_up_server(player)
    
    def on_player_left(self, player: str):
        """Handle player leave event"""
        self.player_count = max(0, self.player_count - 1)
        self.server.logger.info(f"Player {player} left. Current players: {self.player_count}")
        
        # If no players left, start hibernation timer
        if self.player_count == 0 and not self.is_hibernating:
            self.start_hibernation_timer()
    
    def on_wake_up_request(self, username, address):
        """Handle wake up request from proxy server"""
        self.server.logger.info(f"Wake up request from {username} at {address}")
        
        if self.is_hibernating:
            self.wake_up_server(username)
    
    def wake_up_server(self, player: str = None):
        """Wake up the server"""
        self.server.logger.info("Waking up server...")
        
        # Mark as not hibernating first to prevent race conditions
        self.is_hibernating = False
        
        # Stop proxy server in a separate thread to avoid blocking
        def stop_proxy():
            if self.proxy_server:
                self.proxy_server.stop()
        
        proxy_stop_thread = threading.Thread(target=stop_proxy, daemon=True)
        proxy_stop_thread.start()
        
        # Check how to wake up the server based on hibernation mode
        if self.config["hibernation"]["stop_server"]:
            # Start the server through MCDReforged
            self.server.logger.info("Starting server through MCDReforged...")
            self.server.start()
            
            # Notify players that server is starting
            if player:
                self.server.logger.info(f"Server is starting up for {player}...")
                
                # Schedule notification after server is fully started
                def notify_player():
                    time.sleep(10)  # Wait for server to fully start
                    try:
                        self.server.execute_command(f"tellraw @a {{\"text\":\"§aServer is waking up for {player}!\"}}")
                    except:
                        pass  # Server might not be fully ready yet
                
                threading.Thread(target=notify_player, daemon=True).start()
        else:
            # Resume the suspended server process
            self.server.logger.info("Resuming suspended server process...")
            if self.process_manager.resume_server():
                self.server.logger.info("Server process resumed successfully")
                
                # Notify players that server is awake
                if player:
                    try:
                        self.server.execute_command(f"tellraw @a {{\"text\":\"§aServer is waking up for {player}!\"}}")
                    except:
                        pass  # Command might fail if server is not ready
            else:
                self.server.logger.error("Failed to resume server process")
        
        self.server.logger.info("Server is now awake")
    
    def start_hibernation_timer(self):
        """Start the hibernation timer"""
        # Check if server is running using MCDReforged API
        if not self.server.is_server_running():
            self.server.logger.debug("Server is not running, not starting hibernation timer")
            return
            
        # Check if server is started up
        if not self.server.is_server_startup():
            self.server.logger.debug("Server is not started up yet, not starting hibernation timer")
            return
        
        delay = self.config["hibernation"]["hibernation_delay"]
        self.server.logger.info(f"Starting hibernation timer: {delay} seconds")
        
        self.hibernation_timer = threading.Timer(
            delay,
            self.hibernate_server
        )
        self.hibernation_timer.start()
    
    def hibernate_server(self):
        """Hibernate the server"""
        # Check if server is running using MCDReforged API
        if not self.server.is_server_running():
            self.server.logger.debug("Server is not running, cancelling hibernation")
            self.is_hibernating = False
            return
            
        # Check if server is started up
        if not self.server.is_server_startup():
            self.server.logger.debug("Server is not started up yet, cancelling hibernation")
            self.is_hibernating = False
            return
        
        if self.player_count > 0:
            self.server.logger.info("Players still online, cancelling hibernation")
            return
        
        self.server.logger.info("Hibernating server...")
        self.is_hibernating = True
        
        # Check if we should stop the server or suspend the process
        if self.config["hibernation"]["stop_server"]:
            # Stop the server and start a proxy
            self.server.logger.info("Stopping server through MCDReforged...")
            
            # Start proxy server after a delay to ensure server is stopped
            def start_proxy_delayed():
                # Wait for server to fully stop
                time.sleep(5)
                
                # Start proxy server on a different port
                proxy_port = self.config["proxy"]["port"]
                if proxy_port == self.config["server"]["port"]:
                    # Use a different port for the proxy
                    proxy_port = self.config["server"]["port"] + 1
                    self.config["proxy"]["port"] = proxy_port
                    self.server.logger.info(f"Using port {proxy_port} for proxy server")
                
                if self.proxy_server.start():
                    self.server.logger.info("Proxy server started")
                    # Notify players that they need to connect to the new port
                    self.server.logger.info(f"Players should connect to port {proxy_port} while server is hibernating")
                else:
                    self.server.logger.error("Failed to start proxy server")
                    self.is_hibernating = False
            
            # Stop the server and start proxy in a separate thread with delay
            self.server.stop()
            threading.Thread(target=start_proxy_delayed, daemon=True).start()
        else:
            # Suspend the server process
            self.server.logger.info("Suspending server process...")
            if self.process_manager.suspend_server():
                self.server.logger.info("Server process suspended successfully")
                
                # Start proxy server on a different port (since suspended process still holds the original port)
                proxy_port = self.config["proxy"]["port"]
                if proxy_port == self.config["server"]["port"]:
                    # Use a different port for the proxy
                    proxy_port = self.config["server"]["port"] + 1
                    self.config["proxy"]["port"] = proxy_port
                    self.server.logger.info(f"Using port {proxy_port} for proxy server (different from server)")
                
                if self.proxy_server.start():
                    self.server.logger.info("Proxy server started")
                    self.server.logger.info(f"Players should connect to port {proxy_port} while server is hibernating")
                else:
                    self.server.logger.error("Failed to start proxy server")
                    # Try to resume the server
                    self.process_manager.resume_server()
                    self.is_hibernating = False
            else:
                self.server.logger.error("Failed to suspend server process")
                self.is_hibernating = False
    
    def start_periodic_check(self):
        """Start periodic player count check"""
        interval = self.config["hibernation"]["check_interval"]
        
        def check_players():
            # Schedule next check
            self.check_timer = threading.Timer(
                interval,
                check_players
            )
            self.check_timer.start()
            
            # Check if server is running using MCDReforged API
            if not self.server.is_server_running():
                self.server.logger.debug("Server is not running, skipping player check")
                return
                
            # Check if server is started up
            if not self.server.is_server_startup():
                self.server.logger.debug("Server is not started up yet, skipping player check")
                return
            
            # Get player count from server
            try:
                response = self.server.execute_command("list")
                if response and response.success:
                    # Parse player count from response
                    import re
                    match = re.search(r'There are (\d+) of a max', response.get_info())
                    if match:
                        count = int(match.group(1))
                        if count != self.player_count:
                            self.player_count = count
                            self.server.logger.debug(f"Player count updated: {count}")
                            
                            # Handle player count change
                            if count == 0 and not self.is_hibernating:
                                self.start_hibernation_timer()
                            elif count > 0 and self.is_hibernating:
                                self.wake_up_server()
            except Exception as e:
                self.server.logger.error(f"Error checking players: {e}")
        
        # Start first check
        check_timer = threading.Timer(
            interval,
            check_players
        )
        check_timer.start()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current plugin status"""
        return {
            "is_hibernating": self.is_hibernating,
            "player_count": self.player_count,
            "proxy_running": self.proxy_server is not None and self.proxy_server.running,
            "server_suspended": self.process_manager.is_server_suspended() if self.process_manager else False,
            "server_running": self.process_manager.is_server_running() if self.process_manager else False
        }