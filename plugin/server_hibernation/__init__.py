"""
Server Hibernation Plugin for MCDReforged
This plugin hibernates the Minecraft server when no players are online
and starts a proxy server to handle player connections.
"""

import mcdreforged as mcdr

from .main import ServerHibernationPlugin
from .commands import register_commands

# Global plugin instance
plugin_instance = None

def on_load(server: mcdr.PluginServerInterface, _prev_module):
    """Plugin load event"""
    global plugin_instance
    plugin_instance = ServerHibernationPlugin(server)
    plugin_instance.load()
    
    # Register commands
    register_commands(server, plugin_instance)

def on_unload(_server: mcdr.PluginServerInterface):
    """Plugin unload event"""
    global plugin_instance
    if plugin_instance:
        plugin_instance.unload()
        plugin_instance = None

def on_player_joined(_server: mcdr.PluginServerInterface, player: str, info):
    """Player joined event"""
    global plugin_instance
    if plugin_instance:
        plugin_instance.on_player_joined(player, info)

def on_player_left(_server: mcdr.PluginServerInterface, player: str):
    """Player left event"""
    global plugin_instance
    if plugin_instance:
        plugin_instance.on_player_left(player)

def on_server_startup(server: mcdr.PluginServerInterface):
    """Server startup event"""
    global plugin_instance
    if plugin_instance:
        server.logger.info("Server started, ensuring hibernation state is correct")
        if plugin_instance.is_hibernating:
            plugin_instance.wake_up_server()