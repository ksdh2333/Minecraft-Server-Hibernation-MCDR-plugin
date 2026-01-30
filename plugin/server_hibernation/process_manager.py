"""
Process management for the Minecraft server
"""

import os
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any

# Windows API constants for process suspension
THREAD_SUSPEND_RESUME = 0x0002
TH32CS_SNAPTHREAD = 0x00000004

# Define THREADENTRY32 structure
class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ThreadID', wintypes.DWORD),
        ('th32OwnerProcessID', wintypes.DWORD),
        ('tpBasePri', wintypes.LONG),
        ('tpDeltaPri', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
    ]

# Define Windows API functions
kernel32 = ctypes.windll.kernel32
kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenThread.restype = wintypes.HANDLE

kernel32.SuspendThread.argtypes = [wintypes.HANDLE]
kernel32.SuspendThread.restype = wintypes.DWORD

kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
kernel32.ResumeThread.restype = wintypes.DWORD

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
kernel32.Thread32First.restype = wintypes.BOOL

kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
kernel32.Thread32Next.restype = wintypes.BOOL

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE


class ProcessManager:
    """Manages the Minecraft server process"""
    
    def __init__(self, server_interface, config: Dict[str, Any]):
        self.server_interface = server_interface
        self.config = config
        self.is_suspended = False
        self.suspended_threads = []  # Track suspended threads for resumption
        
    def get_server_process(self) -> Optional[int]:
        """Get the Minecraft server process PID using MCDReforged's API"""
        # Get the server process PIDs from MCDReforged
        try:
            server_instance = self.server_interface
            if server_instance:
                # Get all server process PIDs from MCDReforged
                server_pids = server_instance.get_server_pid_all()
                
                if server_pids:
                    # Prefer the second PID if available (usually the Java process)
                    if len(server_pids) >= 2:
                        server_pid = server_pids[1]
                        self.server_interface.logger.info(f"Using server process PID: {server_pid}")
                        return server_pid
                    else:
                        # If only one PID available, use it
                        server_pid = server_pids[0]
                        self.server_interface.logger.info(f"Using server process PID: {server_pid}")
                        return server_pid
                else:
                    self.server_interface.logger.warning("MCDReforged returned empty list for server PIDs (server might be stopped)")
                    return None
            else:
                self.server_interface.logger.error("Failed to get MCDReforged server instance")
                return None
        except Exception as e:
            self.server_interface.logger.error(f"Failed to get server PIDs from MCDReforged: {e}")
            return None
    
    
    
    
    
    def suspend_server_windows(self) -> bool:
        """Suspend the server process using Windows API (more reliable)"""
        if not self.is_suspended:
            process_pid = self.get_server_process()
            if process_pid:
                try:
                    self.server_interface.logger.info(f"Attempting to suspend server process {process_pid} using Windows API")
                    
                    # Create snapshot of all threads
                    thread_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
                    if thread_snapshot == -1:
                        self.server_interface.logger.error("Failed to create thread snapshot")
                        return False
                    
                    # Suspend all threads of the target process
                    thread_entry = THREADENTRY32()
                    thread_entry.dwSize = ctypes.sizeof(THREADENTRY32)
                    
                    suspended_count = 0
                    self.suspended_threads = []
                    
                    if kernel32.Thread32First(thread_snapshot, ctypes.byref(thread_entry)):
                        while True:
                            thread_id = thread_entry.th32ThreadID
                            owner_process_id = thread_entry.th32OwnerProcessID
                            
                            if owner_process_id == process_pid:
                                # Open the thread
                                thread_handle = kernel32.OpenThread(THREAD_SUSPEND_RESUME, False, thread_id)
                                if thread_handle:
                                    # Suspend the thread
                                    suspend_count = kernel32.SuspendThread(thread_handle)
                                    if suspend_count != 0xFFFFFFFF:  # Success
                                        self.suspended_threads.append(thread_handle)
                                        suspended_count += 1
                                    else:
                                        kernel32.CloseHandle(thread_handle)
                            
                            # Get next thread
                            if not kernel32.Thread32Next(thread_snapshot, ctypes.byref(thread_entry)):
                                break
                    
                    kernel32.CloseHandle(thread_snapshot)
                    
                    if suspended_count > 0:
                        self.is_suspended = True
                        self.server_interface.logger.info(f"Successfully suspended {suspended_count} threads of process {process_pid}")
                        return True
                    else:
                        self.server_interface.logger.error("No threads were suspended")
                        return False
                        
                except Exception as e:
                    self.server_interface.logger.error(f"Failed to suspend process using Windows API: {e}")
                    # Clean up any partially suspended threads
                    self.resume_server_windows()
                    return False
        return False

    def suspend_server(self) -> bool:
        """Suspend the server process"""
        if not self.config["hibernation"]["stop_server"]:
            # Use Windows-specific method
            if os.name == 'nt':  # Windows
                return self.suspend_server_windows()
            else:
                self.server_interface.logger.error("Process suspension is only supported on Windows")
                return False
        else:
            self.server_interface.logger.info("Process suspension is disabled in config")
            return False
    
    def resume_server_windows(self) -> bool:
        """Resume the server process using Windows API"""
        if self.is_suspended and self.suspended_threads:
            process_pid = self.get_server_process()
            if process_pid:
                try:
                    self.server_interface.logger.info(f"Attempting to resume server process {process_pid} using Windows API")
                    
                    resumed_count = 0
                    failed_threads = []
                    
                    # Resume all suspended threads
                    for thread_handle in self.suspended_threads:
                        try:
                            resume_count = kernel32.ResumeThread(thread_handle)
                            if resume_count != 0xFFFFFFFF:  # Success
                                resumed_count += 1
                            else:
                                failed_threads.append(thread_handle)
                        except Exception as e:
                            self.server_interface.logger.error(f"Failed to resume thread: {e}")
                            failed_threads.append(thread_handle)
                        finally:
                            kernel32.CloseHandle(thread_handle)
                    
                    # Clear the suspended threads list
                    self.suspended_threads = []
                    self.is_suspended = False
                    
                    if resumed_count > 0:
                        self.server_interface.logger.info(f"Successfully resumed {resumed_count} threads of process {process_pid}")
                        
                        if failed_threads:
                            self.server_interface.logger.warning(f"Failed to resume {len(failed_threads)} threads")
                        
                        return True
                    else:
                        self.server_interface.logger.error("No threads were resumed")
                        return False
                        
                except Exception as e:
                    self.server_interface.logger.error(f"Failed to resume process using Windows API: {e}")
                    return False
        return True  # Already resumed or never suspended

    def resume_server(self) -> bool:
        """Resume the server process"""
        if self.is_suspended:
            # Use Windows-specific method
            if os.name == 'nt' and self.suspended_threads:  # Windows and we have suspended threads
                return self.resume_server_windows()
            else:
                self.server_interface.logger.error("Process resumption is only supported on Windows")
                return False
        else:
            self.server_interface.logger.info("Process is not suspended, no need to resume")
            return True
    
    def stop_server(self) -> bool:
        """Stop the server process using MCDReforged's API"""
        try:
            # Use MCDReforged's method to stop the server
            self.server_interface.stop()
            self.server_interface.logger.info("Server stop command sent")
            return True
        except Exception as e:
            self.server_interface.logger.error(f"Failed to stop server: {e}")
            return False
    
    def is_server_running(self) -> bool:
        """Check if server is running using MCDReforged's API"""
        try:
            # Check if server is running using MCDReforged's API
            return self.server_interface.is_server_running()
        except Exception as e:
            self.server_interface.logger.error(f"Failed to check server status: {e}")
            return False
    
    def is_server_suspended(self) -> bool:
        """Check if server is suspended"""
        return self.is_suspended
    
    def get_server_pid(self) -> Optional[int]:
        """Get server process PID using MCDReforged's API"""
        return self.get_server_process()
    
    