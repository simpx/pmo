"""
Log management functionality for Servly.
"""
import os
import sys
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import random

# Rich库导入
from rich.console import Console
from rich.theme import Theme

# 自定义Rich主题，定义我们需要的颜色样式
custom_theme = Theme({
    "warning": "yellow",
    "error": "bold red",
    "info": "green",
    "dim": "dim",
    "stdout_service": "green",
    "stderr_service": "red",
})

# 创建Rich控制台对象
console = Console(theme=custom_theme)

# ANSI 颜色代码 - 保留以确保兼容性
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


# 服务相关的 emoji
class Emojis:
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


# 处理彩色文本对齐的辅助函数 - 保留以确保兼容性
def strip_ansi_codes(text: str) -> str:
    """删除字符串中的所有 ANSI 转义代码"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def get_visible_length(text: str) -> int:
    """获取文本在终端中的可见长度（排除 ANSI 代码和宽字符）"""
    text = strip_ansi_codes(text)
    # 处理中文等宽字符（在大多数终端中占用两个字符宽度）
    length = 0
    for char in text:
        if ord(char) > 127:  # 简单判断是否是非ASCII字符
            length += 2
        else:
            length += 1
    return length

def align_colored_text(text: str, width: int, align='left') -> str:
    """
    将彩色文本对齐到指定宽度
    
    Args:
        text: 可能包含 ANSI 颜色代码的文本
        width: 期望的显示宽度
        align: 对齐方式，'left', 'right' 或 'center'
        
    Returns:
        对齐后的文本，保留颜色代码
    """
    visible_length = get_visible_length(text)
    padding = max(0, width - visible_length)
    
    if align == 'right':
        return ' ' * padding + text
    elif align == 'center':
        left_padding = padding // 2
        right_padding = padding - left_padding
        return ' ' * left_padding + text + ' ' * right_padding
    else:  # left alignment
        return text + ' ' * padding


class LogManager:
    """Handles viewing and managing logs for servly services."""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.default_tail_lines = 15  # 默认展示最后15行日志
        
    def get_log_files(self, service_name: str) -> Dict[str, Path]:
        """Get the stdout and stderr log files for a service."""
        return {
            'stdout': self.log_dir / f"{service_name}-out.log",
            'stderr': self.log_dir / f"{service_name}-error.log"
        }
    
    def _format_log_header(self, service: str, log_type: str) -> str:
        """格式化日志头部为PM2风格"""
        log_files = self.get_log_files(service)
        file_path = log_files[log_type]
        file_path_str = str(file_path)
        
        # PM2风格的头部（使用rich来打印，不需要返回格式化字符串）
        return file_path_str
    
    def _parse_log_line(self, line: str) -> Tuple[str, str]:
        """解析日志行，提取时间戳和内容"""
        timestamp = ""
        content = line.rstrip()
        
        # 尝试提取时间戳
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
            # 移除行中已有的时间戳部分
            content = line.replace(timestamp, "", 1).lstrip().rstrip()
        else:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        return timestamp, content
    
    def tail_logs(self, service_names: List[str], follow: bool = True, lines: int = None):
        """
        Display logs for specified services in real-time.
        
        Args:
            service_names: List of service names to show logs for
            follow: Whether to follow logs in real-time (like tail -f)
            lines: Number of recent lines to display initially, defaults to self.default_tail_lines
        """
        if lines is None:
            lines = self.default_tail_lines
            
        if not service_names:
            console.print(f"{Emojis.WARNING} No services specified for log viewing.", style="warning")
            return

        # Check if the logs exist
        log_files = []
        for service in service_names:
            service_logs = self.get_log_files(service)
            for log_type, log_path in service_logs.items():
                if log_path.exists():
                    log_files.append((service, log_type, log_path))
                else:
                    style = "stderr_service" if log_type == "stderr" else "stdout_service" 
                    console.print(f"{Emojis.WARNING} No {log_type} logs found for [{style}]{service}[/].", style="warning")
                    
        if not log_files:
            console.print(f"{Emojis.WARNING} No log files found for specified services.", style="warning")
            return
            
        if follow:
            # 首先显示最后几行，然后再开始跟踪
            self._display_recent_logs(log_files, lines)
            self._follow_logs(log_files)
        else:
            self._display_recent_logs(log_files, lines)
    
    def _display_recent_logs(self, log_files: List[Tuple[str, str, Path]], lines: int):
        """Display the most recent lines from log files."""
        for service, log_type, log_path in log_files:
            file_path_str = self._format_log_header(service, log_type)
            console.print(f"\n[dim]{file_path_str} last {self.default_tail_lines} lines:[/]")
            
            try:
                # 读取最后N行
                with open(log_path, 'r') as f:
                    content = f.readlines()
                    last_lines = content[-lines:] if len(content) >= lines else content
                    
                    # 打印每一行，增加格式
                    for line in last_lines:
                        timestamp, message = self._parse_log_line(line)
                        style = "stderr_service" if log_type == "stderr" else "stdout_service"
                        console.print(f"[{style}]{service}[/] | {timestamp}: {message}")
            except Exception as e:
                console.print(f"{Emojis.ERROR} Error reading logs: {str(e)}", style="error")
    
    def _follow_logs(self, log_files: List[Tuple[str, str, Path]]):
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
                
            console.print(f"\n[dim]Following logs... (Ctrl+C to stop)[/]")
            
            while True:
                has_new_data = False
                
                for (service, log_type), f in file_handlers.items():
                    line = f.readline()
                    if line:
                        has_new_data = True
                        timestamp, message = self._parse_log_line(line)
                        style = "stderr_service" if log_type == "stderr" else "stdout_service"
                        console.print(f"[{style}]{service}[/] | {timestamp}: {message}")
                
                if not has_new_data:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            console.print(f"\n[dim]Stopped following logs.[/]")
        finally:
            # Close all file handlers
            for f in file_handlers.values():
                f.close()