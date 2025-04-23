"""
Log management functionality for PMO.
Using Rich library for log formatting and display for a PM2-style log experience.
"""
import os
import sys
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich import box

# Custom Rich theme
custom_theme = Theme({
    "warning": "yellow",
    "error": "bold red",
    "info": "green",
    "dim": "dim",
    "stdout_service": "green",
    "stderr_service": "red",
    "header": "cyan bold",
    "subheader": "bright_black",
    "running": "green",
    "stopped": "bright_black",
    "restart": "magenta",
    "separator": "cyan",
})

# Create Rich console object
console = Console(theme=custom_theme)

# Service related emojis
class Emojis:
    """Service status related emojis"""
    SERVICE = "🔧"
    START = "🟢"
    STOP = "🔴"
    RESTART = "🔄"
    INFO = "ℹ️ "
    WARNING = "⚠️ "
    ERROR = "❌"
    LOG = "📝"
    STDOUT = "📤"
    STDERR = "📥"
    TIME = "🕒"
    RUNNING = "✅"
    STOPPED = "⛔"
    LOADING = "⏳"

# Rich formatting output utility functions
def print_header(title: str):
    """Print beautified title"""
    console.print()
    console.rule(f"[header]{Emojis.SERVICE} {title}[/]", style="separator")
    console.print()

def print_info(message: str):
    """Print info message"""
    console.print(f"{Emojis.INFO} {message}", style="info")

def print_warning(message: str):
    """Print warning message"""
    console.print(f"{Emojis.WARNING} {message}", style="warning")

def print_error(message: str):
    """Print error message"""
    console.print(f"{Emojis.ERROR} {message}", style="error")

def print_success(message: str):
    """Print success message"""
    console.print(f"{Emojis.RUNNING} {message}", style="running")

def print_service_table(services: List[Dict]):
    """Print service status table, compact PM2-style layout"""
    table = Table(show_header=True, header_style="header", box=box.ASCII)
    
    # PM2-style column headers
    table.add_column("id", justify="center", width=4)
    table.add_column("name", style="cyan", no_wrap=True, width=20)
    table.add_column("pid", justify="right", width=10)
    table.add_column("uptime", justify="right", width=8)
    table.add_column("status", justify="center", width=11)
    table.add_column("cpu", justify="right", width=10)
    table.add_column("mem", justify="right", width=10)
    table.add_column("gpu mem", justify="right", width=10)
    table.add_column("gpu id", justify="center", width=6)
    table.add_column("user", width=10)
    
    for service in services:
        name = service["name"]
        pid = service["pid"] or "0"
        uptime = service.get("uptime", "0")
        cpu = service.get("cpu", "0%")
        memory = service.get("memory", "0b")
        gpu_memory = service.get("gpu_memory", "-")
        gpu_id = service.get("gpu_id", "-")
        status = service["status"]
        
        # 使用服务对象中的 id 字段，而不是使用索引
        service_id = service.get("id", "0")
        
        # Get username if possible
        import os
        user = os.environ.get('USER', 'unknown')
        
        # Handle restarts count (default to 0)
        restarts = service.get("restarts", "0")
        
        status_style = "running" if status == "running" else "stopped"
        
        table.add_row(
            Text(service_id, style=status_style),
            Text(name, style=status_style),
            Text(str(pid), style=status_style),
            Text(str(uptime), style=status_style),
            Text(status, style=status_style),
            Text(str(cpu), style=status_style),
            Text(str(memory), style=status_style),
            Text(str(gpu_memory), style=status_style),
            Text(str(gpu_id), style=status_style),
            Text(user, style=status_style),
        )
    
    console.print(table)
    console.print()


