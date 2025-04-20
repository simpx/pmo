"""
Log management functionality for Servly.
使用Rich库进行日志格式化和展示，实现PM2风格的日志效果。
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

# 自定义Rich主题
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

# 创建Rich控制台对象
console = Console(theme=custom_theme)

# 服务相关的 emoji
class Emojis:
    """服务状态相关的emoji图标"""
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

# Rich格式化输出工具函数
def print_header(title: str):
    """打印美化的标题"""
    console.print()
    console.rule(f"[header]{Emojis.SERVICE} {title}[/]", style="separator")
    console.print()

def print_info(message: str):
    """打印信息消息"""
    console.print(f"{Emojis.INFO} {message}", style="info")

def print_warning(message: str):
    """打印警告消息"""
    console.print(f"{Emojis.WARNING} {message}", style="warning")

def print_error(message: str):
    """打印错误消息"""
    console.print(f"{Emojis.ERROR} {message}", style="error")

def print_success(message: str):
    """打印成功消息"""
    console.print(f"{Emojis.RUNNING} {message}", style="running")

def print_service_table(services: List[Dict]):
    """打印服务状态表格"""
    table = Table(show_header=True, header_style="header", expand=True)
    table.add_column("名称", style="cyan")
    table.add_column("状态")
    table.add_column("PID")
    
    for service in services:
        name = service["name"]
        status = service["status"]
        pid = service["pid"] or "-"
        
        status_style = "running" if status == "running" else "stopped"
        status_emoji = Emojis.RUNNING if status == "running" else Emojis.STOPPED
        status_text = f"{status_emoji} {status.upper()}"
        
        table.add_row(
            name,
            Text(status_text, style=status_style),
            Text(str(pid), style=status_style)
        )
    
    console.print(table)
    console.print()


class LogManager:
    """管理和显示服务日志"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.default_tail_lines = 15  # 默认展示最后15行日志
        
    def get_log_files(self, service_name: str) -> Dict[str, Path]:
        """获取服务的stdout和stderr日志文件路径"""
        return {
            'stdout': self.log_dir / f"{service_name}-out.log",
            'stderr': self.log_dir / f"{service_name}-error.log"
        }
    
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
        显示服务日志
        
        Args:
            service_names: 要查看的服务名称列表
            follow: 是否实时跟踪日志（类似tail -f）
            lines: 初始显示的行数，默认为self.default_tail_lines
        """
        if lines is None:
            lines = self.default_tail_lines
            
        if not service_names:
            print_warning("未指定要查看日志的服务。")
            return

        # 检查日志文件是否存在
        log_files = []
        for service in service_names:
            service_logs = self.get_log_files(service)
            for log_type, log_path in service_logs.items():
                if log_path.exists():
                    log_files.append((service, log_type, log_path))
                else:
                    style = "stderr_service" if log_type == "stderr" else "stdout_service" 
                    console.print(f"{Emojis.WARNING} 未找到服务 [{style}]{service}[/] 的 {log_type} 日志。", style="warning")
                    
        if not log_files:
            print_warning("未找到指定服务的日志文件。")
            return
            
        if follow:
            # 首先显示最后几行，然后再开始跟踪
            self._display_recent_logs(log_files, lines)
            self._follow_logs(log_files)
        else:
            self._display_recent_logs(log_files, lines)
    
    def _display_recent_logs(self, log_files: List[Tuple[str, str, Path]], lines: int):
        """显示最近的日志行"""
        for service, log_type, log_path in log_files:
            # PM2风格的标题
            console.print(f"\n[dim]{log_path} last {lines} lines:[/]")
            
            try:
                # 读取最后N行
                with open(log_path, 'r') as f:
                    content = f.readlines()
                    last_lines = content[-lines:] if len(content) >= lines else content
                    
                    # 打印每一行，PM2格式
                    for line in last_lines:
                        timestamp, message = self._parse_log_line(line)
                        style = "stderr_service" if log_type == "stderr" else "stdout_service"
                        console.print(f"[{style}]{service}[/] | {timestamp}: {message}")
            except Exception as e:
                print_error(f"读取日志文件出错: {str(e)}")
    
    def _follow_logs(self, log_files: List[Tuple[str, str, Path]]):
        """实时跟踪日志（类似tail -f）"""
        file_handlers = {}
        
        try:
            # 打开所有日志文件
            for service, log_type, log_path in log_files:
                f = open(log_path, 'r')
                # 移动到文件末尾
                f.seek(0, os.SEEK_END)
                file_handlers[(service, log_type)] = f
                
            console.print(f"\n[dim]正在跟踪日志... (按Ctrl+C停止)[/]")
            
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
            console.print(f"\n[dim]已停止日志跟踪[/]")
        finally:
            # 关闭所有文件
            for f in file_handlers.values():
                f.close()