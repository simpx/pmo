#!/usr/bin/env python3
"""
Command-line interface for Servly process manager.
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

from servly.service import ServiceManager
from servly.logs import LogManager
from servly.logs import Colors, Emojis  # 导入颜色和表情符号定义
from servly.logs import align_colored_text  # 导入对齐工具函数

# 配置彩色日志记录器
class ColoredFormatter(logging.Formatter):
    """添加颜色支持的日志格式化器"""
    
    def format(self, record):
        log_message = super().format(record)
        
        if record.levelno >= logging.ERROR:
            return f"{Emojis.ERROR} {Colors.BRIGHT_RED}{log_message}{Colors.RESET}"
        elif record.levelno >= logging.WARNING:
            return f"{Emojis.WARNING} {Colors.YELLOW}{log_message}{Colors.RESET}"
        elif record.levelno >= logging.INFO:
            return f"{Emojis.INFO} {Colors.GREEN}{log_message}{Colors.RESET}"
        else:
            return f"{Colors.BRIGHT_BLACK}{log_message}{Colors.RESET}"

# 配置日志
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger = logging.getLogger('servly')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

def print_header():
    """打印美化的 Servly 头部"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 50}")
    print(f"{Emojis.SERVICE} SERVLY {Colors.BRIGHT_BLACK}- Modern Process Manager")
    print(f"{Colors.CYAN}{'=' * 50}{Colors.RESET}\n")

def setup_arg_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description=f"{Colors.CYAN}{Colors.BOLD}{Emojis.SERVICE} Servly - Modern process manager{Colors.RESET}",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 全局参数
    parser.add_argument('-f', '--config', 
                      help='配置文件路径 (默认: servly.yml)',
                      default='servly.yml')
    
    subparsers = parser.add_subparsers(dest='command', help='要执行的命令')
    
    # Start 命令
    start_parser = subparsers.add_parser('start', help=f'{Emojis.START} 启动服务')
    start_parser.add_argument('service', nargs='?', default='all', 
                            help='服务名称或 "all" 启动所有服务')
    
    # Stop 命令
    stop_parser = subparsers.add_parser('stop', help=f'{Emojis.STOP} 停止服务')
    stop_parser.add_argument('service', nargs='?', default='all',
                           help='服务名称或 "all" 停止所有服务')
    
    # Restart 命令
    restart_parser = subparsers.add_parser('restart', help=f'{Emojis.RESTART} 重启服务')
    restart_parser.add_argument('service', nargs='?', default='all',
                              help='服务名称或 "all" 重启所有服务')
    
    # Log 命令
    log_parser = subparsers.add_parser('log', help=f'{Emojis.LOG} 查看服务日志')
    log_parser.add_argument('service', nargs='?', default='all',
                          help='服务名称或 "all" 查看所有日志')
    log_parser.add_argument('--no-follow', '-n', action='store_true',
                          help='不实时跟踪日志')
    log_parser.add_argument('--lines', '-l', type=int, default=10,
                          help='初始显示的行数')
    
    # List 命令 - 保留原命令名，不改为 ps
    list_parser = subparsers.add_parser('list', help='列出服务')
    
    return parser

def handle_start(manager: ServiceManager, service_name: str) -> bool:
    """处理启动命令"""
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print(f"{Emojis.WARNING} {Colors.YELLOW}配置中没有定义任何服务。{Colors.RESET}")
            return False
        
        print(f"{Emojis.START} {Colors.BRIGHT_GREEN}正在启动所有服务...{Colors.RESET}")
        success = True
        for name in service_names:
            if not manager.start(name):
                print(f"{Emojis.ERROR} {Colors.RED}启动服务 '{name}' 失败{Colors.RESET}")
                success = False
            else:
                print(f"{Emojis.RUNNING} {Colors.GREEN}服务 '{name}' 已成功启动{Colors.RESET}")
        
        if success:
            print(f"\n{Emojis.RUNNING} {Colors.BRIGHT_GREEN}所有服务已成功启动！{Colors.RESET}")
        else:
            print(f"\n{Emojis.WARNING} {Colors.YELLOW}有些服务启动失败，请检查日志获取详情。{Colors.RESET}")
        
        return success
    else:
        result = manager.start(service_name)
        if result:
            print(f"{Emojis.RUNNING} {Colors.GREEN}服务 '{service_name}' 已成功启动{Colors.RESET}")
        else:
            print(f"{Emojis.ERROR} {Colors.RED}启动服务 '{service_name}' 失败{Colors.RESET}")
        return result

def handle_stop(manager: ServiceManager, service_name: str) -> bool:
    """处理停止命令"""
    if service_name == 'all':
        service_names = manager.get_running_services()
        if not service_names:
            print(f"{Emojis.INFO} {Colors.BRIGHT_BLACK}当前没有正在运行的服务。{Colors.RESET}")
            return True
        
        print(f"{Emojis.STOP} {Colors.YELLOW}正在停止所有服务...{Colors.RESET}")
        success = True
        for name in service_names:
            if not manager.stop(name):
                print(f"{Emojis.ERROR} {Colors.RED}停止服务 '{name}' 失败{Colors.RESET}")
                success = False
            else:
                print(f"{Emojis.STOPPED} {Colors.YELLOW}服务 '{name}' 已停止{Colors.RESET}")
        
        if success:
            print(f"\n{Emojis.STOPPED} {Colors.YELLOW}所有服务已成功停止！{Colors.RESET}")
        else:
            print(f"\n{Emojis.WARNING} {Colors.YELLOW}有些服务停止失败，请检查日志获取详情。{Colors.RESET}")
        
        return success
    else:
        result = manager.stop(service_name)
        if result:
            print(f"{Emojis.STOPPED} {Colors.YELLOW}服务 '{service_name}' 已成功停止{Colors.RESET}")
        else:
            print(f"{Emojis.ERROR} {Colors.RED}停止服务 '{service_name}' 失败{Colors.RESET}")
        return result

