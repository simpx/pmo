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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger('servly')

def setup_arg_parser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Servly - Simple process manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global arguments
    parser.add_argument('-f', '--config', 
                      help='Path to the configuration file (default: servly.yml)',
                      default='servly.yml')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start services')
    start_parser.add_argument('service', nargs='?', default='all', 
                            help='Service name or "all" to start all services')
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop services')
    stop_parser.add_argument('service', nargs='?', default='all',
                           help='Service name or "all" to stop all services')
    
    # Restart command
    restart_parser = subparsers.add_parser('restart', help='Restart services')
    restart_parser.add_argument('service', nargs='?', default='all',
                              help='Service name or "all" to restart all services')
    
    # Log command
    log_parser = subparsers.add_parser('log', help='View service logs')
    log_parser.add_argument('service', nargs='?', default='all',
                          help='Service name or "all" to view all logs')
    log_parser.add_argument('--no-follow', '-n', action='store_true',
                          help='Do not follow logs in real-time')
    log_parser.add_argument('--lines', '-l', type=int, default=10,
                          help='Number of lines to display initially')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List services')
    
    return parser

def handle_start(manager: ServiceManager, service_name: str) -> bool:
    """Handle the start command."""
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print("No services defined in configuration.")
            return False
            
        success = True
        for name in service_names:
            if not manager.start(name):
                success = False
        return success
    else:
        return manager.start(service_name)

def handle_stop(manager: ServiceManager, service_name: str) -> bool:
    """Handle the stop command."""
    if service_name == 'all':
        service_names = manager.get_running_services()
        if not service_names:
            print("No services are currently running.")
            return True
            
        success = True
        for name in service_names:
            if not manager.stop(name):
                success = False
        return success
    else:
        return manager.stop(service_name)

def handle_restart(manager: ServiceManager, service_name: str) -> bool:
    """Handle the restart command."""
    if service_name == 'all':
        service_names = manager.get_service_names()
        if not service_names:
            print("No services defined in configuration.")
            return False
            
        success = True
        for name in service_names:
            if not manager.restart(name):
                success = False
        return success
    else:
        return manager.restart(service_name)

def handle_log(manager: ServiceManager, log_manager: LogManager, args) -> bool:
    """Handle the log command."""
    service_name = args.service
    follow = not args.no_follow
    lines = args.lines
    
    if service_name == 'all':
        services = manager.get_service_names()
        if not services:
            print("No services defined in configuration.")
            return False
    else:
        if service_name not in manager.get_service_names():
            print(f"Service '{service_name}' not found in configuration.")
            return False
        services = [service_name]
        
    log_manager.tail_logs(services, follow=follow, lines=lines)
    return True

def handle_list(manager: ServiceManager) -> bool:
    """Handle the list command."""
    service_names = manager.get_service_names()
    
    if not service_names:
        print("No services defined in configuration.")
        return True
        
    print("\nServices:")
    print("-" * 50)
    print("{:<20} {:<10}".format("SERVICE", "STATUS"))
    print("-" * 50)
    
    for name in service_names:
        status = "RUNNING" if manager.is_running(name) else "STOPPED"
        print("{:<20} {:<10}".format(name, status))
        
    print()
    return True

def main():
    """Entry point for the CLI application."""
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Create the service manager with the specified config file
    service_manager = ServiceManager(config_path=args.config)
    
    # Create log manager
    log_manager = LogManager(service_manager.log_dir)
    
    # Handle commands
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
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())