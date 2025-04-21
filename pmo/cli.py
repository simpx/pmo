#!/usr/bin/env python3
"""
Command-line interface for PMO process manager.
Using Rich library for formatted terminal output
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

# Install Rich exception formatter
install()

# Configure Rich logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)]
)

logger = logging.getLogger("pmo")

def setup_arg_parser() -> argparse.ArgumentParser:
    """Set up command line argument parser"""
    parser = argparse.ArgumentParser(
        description=f"{Emojis.SERVICE} PMO - Modern process manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global parameters
    parser.add_argument('-f', '--config', 
                      help='Config file path (default: pmo.yml)',
                      default='pmo.yml')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Start command
    start_parser = subparsers.add_parser('start', help=f'{Emojis.START} Start services')
    start_parser.add_argument('service', nargs='?', 
                            help='Service name or "all" to start all services')
    start_parser.add_argument('--dry-run', action='store_true',
                            help='Show commands to execute without running them')
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help=f'{Emojis.STOP} Stop services')
    stop_parser.add_argument('service', nargs='?',
                           help='Service name or "all" to stop all services')
    
    # Restart command
    restart_parser = subparsers.add_parser('restart', help=f'{Emojis.RESTART} Restart services')
    restart_parser.add_argument('service', nargs='?',
                              help='Service name or "all" to restart all services')
    
    # Log command
    log_parser = subparsers.add_parser('log', help=f'{Emojis.LOG} View service logs')
    log_parser.add_argument('service', nargs='?', default='all',
                          help='Service name or "all" to view all logs')
    log_parser.add_argument('--no-follow', '-n', action='store_true',
                          help='Do not follow logs in real-time')
    log_parser.add_argument('--lines', '-l', type=int, default=10,
                          help='Number of lines to show initially')
    
    # Flush command
    flush_parser = subparsers.add_parser('flush', help=f'{Emojis.LOG} Clear service logs')
    flush_parser.add_argument('service', nargs='?', default='all',
                          help='Service name or "all" to clear all logs')
    
    # LS command (replaces original PS command)
    ls_parser = subparsers.add_parser('ls', help='List services')
    
    return parser

def show_service_prompt(manager: ServiceManager, command: str) -> None:
    """Helper function to show prompt when no service is specified"""
    print_warning(f"Please specify a service name or 'all' to {command} all services.")
    print_info(f"Usage: pmo {command} <service-name> or pmo {command} all")
    service_names = manager.get_service_names()
    if service_names:
        print_info(f"Available services: {', '.join(service_names)}")

def handle_start(manager: ServiceManager, service_name: str, dry_run: bool = False) -> bool:
    """Handle start command"""
    # Check if service_name is None (user ran just 'pmo start')
    if service_name is None:
        show_service_prompt(manager, "start")
        return False
        
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print_warning("No services defined in config.")
            return False
        
        if dry_run:
            console.print(f"{Emojis.INFO} Commands to execute (dry run):", style="running")
        else:
            console.print(f"{Emojis.START} Starting all services...", style="running")
            
        success = True
        for name in service_names:
            if not manager.start(name, dry_run=dry_run):
                print_error(f"Failed to start '{name}'")
                success = False
            else:
                if not dry_run:
                    print_success(f"Service '{name}' started")
        
        if success and not dry_run:
            print_success("All services started successfully!")
        elif not success:
            print_warning("Some services failed to start, check logs for details.")
        
        return success
    else:
        result = manager.start(service_name, dry_run=dry_run)
        if result and not dry_run:
            print_success(f"Service '{service_name}' started")
        elif not result:
            print_error(f"Failed to start '{service_name}'")
        return result

def handle_stop(manager: ServiceManager, service_name: str) -> bool:
    """Handle stop command"""
    # Check if service_name is None (user ran just 'pmo stop')
    if service_name is None:
        show_service_prompt(manager, "stop")
        return False
        
    if service_name == 'all':
        service_names = manager.get_running_services()
        if not service_names:
            console.print(f"{Emojis.INFO} No services are running.", style="dim")
            return True
        
        console.print(f"{Emojis.STOP} Stopping all services...", style="warning")
        success = True
        for name in service_names:
            if not manager.stop(name):
                print_error(f"Failed to stop '{name}'")
                success = False
            else:
                console.print(f"{Emojis.STOPPED} Service '{name}' stopped", style="stopped")
        
        if success:
            console.print(f"\n{Emojis.STOPPED} All services stopped successfully!", style="warning")
        else:
            print_warning("Some services failed to stop, check logs for details.")
        
        return success
    else:
        result = manager.stop(service_name)
        if result:
            console.print(f"{Emojis.STOPPED} Service '{service_name}' stopped", style="warning")
        else:
            print_error(f"Failed to stop '{service_name}'")
        return result

def handle_restart(manager: ServiceManager, service_name: str) -> bool:
    """Handle restart command"""
    # Check if service_name is None (user ran just 'pmo restart')
    if service_name is None:
        show_service_prompt(manager, "restart")
        return False
        
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print_warning("No services defined in config.")
            return False
        
        console.print(f"{Emojis.RESTART} Restarting all services...", style="restart")
        success = True
        for name in service_names:
            if not manager.restart(name):
                print_error(f"Failed to restart '{name}'")
                success = False
            else:
                console.print(f"{Emojis.RUNNING} Service '{name}' restarted", style="restart")
        
        if success:
            print_success("All services restarted successfully!")
        else:
            print_warning("Some services failed to restart, check logs for details.")
        
        return success
    else:
        result = manager.restart(service_name)
        if result:
            console.print(f"{Emojis.RUNNING} Service '{service_name}' restarted", style="restart")
        else:
            print_error(f"Failed to restart '{service_name}'")
        return result

def handle_log(manager: ServiceManager, log_manager: LogManager, args) -> bool:
    """Handle log command"""
    service_name = args.service
    follow = not args.no_follow
    lines = args.lines
    
    if service_name == 'all':
        services = manager.get_service_names()
        if not services:
            print_warning("No services defined in config.")
            return False
    else:
        if service_name not in manager.get_service_names():
            print_error(f"Service '{service_name}' not found in config.")
            return False
        services = [service_name]
    
    # Use LogManager to view logs
    log_manager.tail_logs(services, follow=follow, lines=lines)
    return True

def handle_flush(manager: ServiceManager, log_manager: LogManager, service_name: str) -> bool:
    """Handle flush command to clear logs"""
    # 获取正在运行的服务列表
    running_services = manager.get_running_services()
    
    if service_name == 'all':
        console.print(f"{Emojis.LOG} Flushing all logs...", style="warning")
        result = log_manager.flush_logs(running_services=running_services)
        deleted_count = result.get("deleted", 0)
        cleared_count = result.get("cleared", 0)
        
        if deleted_count > 0 or cleared_count > 0:
            if deleted_count > 0:
                print_success(f"Successfully deleted {deleted_count} log files for non-running services")
            if cleared_count > 0:
                print_success(f"Successfully cleared content of {cleared_count} log files for running services")
        else:
            print_warning("No log files found to flush")
    else:
        if service_name not in manager.get_service_names():
            print_error(f"Service '{service_name}' not found in config.")
            return False
        
        console.print(f"{Emojis.LOG} Flushing logs for '{service_name}'...", style="warning")
        result = log_manager.flush_logs([service_name], running_services=running_services)
        
        if service_name in result:
            service_result = result[service_name]
            deleted_count = service_result.get("deleted", 0)
            cleared_count = service_result.get("cleared", 0)
            
            if deleted_count > 0:
                print_success(f"Successfully deleted {deleted_count} log files for '{service_name}'")
            if cleared_count > 0:
                print_success(f"Successfully cleared content of {cleared_count} log files for '{service_name}'")
            if deleted_count == 0 and cleared_count == 0:
                print_warning(f"No log files found for '{service_name}'")
        else:
            print_warning(f"No log files found for '{service_name}'")
    
    return True

def handle_list(manager: ServiceManager) -> bool:
    """Handle list services command"""
    service_names = manager.get_service_names()
    
    if not service_names:
        print_warning("No services defined in config.")
        return True
    
    # Build service list data
    services = []
    for name in service_names:
        is_running = manager.is_running(name)
        pid = manager.get_service_pid(name)
        
        # Get service uptime
        uptime_seconds = manager.get_uptime(name) if is_running else None
        uptime = manager.format_uptime(uptime_seconds) if is_running else "0"
        
        # Get CPU and memory usage stats
        cpu_mem_stats = {}
        gpu_stats = {"gpu_memory": "-", "gpu_bus_id": "-", "gpu_id": "-"}
        if is_running:
            stats = manager.get_process_stats(name)
            cpu_mem_stats["cpu"] = manager.format_cpu_percent(stats["cpu_percent"])
            cpu_mem_stats["memory"] = manager.format_memory(stats["memory_mb"], stats["memory_percent"])
            
            # 获取 GPU 信息
            if stats.get("gpu_memory"):
                gpu_stats["gpu_memory"] = stats["gpu_memory"]
            if stats.get("gpu_bus_id"):
                gpu_stats["gpu_bus_id"] = stats["gpu_bus_id"]
            if stats.get("gpu_id"):
                gpu_stats["gpu_id"] = stats["gpu_id"]
        else:
            cpu_mem_stats["cpu"] = "0%"
            cpu_mem_stats["memory"] = "0b"
        
        # Get restart count
        restarts_count = manager.get_restarts_count(name)
        
        services.append({
            "name": name,
            "status": "running" if is_running else "stopped",
            "pid": pid,
            "uptime": uptime,
            "cpu": cpu_mem_stats["cpu"],
            "memory": cpu_mem_stats["memory"],
            "gpu_memory": gpu_stats["gpu_memory"],
            "gpu_bus_id": gpu_stats["gpu_bus_id"],
            "gpu_id": gpu_stats["gpu_id"],
            "restarts": str(restarts_count)
        })
    
    # Display services as table
    print_service_table(services)
    
    console.print(f"[dim]Config: {manager.config_path}[/]")
    console.print(f"[dim]Running: {len(manager.get_running_services())}/{len(service_names)}[/]")
    console.print()
    
    return True

def main():
    """CLI application entry point"""
    # Header removed for more compact output
    
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Create service manager
    try:
        service_manager = ServiceManager(config_path=args.config)
    except Exception as e:
        print_error(f"Error loading config file: {escape(str(e))}")
        return 1
    
    # Create log manager
    log_manager = LogManager(service_manager.log_dir)
    
    # Handle commands
    try:
        if args.command == 'start':
            success = handle_start(service_manager, args.service, args.dry_run)
        elif args.command == 'stop':
            success = handle_stop(service_manager, args.service)
        elif args.command == 'restart':
            success = handle_restart(service_manager, args.service)
        elif args.command == 'log':
            success = handle_log(service_manager, log_manager, args)
        elif args.command == 'ls':
            success = handle_list(service_manager)
        elif args.command == 'flush':
            success = handle_flush(service_manager, log_manager, args.service)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        console.print(f"\n{Emojis.STOP} Operation interrupted by user", style="dim")
        return 1
    except Exception as e:
        print_error(f"Error executing command: {escape(str(e))}")
        logger.exception("Command execution error")
        return 1
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())