def handle_restart(manager: ServiceManager, service_name: str) -> bool:
    """处理重启命令"""
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print(f"{Emojis.WARNING} {Colors.YELLOW}配置中没有定义任何服务。{Colors.RESET}")
            return False
        
        print(f"{Emojis.RESTART} {Colors.MAGENTA}正在重启所有服务...{Colors.RESET}")
        success = True
        for name in service_names:
            if not manager.restart(name):
                print(f"{Emojis.ERROR} {Colors.RED}重启服务 '{name}' 失败{Colors.RESET}")
                success = False
            else:
                print(f"{Emojis.RUNNING} {Colors.MAGENTA}服务 '{name}' 已成功重启{Colors.RESET}")
        
        if success:
            print(f"\n{Emojis.RUNNING} {Colors.BRIGHT_GREEN}所有服务已成功重启！{Colors.RESET}")
        else:
            print(f"\n{Emojis.WARNING} {Colors.YELLOW}有些服务重启失败，请检查日志获取详情。{Colors.RESET}")
        
        return success
    else:
        result = manager.restart(service_name)
        if result:
            print(f"{Emojis.RUNNING} {Colors.MAGENTA}服务 '{service_name}' 已成功重启{Colors.RESET}")
        else:
            print(f"{Emojis.ERROR} {Colors.RED}重启服务 '{service_name}' 失败{Colors.RESET}")
        return result

def handle_log(manager: ServiceManager, log_manager: LogManager, args) -> bool:
    """处理日志查看命令"""
    service_name = args.service
    follow = not args.no_follow
    lines = args.lines
    
    if service_name == 'all':
        services = manager.get_service_names()
        if not services:
            print(f"{Emojis.WARNING} {Colors.YELLOW}配置中没有定义任何服务。{Colors.RESET}")
            return False
    else:
        if service_name not in manager.get_service_names():
            print(f"{Emojis.ERROR} {Colors.RED}服务 '{service_name}' 在配置中未找到。{Colors.RESET}")
            return False
        services = [service_name]
    
    # 已经在 LogManager 中添加了彩色输出
    log_manager.tail_logs(services, follow=follow, lines=lines)
    return True

def handle_list(manager: ServiceManager) -> bool:
    """处理列出服务命令"""
    service_names = manager.get_service_names()
    
    if not service_names:
        print(f"{Emojis.WARNING} {Colors.YELLOW}配置中没有定义任何服务。{Colors.RESET}")
        return True
    
    # 表头
    print(f"\n{Colors.CYAN}{Colors.BOLD}{Emojis.SERVICE} 服务列表{Colors.RESET}")
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")
    
    # 列标题
    print(f"{Colors.BOLD}{align_colored_text('  名称', 25)} {align_colored_text('状态', 20)} {align_colored_text('PID', 10)}{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}{'─' * 60}{Colors.RESET}")
    
    # 服务列表
    for name in service_names:
        is_running = manager.is_running(name)
        pid = manager.get_service_pid(name) or '-'
        
        if is_running:
            status_text = f"{Emojis.RUNNING} {Colors.GREEN}RUNNING{Colors.RESET}"
            pid_text = f"{Colors.GREEN}{pid}{Colors.RESET}"
        else:
            status_text = f"{Emojis.STOPPED} {Colors.BRIGHT_BLACK}STOPPED{Colors.RESET}"
            pid_text = f"{Colors.BRIGHT_BLACK}{pid}{Colors.RESET}"
        
        # 为不同服务使用不同颜色
        service_color = Colors.CYAN if is_running else Colors.BRIGHT_BLACK
        service_text = f"{service_color}{name}{Colors.RESET}"
        
        # 使用对齐辅助函数确保正确对齐包含颜色代码的文本
        aligned_service = align_colored_text(f"  {service_text}", 25)
        aligned_status = align_colored_text(status_text, 20)
        aligned_pid = align_colored_text(pid_text, 10)
        
        print(f"{aligned_service}{aligned_status}{aligned_pid}")
    
    print(f"\n{Colors.BRIGHT_BLACK}配置文件: {manager.config_path}{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}运行中服务: {len(manager.get_running_services())}/{len(service_names)}{Colors.RESET}")
    print()
    
    return True

def main():
    """CLI 应用程序入口点"""
    # 显示头部
    print_header()
    
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 创建服务管理器
    try:
        service_manager = ServiceManager(config_path=args.config)
    except Exception as e:
        print(f"{Emojis.ERROR} {Colors.RED}加载配置文件时出错: {e}{Colors.RESET}")
        return 1
    
    # 创建日志管理器
    log_manager = LogManager(service_manager.log_dir)
    
    # 处理命令
    try:
        if args.command == 'start':
            success = handle_start(service_manager, args.service)
        elif args.command == 'stop':
            success = handle_stop(service_manager, args.service)
        elif args.command == 'restart':
            success = handle_restart(service_manager, args.service)
        elif args.command == 'log':
            success = handle_log(service_manager, log_manager, args)
        elif args.command == 'list':
            success = handle_list(service_manager)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print(f"\n{Emojis.STOP} {Colors.BRIGHT_BLACK}操作被用户中断{Colors.RESET}")
        return 1
    except Exception as e:
        print(f"\n{Emojis.ERROR} {Colors.RED}执行命令时出错: {e}{Colors.RESET}")
        return 1
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())