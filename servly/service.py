"""
Service management functionality for Servly.
"""
import os
import subprocess
import signal
import yaml
import logging
import time
from pathlib import Path
from typing import Dict, Union, List, Optional, Any

logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages processes based on servly.yml configuration."""
    
    def __init__(self, config_path: str = "servly.yml", servly_dir: str = ".servly"):
        self.config_path = config_path
        # 修改为使用配置文件所在目录
        config_dir = os.path.dirname(os.path.abspath(config_path))
        self.servly_dir = Path(config_dir) / servly_dir
        self.pid_dir = self.servly_dir / "pids"
        self.log_dir = self.servly_dir / "logs"
        self._ensure_dirs()
        self.services = self._load_config()
        
    def _ensure_dirs(self):
        """Create required directories if they don't exist."""
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self) -> Dict[str, Any]:
        """Load service configurations from servly.yml."""
        if not os.path.exists(self.config_path):
            logger.error(f"Configuration file not found: {self.config_path}")
            return {}
            
        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file) or {}
                
            # Validate config and convert simple format to detailed format
            validated_config = {}
            for name, conf in config.items():
                if name.lower() == "servly":
                    logger.warning(f"'servly' is a reserved name and cannot be used as a service name.")
                    continue
                    
                if isinstance(conf, str):
                    validated_config[name] = {"cmd": conf}
                elif isinstance(conf, dict) and "cmd" in conf:
                    validated_config[name] = conf
                elif isinstance(conf, dict) and "script" in conf:
                    validated_config[name] = conf
                    # Convert script to cmd for consistency
                    validated_config[name]["cmd"] = conf["script"]
                else:
                    logger.warning(f"Invalid configuration for service '{name}', skipping.")
                    
            return validated_config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return {}
    
    def get_pid_file(self, service_name: str) -> Path:
        """Get the path to a service's PID file."""
        return self.pid_dir / f"{service_name}.pid"
    
    def get_service_pid(self, service_name: str) -> Optional[int]:
        """Get the PID for a running service, or None if not running."""
        pid_file = self.get_pid_file(service_name)
        if not pid_file.exists():
            return None
            
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
                
            # Check if process is still running
            if self._is_process_running(pid):
                return pid
            else:
                # Clean up stale PID file
                os.remove(pid_file)
                return None
        except (ValueError, FileNotFoundError):
            return None
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if process with given PID is running."""
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we don't have permission to send signals to it
            return True
    
    def is_running(self, service_name: str) -> bool:
        """Check if a service is running."""
        return self.get_service_pid(service_name) is not None
    
    def get_service_names(self) -> List[str]:
        """Get list of configured service names."""
        return list(self.services.keys())
    
    def get_running_services(self) -> List[str]:
        """Get list of currently running services."""
        return [name for name in self.get_service_names() if self.is_running(name)]
    
    def start(self, service_name: str) -> bool:
        """Start a specified service."""
        if service_name not in self.services:
            logger.error(f"Service '{service_name}' not found in configuration.")
            return False
            
        if self.is_running(service_name):
            logger.info(f"Service '{service_name}' is already running.")
            return True
            
        config = self.services[service_name]
        cmd = config.get("cmd")
        if not cmd:
            logger.error(f"No command specified for service '{service_name}'.")
            return False
            
        # Prepare environment variables
        env = os.environ.copy()
        if "env" in config and isinstance(config["env"], dict):
            env.update(config["env"])
            
        # Prepare working directory
        cwd = config.get("cwd", os.getcwd())
        
        # Prepare log files
        stdout_log = self.log_dir / f"{service_name}-out.log"
        stderr_log = self.log_dir / f"{service_name}-error.log"
        
        try:
            with open(stdout_log, 'a') as out, open(stderr_log, 'a') as err:
                # Add timestamp to logs
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                out.write(f"\n--- Starting service '{service_name}' at {timestamp} ---\n")
                err.write(f"\n--- Starting service '{service_name}' at {timestamp} ---\n")
                
                # Start the process
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=out,
                    stderr=err,
                    cwd=cwd,
                    env=env,
                    start_new_session=True  # Detach from current process group
                )
                
            # Save the PID to file
            with open(self.get_pid_file(service_name), 'w') as f:
                f.write(str(process.pid))
                
            logger.info(f"Started service '{service_name}' with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service '{service_name}': {str(e)}")
            return False
    
    def stop(self, service_name: str, timeout: int = 5) -> bool:
        """Stop a specified service."""
        pid = self.get_service_pid(service_name)
        if not pid:
            logger.info(f"Service '{service_name}' is not running.")
            return True
            
        try:
            # First try SIGTERM for graceful shutdown
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(timeout):
                if not self._is_process_running(pid):
                    break
                time.sleep(1)
                
            # If still running, force kill with SIGKILL
            if self._is_process_running(pid):
                os.killpg(os.getpgid(pid), signal.SIGKILL)
                time.sleep(0.5)
                
            # Clean up PID file
            pid_file = self.get_pid_file(service_name)
            if os.path.exists(pid_file):
                os.remove(pid_file)
                
            logger.info(f"Stopped service '{service_name}'")
            return True
            
        except ProcessLookupError:
            # Process already terminated
            pid_file = self.get_pid_file(service_name)
            if os.path.exists(pid_file):
                os.remove(pid_file)
            logger.info(f"Service '{service_name}' was not running")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service '{service_name}': {str(e)}")
            return False
    
    def restart(self, service_name: str) -> bool:
        """Restart a service."""
        self.stop(service_name)
        return self.start(service_name)