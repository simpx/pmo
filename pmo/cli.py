#!/usr/bin/env python3
"""
Command-line interface for PMO process manager.
使用Rich库进行终端输出格式化
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional

from pmo.service import ServiceManager
from pmo.logs import LogManager, Emojis
from pmo.logs import console, print_header, print_info, print_warning, print_error, print_success, print_service_table

from rich.logging import RichHandler
from rich.traceback import install
from rich.markup import escape

# 安装Rich的异常格式化器
install()

# 配置Rich日志处理
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)]
)

logger = logging.getLogger("pmo")

def setup_arg_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description=f"{Emojis.SERVICE} PMO - Modern process manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 全局参数
    parser.add_argument('-f', '--config', 
                      help='配置文件路径 (默认: pmo.yml)',
                      default='pmo.yml')
    
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
    
    # LS 命令 (替代原 PS 命令)
    ls_parser = subparsers.add_parser('ls', help='列出服务')
    
    return parser

def handle_start(manager: ServiceManager, service_name: str) -> bool:
    """处理启动命令"""
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print_warning("配置中没有定义任何服务。")
            return False
        
        console.print(f"{Emojis.START} 正在启动所有服务...", style="running")
        success = True
        for name in service_names:
            if not manager.start(name):
                print_error(f"启动服务 '{name}' 失败")
                success = False
            else:
                print_success(f"服务 '{name}' 已成功启动")
        
        if success:
            print_success("所有服务已成功启动！")
        else:
            print_warning("有些服务启动失败，请检查日志获取详情。")
        
        return success
    else:
        result = manager.start(service_name)
        if result:
            print_success(f"服务 '{service_name}' 已成功启动")
        else:
            print_error(f"启动服务 '{service_name}' 失败")
        return result

def handle_stop(manager: ServiceManager, service_name: str) -> bool:
    """处理停止命令"""
    if service_name == 'all':
        service_names = manager.get_running_services()
        if not service_names:
            console.print(f"{Emojis.INFO} 当前没有正在运行的服务。", style="dim")
            return True
        
        console.print(f"{Emojis.STOP} 正在停止所有服务...", style="warning")
        success = True
        for name in service_names:
            if not manager.stop(name):
                print_error(f"停止服务 '{name}' 失败")
                success = False
            else:
                console.print(f"{Emojis.STOPPED} 服务 '{name}' 已停止", style="stopped")
        
        if success:
            console.print(f"\n{Emojis.STOPPED} 所有服务已成功停止！", style="warning")
        else:
            print_warning("有些服务停止失败，请检查日志获取详情。")
        
        return success
    else:
        result = manager.stop(service_name)
        if result:
            console.print(f"{Emojis.STOPPED} 服务 '{service_name}' 已成功停止", style="warning")
        else:
            print_error(f"停止服务 '{service_name}' 失败")
        return result

def handle_restart(manager: ServiceManager, service_name: str) -> bool:
    """处理重启命令"""
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print_warning("配置中没有定义任何服务。")
            return False
        
        console.print(f"{Emojis.RESTART} 正在重启所有服务...", style="restart")
        success = True
        for name in service_names:
            if not manager.restart(name):
                print_error(f"重启服务 '{name}' 失败")
                success = False
            else:
                console.print(f"{Emojis.RUNNING} 服务 '{name}' 已成功重启", style="restart")
        
        if success:
            print_success("所有服务已成功重启！")
        else:
            print_warning("有些服务重启失败，请检查日志获取详情。")
        
        return success
    else:
        result = manager.restart(service_name)
        if result:
            console.print(f"{Emojis.RUNNING} 服务 '{service_name}' 已成功重启", style="restart")
        else:
            print_error(f"重启服务 '{service_name}' 失败")
        return result

def handle_log(manager: ServiceManager, log_manager: LogManager, args) -> bool:
    """处理日志查看命令"""
    service_name = args.service
    follow = not args.no_follow
    lines = args.lines
    
    if service_name == 'all':
        services = manager.get_service_names()
        if not services:
            print_warning("配置中没有定义任何服务。")
            return False
    else:
        if service_name not in manager.get_service_names():
            print_error(f"服务 '{service_name}' 在配置中未找到。")
            return False
        services = [service_name]
    
    # 使用LogManager查看日志
    log_manager.tail_logs(services, follow=follow, lines=lines)
    return True

def handle_list(manager: ServiceManager) -> bool:
    """处理列出服务命令"""
    service_names = manager.get_service_names()
    
    if not service_names:
        print_warning("配置中没有定义任何服务。")
        return True
    
    # 构建服务列表数据
    services = []
    for name in service_names:
        is_running = manager.is_running(name)
        pid = manager.get_service_pid(name)
        
        # 获取服务运行时间
        uptime_seconds = manager.get_uptime(name) if is_running else None
        uptime = manager.format_uptime(uptime_seconds) if is_running else "0"
        
        # 获取 CPU 和内存使用情况
        cpu_mem_stats = {}
        if is_running:
            stats = manager.get_process_stats(name)
            cpu_mem_stats["cpu"] = manager.format_cpu_percent(stats["cpu_percent"])
            cpu_mem_stats["memory"] = manager.format_memory(stats["memory_mb"], stats["memory_percent"])
        else:
            cpu_mem_stats["cpu"] = "0%"
            cpu_mem_stats["memory"] = "0b"
        
        # 获取重启次数
        restarts_count = manager.get_restarts_count(name)
        
        services.append({
            "name": name,
            "status": "running" if is_running else "stopped",
            "pid": pid,
            "uptime": uptime,
            "cpu": cpu_mem_stats["cpu"],
            "memory": cpu_mem_stats["memory"],
            "restarts": str(restarts_count)
        })
    
    # 使用Rich表格显示服务列表
    print_service_table(services)
    
    console.print(f"[dim]配置文件: {manager.config_path}[/]")
    console.print(f"[dim]运行中服务: {len(manager.get_running_services())}/{len(service_names)}[/]")
    console.print()
    
    return True

def main():
    """CLI 应用程序入口点"""
    # 移除显示头部
    # print_header("PMO - Modern Process Manager")
    
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 创建服务管理器
    try:
        service_manager = ServiceManager(config_path=args.config)
    except Exception as e:
        print_error(f"加载配置文件时出错: {escape(str(e))}")
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
        elif args.command == 'ls':
            success = handle_list(service_manager)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        console.print(f"\n{Emojis.STOP} 操作被用户中断", style="dim")
        return 1
    except Exception as e:
        print_error(f"执行命令时出错: {escape(str(e))}")
        logger.exception("命令执行异常")
        return 1
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())