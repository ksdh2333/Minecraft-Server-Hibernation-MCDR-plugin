"""
Command handlers for Server Hibernation plugin
"""

from typing import Dict, Any

import mcdreforged as mcdr

def register_commands(server: mcdr.PluginServerInterface, plugin_instance):
    """Register plugin commands using SimpleCommandBuilder"""
    
    builder = mcdr.SimpleCommandBuilder()
    
    # Declare commands
    builder.command('!!sh hibernate', lambda src: hibernate_command(src, plugin_instance))
    builder.command('!!sh wake', lambda src: wake_command(src, plugin_instance))
    builder.command('!!sh status', lambda src: status_command(src, plugin_instance))
    builder.command('!!sh reload', lambda src: reload_command(src, plugin_instance))
    builder.command('!!sh config show', lambda src: show_config_command(src, plugin_instance))
    builder.command('!!sh config set <key> <value>', lambda src, ctx: set_config_command(src, ctx, plugin_instance))
    builder.command('!!sh test', lambda src: test_process_command(src, None, plugin_instance))
    builder.command('!!sh help', lambda src: help_command(src, plugin_instance))
    
    # Define argument types
    builder.arg('key', mcdr.Text)
    builder.arg('value', mcdr.GreedyText)
    
    # Register commands to server
    builder.register(server)

def hibernate_command(source, plugin_instance):
    """Handle hibernate command"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    if plugin_instance.is_hibernating:
        source.reply("§6Server is already hibernating")
        return
    
    if plugin_instance.player_count > 0:
        source.reply(f"§cCannot hibernate with {plugin_instance.player_count} players online")
        return
    
    source.reply("§eHibernating server...")
    plugin_instance.hibernate_server()

def wake_command(source, plugin_instance):
    """Handle wake command"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    if not plugin_instance.is_hibernating:
        source.reply("§6Server is not hibernating")
        return
    
    source.reply("§eWaking up server...")
    plugin_instance.wake_up_server()

def status_command(source, plugin_instance):
    """Handle status command"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    status = plugin_instance.get_status()
    
    source.reply("§6=== Server Hibernation Status ===")
    source.reply(f"§7Hibernating: §{'cYes' if status['is_hibernating'] else 'aNo'}")
    source.reply(f"§7Players Online: §e{status['player_count']}")
    source.reply(f"§7Proxy Running: §{'aYes' if status['proxy_running'] else 'cNo'}")
    source.reply(f"§7Server Running: §{'aYes' if status['server_running'] else 'cNo'}")
    source.reply(f"§7Server Suspended: §{'6Yes' if status['server_suspended'] else 'aNo'}")

def reload_command(source, plugin_instance):
    """Handle reload command"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    try:
        # Reload configuration using MCDReforged's built-in method
        default_config = {
            "server": {
                "host": "localhost",
                "port": 25565
            },
            "proxy": {
                "host": "0.0.0.0",
                "port": 25565,
                "motd": "§6Server is hibernating\n§eJoin to wake it up!",
                "version": "1.19.2",
                "protocol": 760,
                "max_players": 20
            },
            "hibernation": {
                "check_interval": 30,
                "hibernation_delay": 60,
                "stop_server": True,
                "wake_message": "§aServer is waking up, please wait..."
            }
        }
        
        plugin_instance.config = plugin_instance.server.load_config_simple(
            default_config=default_config,
            in_data_folder=True
        )
        source.reply("§aConfiguration reloaded successfully")
    except Exception as e:
        source.reply(f"§cFailed to reload configuration: {e}")

def show_config_command(source, plugin_instance):
    """Handle show config command"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    source.reply("§6=== Current Configuration ===")
    
    # Show key configuration values
    config = plugin_instance.config
    source.reply(f"§7Check Interval: §e{config['hibernation']['check_interval']}s")
    source.reply(f"§7Hibernation Delay: §e{config['hibernation']['hibernation_delay']}s")
    source.reply(f"§7Hibernation Mode: §{'aStop Server' if config['hibernation']['stop_server'] else 'bSuspend Process'}")
    source.reply(f"§7Proxy Port: §e{config['proxy']['port']}")
    source.reply(f"§7Server Port: §e{config['server']['port']}")

def set_config_command(source, ctx, plugin_instance):
    """Handle set config command"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    key = ctx['key']
    value = ctx['value']
    
    try:
        # Parse value based on key
        if key in ['hibernation.check_interval', 'hibernation.hibernation_delay']:
            value = int(value)
        elif key == 'hibernation.stop_server':
            value = value.lower() in ['true', 'yes', '1', 'on']
        elif key in ['proxy.port', 'server.port']:
            value = int(value)
        
        # Set configuration value
        keys = key.split('.')
        config_section = plugin_instance.config
        
        for k in keys[:-1]:
            if k not in config_section:
                config_section[k] = {}
            config_section = config_section[k]
        
        config_section[keys[-1]] = value
        
        # Save configuration using MCDReforged's built-in method
        plugin_instance.server.save_config_simple(plugin_instance.config)
        
        source.reply(f"§aConfiguration updated: {key} = {value}")
        
        # Restart components if needed
        if key in ['proxy.port', 'proxy.host'] and plugin_instance.is_hibernating:
            source.reply("§eRestarting proxy server with new configuration...")
            plugin_instance.proxy_server.stop()
            plugin_instance.proxy_server.start()
            
    except Exception as e:
        source.reply(f"§cFailed to set configuration: {e}")

def help_command(source, plugin_instance):
    """Handle help command"""
    source.reply("§6=== Server Hibernation Commands ===")
    source.reply("§e!!sh hibernate §7- Put the server into hibernation mode")
    source.reply("§e!!sh wake §7- Wake up the server from hibernation")
    source.reply("§e!!sh status §7- Show current hibernation status")
    source.reply("§e!!sh reload §7- Reload plugin configuration")
    source.reply("§e!!sh config show §7- Show current configuration")
    source.reply("§e!!sh config set <key> <value> §7- Set configuration value")
    source.reply("§e!!sh test §7- Test process suspension/resumption")
    source.reply("§e!!sh help §7- Show this help message")
    source.reply("§7Note: All commands require admin permission (level 3+)")

def test_process_command(source, ctx, plugin_instance):
    """Test process suspension and resumption"""
    if source.get_permission_level() < 3:  # Require admin permission
        source.reply("§cYou don't have permission to use this command")
        return
    
    # Check if process suspension is enabled
    if plugin_instance.config["hibernation"]["stop_server"]:
        source.reply("§cProcess suspension is disabled in config (stop_server=true)")
        return
    
    # Get current process status
    process = plugin_instance.process_manager.get_server_process()
    if not process:
        source.reply("§cCould not find server process")
        return
    
    if plugin_instance.process_manager.is_suspended:
        source.reply("§aProcess is already suspended, testing resumption...")
        
        # Test resumption
        success = plugin_instance.process_manager.resume_server()
        if success:
            source.reply("§aProcess resumed successfully")
        else:
            source.reply("§cProcess resumption failed")
    else:
        source.reply("§aTesting process suspension...")
        
        # Test suspension
        success = plugin_instance.process_manager.suspend_server()
        if success:
            source.reply("§aProcess suspended successfully")
            source.reply("§eType '!!sh test' again to test resumption")
        else:
            source.reply("§cProcess suspension failed")