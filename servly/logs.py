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
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import random


# ANSI 颜色代码
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


# 处理彩色文本对齐的辅助函数
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
        # 为每个服务分配一个固定颜色，使日志更易读
        self.service_colors = {}
        self.available_colors = [
            Colors.GREEN, Colors.YELLOW, Colors.BLUE, Colors.MAGENTA, Colors.CYAN,
            Colors.BRIGHT_GREEN, Colors.BRIGHT_YELLOW, Colors.BRIGHT_BLUE, 
            Colors.BRIGHT_MAGENTA, Colors.BRIGHT_CYAN
        ]
        
    def get_log_files(self, service_name: str) -> Dict[str, Path]:
        """Get the stdout and stderr log files for a service."""
        return {
            'stdout': self.log_dir / f"{service_name}-out.log",
            'stderr': self.log_dir / f"{service_name}-error.log"
        }
    
    def _get_service_color(self, service_name: str) -> str:
        """为服务分配一个固定的颜色"""
        if service_name not in self.service_colors:
            if not self.available_colors:
                # 如果颜色用完了，就随机分配
                self.service_colors[service_name] = random.choice([
                    Colors.GREEN, Colors.YELLOW, Colors.BLUE, Colors.MAGENTA, Colors.CYAN
                ])
            else:
                # 从可用颜色中选择一个
                self.service_colors[service_name] = self.available_colors.pop(0)
        return self.service_colors[service_name]
    
    def _format_log_header(self, service: str, log_type: str) -> str:
        """格式化日志头部，带颜色和 emoji"""
        service_color = self._get_service_color(service)
        emoji = Emojis.STDOUT if log_type == 'stdout' else Emojis.STDERR
        type_color = Colors.GREEN if log_type == 'stdout' else Colors.YELLOW
        
        return (f"\n{Colors.BOLD}{Colors.WHITE}{Emojis.LOG} Log Stream: "
                f"{service_color}{service}{Colors.RESET} "
                f"{Colors.BRIGHT_BLACK}({type_color}{emoji} {log_type}{Colors.BRIGHT_BLACK}){Colors.RESET}\n"
                f"{Colors.BRIGHT_BLACK}{'─' * 60}{Colors.RESET}")
    
    def _format_log_line(self, service: str, log_type: str, line: str, show_timestamp: bool = True) -> str:
        """格式化单行日志，带颜色和 emoji"""
        service_color = self._get_service_color(service)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S") if show_timestamp else ""
        
        # 根据日志类型选择颜色
        line_color = Colors.RESET
        if log_type == 'stderr' and ('error' in line.lower() or 'exception' in line.lower()):
            prefix = f"{Emojis.ERROR} "
            line_color = Colors.BRIGHT_RED
        elif log_type == 'stderr':
            prefix = f"{Emojis.WARNING} "
            line_color = Colors.YELLOW
        else:
            prefix = f"{Emojis.INFO} "
        
        # 格式化输出
        if show_timestamp:
            return (f"{Colors.BRIGHT_BLACK}[{Emojis.TIME} {timestamp}]{Colors.RESET} "
                    f"{service_color}{service}{Colors.RESET} "
                    f"{prefix}{line_color}{line.rstrip()}{Colors.RESET}")
        else:
            return f"{line_color}{line.rstrip()}{Colors.RESET}"
    
    def tail_logs(self, service_names: List[str], follow: bool = True, lines: int = 10):
        """
        Display logs for specified services in real-time.
        
        Args:
            service_names: List of service names to show logs for
            follow: Whether to follow logs in real-time (like tail -f)
            lines: Number of recent lines to display initially
        """
        if not service_names:
            print(f"{Emojis.WARNING} {Colors.YELLOW}No services specified for log viewing.{Colors.RESET}")
            return

        # Check if the logs exist
        log_files = []
        for service in service_names:
            service_logs = self.get_log_files(service)
            for log_type, log_path in service_logs.items():
                if log_path.exists():
                    log_files.append((service, log_type, log_path))
                else:
                    service_color = self._get_service_color(service)
                    print(f"{Emojis.WARNING} {Colors.YELLOW}No {log_type} logs found for {service_color}{service}{Colors.RESET}.")
                    
        if not log_files:
            print(f"{Emojis.WARNING} {Colors.YELLOW}No log files found for specified services.{Colors.RESET}")
            return
            
        if follow:
            self._follow_logs(log_files)
        else:
            self._display_recent_logs(log_files, lines)
    
    def _display_recent_logs(self, log_files: List[Tuple[str, str, Path]], lines: int):
        """Display the most recent lines from log files."""
        for service, log_type, log_path in log_files:
            print(self._format_log_header(service, log_type))
            try:
                # 读取最后N行
                with open(log_path, 'r') as f:
                    content = f.readlines()
                    last_lines = content[-lines:] if len(content) >= lines else content
                    
                    # 打印每一行，增加格式
                    for line in last_lines:
                        print(self._format_log_line(service, log_type, line, show_timestamp=False))
            except Exception as e:
                print(f"{Emojis.ERROR} {Colors.RED}Error reading logs: {str(e)}{Colors.RESET}")
    
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
                
                # 打印日志头部
                print(self._format_log_header(service, log_type))
                
            print(f"\n{Emojis.LOADING} {Colors.BRIGHT_BLACK}Following logs... (Ctrl+C to stop){Colors.RESET}")
            print(f"{Colors.BRIGHT_BLACK}{'─' * 60}{Colors.RESET}")
            
            while True:
                has_new_data = False
                
                for (service, log_type), f in file_handlers.items():
                    line = f.readline()
                    if line:
                        has_new_data = True
                        print(self._format_log_line(service, log_type, line))
                
                if not has_new_data:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            print(f"\n{Emojis.STOP} {Colors.BRIGHT_BLACK}Stopped following logs.{Colors.RESET}")
        finally:
            # Close all file handlers
            for f in file_handlers.values():
                f.close()