"""
Process management for the Minecraft server
"""

import os
import time
import psutil
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
        self.server_process = None
        self.is_suspended = False
        self.suspended_threads = []  # Track suspended threads for resumption
        
    def get_server_process(self) -> Optional[psutil.Process]:
        """Get the Minecraft server process using MCDReforged's API"""
        if self.server_process and self.server_process.is_running():
            return self.server_process
        
        # Get the server process PIDs from MCDReforged
        try:
            # Use the server interface that was passed to us
            server_instance = self.server_interface
            if server_instance:
                # Get all server process PIDs from MCDReforged
                server_pids = server_instance.get_server_pid_all()
                if server_pids:
                    # Find the Java process among the server PIDs
                    java_process = None
                    for pid in server_pids:
                        try:
                            process = psutil.Process(pid)
                            # Check if this is a Java process
                            if 'java' in process.name().lower():
                                java_process = process
                                self.server_interface.logger.info(f"Found Java server process: PID {process.pid}")
                                break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    if java_process:
                        self.server_process = java_process
                        return self.server_process
                    else:
                        self.server_interface.logger.error(f"No Java process found in server PIDs: {server_pids}")
                        return None
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
            process = self.get_server_process()
            if process:
                try:
                    self.server_interface.logger.info(f"Attempting to suspend server process {process.pid} using Windows API")
                    status = process.status()
                    num_threads = process.num_threads()
                    self.server_interface.logger.info(f"Process {process.pid} status: {status}")
                    self.server_interface.logger.info(f"Process {process.pid} thread count: {num_threads}")
                    
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
                            
                            if owner_process_id == process.pid:
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
                        self.server_interface.logger.info(f"Successfully suspended {suspended_count} threads of process {process.pid}")
                        
                        # Verify suspension
                        time.sleep(0.5)
                        new_status = process.status()
                        new_num_threads = process.num_threads()
                        cpu_before = process.cpu_percent(interval=0.1)
                        time.sleep(1)
                        cpu_after = process.cpu_percent(interval=0.1)
                        
                        self.server_interface.logger.info(f"Process {process.pid} status after suspend: {new_status}")
                        self.server_interface.logger.info(f"Process {process.pid} thread count after suspend: {new_num_threads}")
                        self.server_interface.logger.info(f"Process {process.pid} CPU usage: {cpu_before}% -> {cpu_after}%")
                        
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
            process = self.get_server_process()
            if process:
                try:
                    self.server_interface.logger.info(f"Attempting to resume server process {process.pid} using Windows API")
                    status = process.status()
                    num_threads = process.num_threads()
                    self.server_interface.logger.info(f"Process {process.pid} status before resume: {status}")
                    self.server_interface.logger.info(f"Process {process.pid} thread count before resume: {num_threads}")
                    
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
                        self.server_interface.logger.info(f"Successfully resumed {resumed_count} threads of process {process.pid}")
                        
                        # Verify resumption
                        time.sleep(0.5)
                        new_status = process.status()
                        new_num_threads = process.num_threads()
                        cpu_before = process.cpu_percent(interval=0.1)
                        time.sleep(1)
                        cpu_after = process.cpu_percent(interval=0.1)
                        
                        self.server_interface.logger.info(f"Process {process.pid} status after resume: {new_status}")
                        self.server_interface.logger.info(f"Process {process.pid} thread count after resume: {new_num_threads}")
                        self.server_interface.logger.info(f"Process {process.pid} CPU usage: {cpu_before}% -> {cpu_after}%")
                        
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
        """Stop the server process"""
        process = self.get_server_process()
        if process:
            try:
                # Try graceful shutdown first
                process.terminate()
                
                # Wait for process to terminate
                try:
                    process.wait(timeout=10)
                except psutil.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    process.kill()
                    process.wait()
                
                self.server_interface.logger.info(f"Server process {process.pid} stopped")
                return True
            except Exception as e:
                self.server_interface.logger.error(f"Failed to stop process: {e}")
                return False
        return False
    
    def is_server_running(self) -> bool:
        """Check if server is running"""
        process = self.get_server_process()
        return process is not None and process.is_running()
    
    def is_server_suspended(self) -> bool:
        """Check if server is suspended"""
        return self.is_suspended
    
    def get_server_pid(self) -> Optional[int]:
        """Get server process PID"""
        process = self.get_server_process()
        return process.pid if process else None
    
    def get_server_resource_usage(self) -> Optional[Dict[str, float]]:
        """Get server resource usage"""
        process = self.get_server_process()
        if process:
            try:
                return {
                    'cpu_percent': process.cpu_percent(),
                    'memory_percent': process.memory_percent(),
                    'memory_mb': process.memory_info().rss / 1024 / 1024
                }
            except Exception as e:
                self.server_interface.logger.error(f"Failed to get resource usage: {e}")
        return None