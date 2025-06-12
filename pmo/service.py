"""
Service management functionality for PMO.
"""
import os
import subprocess
import signal
import yaml
import logging
import time
import psutil
import socket
from pathlib import Path
from datetime import datetime
import re
import shutil
import mimetypes
from typing import Dict, Union, List, Optional, Any, Tuple
from dotenv import dotenv_values

from pmo.logs import console

# 初始化mimetypes
mimetypes.init()
# 确保.py扩展名被正确映射为Python脚本
if '.py' not in mimetypes.types_map:
    mimetypes.add_type('text/x-python', '.py')
if '.pyw' not in mimetypes.types_map:
    mimetypes.add_type('text/x-python', '.pyw')

logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages processes based on pmo.yml configuration."""
    
    def __init__(self, config_path: str = "pmo.yml", pmo_dir: str = ".pmo"):
        self.config_path = config_path
        # 修改为使用配置文件所在目录
        config_dir = os.path.dirname(os.path.abspath(config_path))
        self.config_dir = config_dir
        self.pmo_base_dir = Path(config_dir) / pmo_dir
        # 使用主机名创建子目录，使多台机器可共享同一个NAS
        hostname = socket.gethostname()
        self.pmo_dir = self.pmo_base_dir / hostname
        self.pid_dir = self.pmo_dir / "pids"
        self.log_dir = self.pmo_dir / "logs"
        # 存储服务启动时间，用于计算运行时长
        self.start_times = {}
        # 存储服务重启次数
        self.restarts = {}
        # 存储从.env文件加载的环境变量
        self.dotenv_vars = {}
        self._ensure_dirs()
        # 加载.env文件
        self._load_dotenv()
        self.services = self._load_config()
        # 加载现有的服务启动时间
        self._load_start_times()
        # 加载现有的服务重启次数
        self._load_restarts()
        
    def _ensure_dirs(self):
        """Create required directories if they don't exist."""
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_dotenv(self):
        """Load environment variables from .env file if it exists."""
        dotenv_path = Path(self.config_dir) / ".env"
        
        if not dotenv_path.exists():
            logger.debug(f"No .env file found at {dotenv_path}")
            return
        
        try:
            # 使用 python-dotenv 加载环境变量
            self.dotenv_vars = dotenv_values(dotenv_path)
            logger.info(f"Loaded {len(self.dotenv_vars)} environment variables from {dotenv_path}")
        except Exception as e:
            logger.error(f"Error loading .env file: {str(e)}")
    
    def _load_start_times(self):
        """加载已运行服务的启动时间"""
        for service_name in self.get_service_names():
            if self.is_running(service_name):
                # 尝试从文件获取启动时间，如果没有则使用当前时间
                start_time_file = self.pid_dir / f"{service_name}.time"
                if start_time_file.exists():
                    try:
                        with open(start_time_file, "r") as f:
                            timestamp = float(f.read().strip())
                            self.start_times[service_name] = timestamp
                    except (ValueError, IOError):
                        # 如果文件无法读取或格式不正确，使用当前时间
                        self.start_times[service_name] = time.time()
                else:
                    # 如果没有时间文件，使用当前时间
                    self.start_times[service_name] = time.time()
    
    def _load_restarts(self):
        """加载服务重启次数"""
        for service_name in self.get_service_names():
            restart_file = self.pid_dir / f"{service_name}.restarts"
            if restart_file.exists():
                try:
                    with open(restart_file, "r") as f:
                        count = int(f.read().strip())
                        self.restarts[service_name] = count
                except (ValueError, IOError):
                    # 如果文件无法读取或格式不正确，设置为0
                    self.restarts[service_name] = 0
            else:
                # 如果没有重启文件，设置为0
                self.restarts[service_name] = 0
        
    def _load_config(self) -> Dict[str, Any]:
        """Load service configurations from pmo.yml, supporting 'extends' inheritance."""
        if not os.path.exists(self.config_path):
            logger.error(f"Configuration file not found: {self.config_path}")
            return {}

        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file) or {}

            # Step 1: 规范化所有服务配置
            raw_config = {}
            for name, conf in config.items():
                if name.lower() == "pmo":
                    logger.warning(f"'pmo' is a reserved name and cannot be used as a service name.")
                    continue
                if isinstance(conf, str):
                    raw_config[name] = {"cmd": conf}
                elif isinstance(conf, dict):
                    # 允许只包含 extends 的 dict，后续递归处理
                    d = dict(conf)
                    if "script" in d:
                        d["cmd"] = d["script"]
                    raw_config[name] = d
                else:
                    logger.warning(f"Invalid configuration for service '{name}', skipping.")

            # Step 2: 递归合并 extends
            def merge_env(parent_env, child_env):
                result = dict(parent_env or {})
                result.update(child_env or {})
                return result

            def merge_service(parent, child):
                merged = dict(parent)
                merged.update(child)
                # env 字典递归合并
                if "env" in parent or "env" in child:
                    merged["env"] = merge_env(parent.get("env"), child.get("env"))
                return merged

            def resolve_extends(name, seen=None):
                if seen is None:
                    seen = set()
                if name in seen:
                    raise ValueError(f"Circular extends detected for service '{name}'")
                seen.add(name)
                conf = raw_config.get(name)
                if conf is None:
                    raise ValueError(f"Service '{name}' not found for extends")
                if "extends" in conf:
                    parent_name = conf["extends"]
                    if parent_name not in raw_config:
                        raise ValueError(f"Service '{name}' extends unknown service '{parent_name}'")
                    parent_conf = resolve_extends(parent_name, seen)
                    merged = merge_service(parent_conf, {k: v for k, v in conf.items() if k != "extends"})
                    return merged
                else:
                    return dict(conf)

            validated_config = {}
            for name in raw_config:
                try:
                    merged = resolve_extends(name)
                    if not isinstance(merged, dict) or "cmd" not in merged:
                        logger.warning(f"Invalid configuration for service '{name}', skipping.")
                        continue
                    validated_config[name] = merged
                except Exception as e:
                    logger.error(f"Error resolving extends for service '{name}': {e}")

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
                # 删除相关的启动时间记录
                if service_name in self.start_times:
                    del self.start_times[service_name]
                start_time_file = self.pid_dir / f"{service_name}.time"
                if start_time_file.exists():
                    os.remove(start_time_file)
                return None
        except (ValueError, FileNotFoundError):
            return None
    
    def get_uptime(self, service_name: str) -> Optional[float]:
        """获取服务运行时间（以秒为单位）"""
        if service_name in self.start_times and self.is_running(service_name):
            return time.time() - self.start_times[service_name]
        return None
    
    def format_uptime(self, uptime_seconds: Optional[float]) -> str:
        """将运行时间格式化为易读格式"""
        if uptime_seconds is None:
            return "-"
        
        # 转换为整数秒
        seconds = int(uptime_seconds)
        
        # 计算天、小时、分钟、秒
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        # 格式化为易读字符串
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
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
    
    def _is_python_script(self, cmd: str, cwd: Optional[str] = None) -> bool:
        """
        判断命令是否运行Python脚本
        
        Args:
            cmd: 要执行的命令
            cwd: 命令的工作目录
            
        Returns:
            bool: 如果是Python脚本则返回True，否则返回False
        """
        # 检查命令是否以python解释器开头
        if cmd.strip().startswith(('python', 'python3', 'python2', '/usr/bin/python')) or \
           any(part.endswith(('python', 'python3', 'python2')) for part in cmd.split()):
            return True
            
        # 检查第一个参数是否是Python脚本文件
        cmd_parts = cmd.strip().split()
        if not cmd_parts:
            return False
            
        # 获取可能的脚本文件路径
        possible_script = cmd_parts[0]
        
        # 处理相对路径
        script_path = possible_script
        if not os.path.isabs(possible_script) and cwd:
            script_path = os.path.join(cwd, possible_script)
            
        # 检查文件是否存在
        if not os.path.isfile(script_path):
            return False
            
        # 使用mimetypes.guess_type检测文件类型
        mime_type, _ = mimetypes.guess_type(script_path)
        return mime_type == 'text/x-python'
        
    def start(self, service_name: str, dry_run: bool = False) -> bool:
        """
        Start a specified service.
        
        Args:
            service_name: 服务名称
            dry_run: 若为True，只返回将要执行的命令而不实际执行
        """
        if service_name not in self.services:
            logger.error(f"Service '{service_name}' not found in configuration.")
            return False
        if self.is_running(service_name) and not dry_run:
            logger.info(f"Service '{service_name}' is already running.")
            return True
        config = self.services[service_name]
        cmd = config.get("cmd")
        if not cmd:
            logger.error(f"No command specified for service '{service_name}'.")
            return False
        # Prepare environment variables (优先级: config.env > .env > os.environ)
        from pmo.util import substitute_env_vars
        env = dict(os.environ)
        if "env" in config and isinstance(config["env"], dict):
            config_env = {k: str(v) for k, v in config["env"].items()}
            env.update(self.dotenv_vars)
            env.update(config_env)
        else:
            env.update(self.dotenv_vars)
        # 环境变量替换: 支持 ${VAR}、${VAR:-default} 语法
        cmd = substitute_env_vars(cmd, env)
        # Prepare working directory
        cwd = config.get("cwd", None)
        # 使用纯Python方式检测是否为Python脚本
        if self._is_python_script(cmd, cwd):
            env['PYTHONUNBUFFERED'] = '1'
            logger.debug(f"Auto-enabled unbuffered mode for Python process: {service_name}")
            
        if dry_run:
            # 构造将要执行的命令字符串，但不执行
            cmd_str = ""
            
            # 如果指定了工作目录，添加cd命令
            if cwd:
                cmd_str += f"cd {cwd} && "
            
            # 添加环境变量
            if env:
                env_str = " ".join([f"{key}={value}" for key, value in env.items()])
                if env_str:
                    cmd_str += f"{env_str} "
            
            # 添加实际命令和参数
            cmd_str += cmd
            
            # 打印命令但不执行
            console.print(f"[bold cyan]{service_name}[/]: {cmd_str}")
            return True
        
        # 非dry-run模式下的实际执行代码
        env_copy = os.environ.copy()
        if env:
            env_copy.update(env)
        
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
                    env=env_copy,
                    start_new_session=True  # Detach from current process group
                )
                
            # Save the PID to file
            with open(self.get_pid_file(service_name), 'w') as f:
                f.write(str(process.pid))
                
            # 记录启动时间
            start_time = time.time()
            self.start_times[service_name] = start_time
            
            # 保存启动时间到文件
            start_time_file = self.pid_dir / f"{service_name}.time"
            with open(start_time_file, 'w') as f:
                f.write(str(start_time))
                
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
                
            # 清理启动时间记录
            if service_name in self.start_times:
                del self.start_times[service_name]
            
            # 删除启动时间文件
            start_time_file = self.pid_dir / f"{service_name}.time"
            if start_time_file.exists():
                os.remove(start_time_file)
                
            logger.info(f"Stopped service '{service_name}'")
            return True
            
        except ProcessLookupError:
            # Process already terminated
            pid_file = self.get_pid_file(service_name)
            if os.path.exists(pid_file):
                os.remove(pid_file)
            
            # 清理启动时间记录
            if service_name in self.start_times:
                del self.start_times[service_name]
            
            # 删除启动时间文件
            start_time_file = self.pid_dir / f"{service_name}.time"
            if start_time_file.exists():
                os.remove(start_time_file)
                
            logger.info(f"Service '{service_name}' was not running")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service '{service_name}': {str(e)}")
            return False
    
    def restart(self, service_name: str) -> bool:
        """Restart a service."""
        self.stop(service_name)
        result = self.start(service_name)
        if result:
            # 增加重启次数
            self.restarts[service_name] = self.restarts.get(service_name, 0) + 1
            # 保存重启次数到文件
            restart_file = self.pid_dir / f"{service_name}.restarts"
            with open(restart_file, 'w') as f:
                f.write(str(self.restarts[service_name]))
        return result
    
    def get_process_stats(self, service_name: str) -> Dict[str, Any]:
        """获取进程的 CPU 和内存使用情况"""
        pid = self.get_service_pid(service_name)
        stats = {"cpu_percent": None, "memory_percent": None, "memory_mb": None}
        
        if pid:
            try:
                process = psutil.Process(pid)
                # 获取 CPU 使用百分比 (非阻塞模式)
                stats["cpu_percent"] = process.cpu_percent(interval=0)
                
                # 获取内存使用情况
                memory_info = process.memory_info()
                stats["memory_mb"] = memory_info.rss / (1024 * 1024)  # 转换为 MB
                
                # 计算内存使用百分比
                stats["memory_percent"] = process.memory_percent()
                
                # 获取GPU信息 - 从进程树中获取所有进程
                gpu_stats = self.get_gpu_stats_for_process_tree(pid)
                stats.update(gpu_stats)
                
                return stats
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # 如果进程已不存在或无法访问，返回默认值
                pass
                
        return stats
    
    def get_process_tree(self, pid: int) -> List[int]:
        """获取进程及其所有子进程的PID列表"""
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)
            return [pid] + [child.pid for child in children]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return [pid]
    
    def get_gpu_stats_for_process_tree(self, pid: int) -> Dict[str, Any]:
        """获取进程树中所有进程的GPU使用情况"""
        result = {
            "gpu_memory": None,
            "gpu_bus_id": None,
            "gpu_id": None
        }
        
        # 首先检查是否有pynvml库
        try:
            import pynvml
            return self._get_gpu_stats_pynvml(pid)
        except ImportError:
            # 如果没有pynvml，回退到nvidia-smi命令
            pass
        
        try:
            # 获取进程树中的所有PID
            process_tree_pids = self.get_process_tree(pid)
            
            # 检查nvidia-smi命令是否存在
            if not self._is_command_available("nvidia-smi"):
                logger.warning("nvidia-smi command not available")
                return result
            
            # 先获取所有GPU设备信息，用于映射总线ID到设备ID
            cmd_devices = ["nvidia-smi", "--query-gpu=index,gpu_bus_id", "--format=csv,noheader"]
            output_devices = subprocess.check_output(cmd_devices, universal_newlines=True)
            
            # 解析设备信息，创建总线ID到设备ID的映射
            pci_to_device_id = {}
            for line in output_devices.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split(', ')
                if len(parts) == 2:
                    device_idx = parts[0].strip()
                    bus_id = parts[1].strip()
                    pci_to_device_id[bus_id] = device_idx
            
            # 使用nvidia-smi获取GPU信息
            cmd = ["nvidia-smi", "--query-compute-apps=pid,gpu_name,used_memory,gpu_bus_id", "--format=csv,noheader"]
            output = subprocess.check_output(cmd, universal_newlines=True)
            
            # 解析输出
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split(', ')
                if len(parts) >= 4:
                    try:
                        process_pid = int(parts[0].strip())
                        if process_pid in process_tree_pids:
                            result["gpu_memory"] = parts[2].strip()
                            bus_id = parts[3].strip()
                            result["gpu_bus_id"] = bus_id
                            
                            # 将总线ID转换为设备ID
                            result["gpu_id"] = pci_to_device_id.get(bus_id, "?")
                            break
                    except (ValueError, IndexError):
                        continue
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"Error getting GPU stats: {str(e)}")
        
        return result
    
    def _get_gpu_stats_pynvml(self, pid: int) -> Dict[str, Any]:
        """使用pynvml获取GPU信息"""
        import pynvml
        result = {
            "gpu_memory": None,
            "gpu_bus_id": None,
            "gpu_id": None
        }
        
        try:
            # 初始化NVML库
            pynvml.nvmlInit()
            
            # 获取进程树
            process_tree_pids = self.get_process_tree(pid)
            
            # 获取设备数量
            device_count = pynvml.nvmlDeviceGetCount()
            
            # 遍历每个GPU设备
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                # 获取进程信息
                processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                
                for process in processes:
                    if process.pid in process_tree_pids:
                        # 将内存从字节转换为MB
                        memory_mb = process.usedGpuMemory / (1024 * 1024)
                        result["gpu_memory"] = f"{int(memory_mb)} MiB"
                        
                        # 获取GPU总线ID
                        bus_id = pynvml.nvmlDeviceGetPciInfo(handle).busId
                        if isinstance(bus_id, bytes):
                            bus_id = bus_id.decode('utf-8')
                        result["gpu_bus_id"] = bus_id
                        
                        # 直接使用设备索引作为GPU ID
                        result["gpu_id"] = str(i)
                        break
            
            # 关闭NVML
            pynvml.nvmlShutdown()
            
        except Exception as e:
            logger.debug(f"Error getting GPU stats using pynvml: {str(e)}")
            
        return result
    
    def _is_command_available(self, cmd: str) -> bool:
        """检查命令是否可用"""
        return shutil.which(cmd) is not None
    
    def format_cpu_percent(self, cpu_percent: Optional[float]) -> str:
        """格式化 CPU 使用百分比"""
        if cpu_percent is None:
            return "0%"
        return f"{cpu_percent:.1f}%"
    
    def format_memory(self, memory_mb: Optional[float], memory_percent: Optional[float]) -> str:
        """格式化内存使用情况"""
        if memory_mb is None:
            return "0b"
        
        # 如果小于 1MB，显示为 KB
        if memory_mb < 1:
            return f"{int(memory_mb * 1024)}kb"
        
        # 如果大于 1GB，显示为 GB
        if memory_mb > 1024:
            return f"{memory_mb/1024:.1f}gb"
            
        # 否则显示为 MB
        return f"{int(memory_mb)}mb"

    def format_gpu_memory(self, gpu_memory: Optional[str]) -> str:
        """格式化GPU内存使用"""
        if gpu_memory is None:
            return "0"
        return gpu_memory

    def get_restarts_count(self, service_name: str) -> int:
        """获取服务重启次数"""
        return self.restarts.get(service_name, 0)