class LogManager:
    """Manage and display service logs"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.default_tail_lines = 15  # Default to showing last 15 lines of logs
        
    def get_log_files(self, service_name: str) -> Dict[str, Path]:
        """Get service's stdout and stderr log file paths"""
        return {
            'stdout': self.log_dir / f"{service_name}-out.log",
            'stderr': self.log_dir / f"{service_name}-error.log"
        }
    
    def flush_logs(self, service_names: List[str] = None, running_services: List[str] = None) -> Dict[str, int]:
        """
        清空日志文件
        
        Args:
            service_names: 要清空日志的服务名称列表，如果为None则清空所有日志文件
            running_services: 当前正在运行的服务列表，这些服务的日志文件内容会被清空但不删除文件
            
        Returns:
            Dict[str, int]: 键为服务名称，值为操作的日志文件数量
        """
        result = {}
        running_services = running_services or []
        
        # 如果没有指定服务，处理.pmo/logs目录下所有日志文件
        if not service_names:
            # 获取所有日志文件
            log_files = list(self.log_dir.glob('*-out.log')) + list(self.log_dir.glob('*-error.log'))
            
            deleted_count = 0
            cleared_count = 0
            
            for log_file in log_files:
                # 从文件名中提取服务名称
                file_name = log_file.name
                service_name = file_name.replace('-out.log', '').replace('-error.log', '')
                
                try:
                    # 如果服务正在运行，清空文件内容但不删除文件
                    if service_name in running_services:
                        # 清空文件内容
                        with open(log_file, 'w') as f:
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            f.write(f"--- Log flushed at {timestamp} ---\n")
                        cleared_count += 1
                    else:
                        # 服务未运行，直接删除文件
                        log_file.unlink()
                        deleted_count += 1
                except (IOError, PermissionError) as e:
                    print_error(f"Failed to process log file {log_file}: {str(e)}")
            
            result["deleted"] = deleted_count
            result["cleared"] = cleared_count
            return result
                
        # 对每个指定的服务处理其日志
        for service_name in service_names:
            log_files = self.get_log_files(service_name)
            deleted = 0
            cleared = 0
            
            for log_type, log_path in log_files.items():
                if log_path.exists():
                    try:
                        # 如果服务正在运行，清空文件内容但不删除文件
                        if service_name in running_services:
                            # 清空文件内容
                            with open(log_path, 'w') as f:
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                                f.write(f"--- Log flushed at {timestamp} ---\n")
                            cleared += 1
                        else:
                            # 服务未运行，直接删除文件
                            log_path.unlink()
                            deleted += 1
                    except (IOError, PermissionError) as e:
                        print_error(f"Failed to process {log_type} log for '{service_name}': {str(e)}")
            
            result[service_name] = {"deleted": deleted, "cleared": cleared}
            
        return result
    
    def _parse_log_line(self, line: str) -> Tuple[str, str]:
        """Parse log line, extract timestamp and content"""
        timestamp = ""
        content = line.rstrip()
        
        # Try to extract timestamp
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
            # Remove timestamp part from line
            content = line.replace(timestamp, "", 1).lstrip().rstrip()
        else:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return timestamp, content
    
    def tail_logs(self, service_names: List[str], follow: bool = True, lines: int = None, service_id_map: Dict[str, str] = None):
        """
        Display service logs
        
        Args:
            service_names: List of service names to view
            follow: Whether to follow logs in real-time (like tail -f)
            lines: Number of lines to show initially, defaults to self.default_tail_lines
            service_id_map: Dictionary mapping service names to their IDs (from pmo ls)
        """
        if lines is None:
            lines = self.default_tail_lines
            
        if not service_names:
            print_warning("No services specified for log viewing.")
            return

        # If no service_id_map provided, create one (fallback to indexed IDs)
        if service_id_map is None:
            service_id_map = {name: str(i) for i, name in enumerate(service_names)}
            
        # Check if log files exist
        log_files = []
        for service in service_names:
            service_logs = self.get_log_files(service)
            for log_type, log_path in service_logs.items():
                if log_path.exists():
                    # Use ID from service_id_map if available, otherwise use fallback
                    service_id = service_id_map.get(service, str(service_names.index(service)))
                    log_files.append((service, log_type, log_path, service_id))
                else:
                    style = "stderr_service" if log_type == "stderr" else "stdout_service" 
                    console.print(f"{Emojis.WARNING} No {log_type} log found for [{style}]{service}[/]", style="warning")
                    
        if not log_files:
            print_warning("No log files found for specified services.")
            return
            
        if follow:
            # First show last few lines, then start following
            self._display_recent_logs(log_files, lines)
            self._follow_logs(log_files)
        else:
            self._display_recent_logs(log_files, lines)
    
    def _display_recent_logs(self, log_files: List[Tuple[str, str, Path, str]], lines: int):
        """Display recent log lines"""
        for service, log_type, log_path, service_id in log_files:
            # PM2-style title
            console.print(f"\n[dim]{log_path} last {lines} lines:[/]")
            
            try:
                # Read last N lines
                with open(log_path, 'r') as f:
                    content = f.readlines()
                    last_lines = content[-lines:] if len(content) >= lines else content
                    
                    # Print each line with service ID, PM2 format
                    for line in last_lines:
                        timestamp, message = self._parse_log_line(line)
                        style = "stderr_service" if log_type == "stderr" else "stdout_service"
                        console.print(f"{service_id} | [{style}]{service}[/] | {timestamp}: {message}")
            except Exception as e:
                print_error(f"Error reading log file: {str(e)}")
    
    def _follow_logs(self, log_files: List[Tuple[str, str, Path, str]]):
        """Follow logs in real-time (like tail -f)"""
        file_handlers = {}
        service_ids = {}
        
        try:
            # Open all log files
            for service, log_type, log_path, service_id in log_files:
                f = open(log_path, 'r')
                # Move to end of file
                f.seek(0, os.SEEK_END)
                file_handlers[(service, log_type)] = f
                service_ids[(service, log_type)] = service_id
                
            console.print(f"\n[dim]Following logs... (Press Ctrl+C to stop)[/]")
            
            while True:
                has_new_data = False
                
                for (service, log_type), f in file_handlers.items():
                    # Force file stat refresh to detect changes even with buffered writes
                    try:
                        # On some systems this can help detect file changes faster
                        os.fstat(f.fileno())
                    except Exception:
                        pass
                        
                    line = f.readline()
                    if line:
                        has_new_data = True
                        timestamp, message = self._parse_log_line(line)
                        style = "stderr_service" if log_type == "stderr" else "stdout_service"
                        service_id = service_ids[(service, log_type)]
                        console.print(f"{service_id} | [{style}]{service}[/] | {timestamp}: {message}")
                
                if not has_new_data:
                    # Use a short sleep interval to be more responsive to new output
                    time.sleep(0.05)
                    
        except KeyboardInterrupt:
            console.print(f"\n[dim]Log following stopped[/]")
        finally:
            # Close all files
            for f in file_handlers.values():
                f.close()