"""
Log management functionality for Servly.
"""
import os
import sys
import time
import select
import fcntl
import termios
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class LogManager:
    """Handles viewing and managing logs for servly services."""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        
    def get_log_files(self, service_name: str) -> Dict[str, Path]:
        """Get the stdout and stderr log files for a service."""
        return {
            'stdout': self.log_dir / f"{service_name}-out.log",
            'stderr': self.log_dir / f"{service_name}-error.log"
        }
    
    def tail_logs(self, service_names: List[str], follow: bool = True, lines: int = 10):
        """
        Display logs for specified services in real-time.
        
        Args:
            service_names: List of service names to show logs for
            follow: Whether to follow logs in real-time (like tail -f)
            lines: Number of recent lines to display initially
        """
        if not service_names:
            print("No services specified for log viewing.")
            return

        # Check if the logs exist
        log_files = []
        for service in service_names:
            service_logs = self.get_log_files(service)
            for log_type, log_path in service_logs.items():
                if log_path.exists():
                    log_files.append((service, log_type, log_path))
                else:
                    print(f"No {log_type} logs found for {service}.")
                    
        if not log_files:
            print("No log files found for specified services.")
            return
            
        if follow:
            self._follow_logs(log_files)
        else:
            self._display_recent_logs(log_files, lines)
    
    def _display_recent_logs(self, log_files: List[tuple], lines: int):
        """Display the most recent lines from log files."""
        for service, log_type, log_path in log_files:
            print(f"\n=== {service} ({log_type}) ===")
            try:
                # Use tail command to show last N lines
                subprocess.run(["tail", "-n", str(lines), str(log_path)])
            except Exception as e:
                print(f"Error reading logs: {str(e)}")
    
    def _follow_logs(self, log_files: List[tuple]):
        """Follow logs in real-time, similar to tail -f."""
        # Dictionary to keep track of file positions
        file_handlers = {}
        
        try:
            # Open all log files
            for service, log_type, log_path in log_files:
                f = open(log_path, 'r')
                # Move to the end of the file
                f.seek(0, os.SEEK_END)
                file_handlers[(service, log_type)] = f
                
            print("Following logs... (Ctrl+C to stop)")
            
            while True:
                has_new_data = False
                
                for (service, log_type), f in file_handlers.items():
                    line = f.readline()
                    if line:
                        has_new_data = True
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"[{timestamp}] {service} ({log_type}): {line}", end="")
                
                if not has_new_data:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            print("\nStopped following logs.")
        finally:
            # Close all file handlers
            for f in file_handlers.values():
                f.close()