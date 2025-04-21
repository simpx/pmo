"""
集成测试 Servly 项目的主要功能。
这些测试主要关注组件间的交互和真实场景下的功能表现。
"""
import os
import time
import signal
import pytest
import subprocess
import tempfile
import yaml
import psutil
from pathlib import Path
from unittest.mock import patch

from pmo.service import ServiceManager
from pmo.logs import LogManager
from pmo.cli import handle_start, handle_stop, handle_list, handle_log

class TestFullServiceLifecycle:
    """测试服务的完整生命周期，从创建配置，启动到停止"""
    
    @pytest.fixture
    def real_service_config(self):
        """创建一个能够真实运行的服务配置"""
        # 创建一个临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / 'test_pmo.yml'
            
            # 创建一个简单的长期运行测试脚本
            script_path = temp_path / 'test_long_running.py'
            with open(script_path, 'w') as f:
                f.write("""
import time
import sys

# 创建一个简单的输出文件
with open(sys.argv[1], 'w') as f:
    f.write("Service started\\n")

# 每5秒写入一次时间戳
count = 0
while count < 5:
    time.sleep(1)
    with open(sys.argv[1], 'a') as f:
        f.write(f"Timestamp: {time.time()}\\n")
    count += 1
                """)
                
            # 创建一个简单的立即退出脚本
            echo_script_path = temp_path / 'test_echo.py'
            with open(echo_script_path, 'w') as f:
                f.write("""
import sys
print(f"Echo test with args: {sys.argv[1:]}")
                """)
            
            # 创建配置文件
            output_file = temp_path / 'service_output.txt'
            config = {
                'long-running': f'python {script_path} {output_file}',
                'quick-echo': {
                    'cmd': f'python {echo_script_path} test1 test2',
                    'env': {
                        'TEST_ENV': 'integration_test'
                    }
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f)
                
            yield {
                'config_path': config_path,
                'output_file': output_file,
                'temp_dir': temp_path
            }
    
    def test_service_lifecycle(self, real_service_config):
        """测试服务的完整生命周期，从配置到启动再到停止"""
        config_path = real_service_config['config_path']
        output_file = real_service_config['output_file']
        
        # 创建服务管理器
        manager = ServiceManager(config_path=str(config_path))
        
        # 检查配置是否正确加载
        services = manager.get_service_names()
        assert 'long-running' in services
        assert 'quick-echo' in services
        
        # 启动快速完成的服务
        result = manager.start('quick-echo')
        assert result is True
        
        # 检查服务日志
        time.sleep(1)  # 给一点时间让日志写入
        log_path = manager.log_dir / 'quick-echo-out.log'
        assert log_path.exists()
        with open(log_path, 'r') as f:
            content = f.read()
            assert "Echo test with args" in content
        
        # 启动长期运行的服务
        result = manager.start('long-running')
        assert result is True
        
        # 验证服务正在运行
        time.sleep(1)
        pid = manager.get_service_pid('long-running')
        assert pid is not None
        assert manager.is_running('long-running')
        
        # 检查输出文件是否创建并有内容
        time.sleep(2)
        assert output_file.exists()
        with open(output_file, 'r') as f:
            content = f.read()
            assert "Service started" in content
            assert "Timestamp" in content
        
        # 停止服务
        result = manager.stop('long-running')
        assert result is True
        
        # 验证服务已停止
        time.sleep(1)
        assert not manager.is_running('long-running')
        
        # 检查 PID 文件是否被删除
        pid_file = manager.get_pid_file('long-running')
        assert not pid_file.exists()

class TestCLIIntegration:
    """测试 CLI 接口和管理器的集成"""
    
    @pytest.fixture
    def cli_test_config(self):
        """创建用于 CLI 集成测试的配置"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / 'cli_test.yml'
            
            # 创建一个简单的测试脚本
            script_path = temp_path / 'cli_test_script.py'
            with open(script_path, 'w') as f:
                f.write("""
import time
import sys
import os

print(f"Started with env: TEST_VAR={os.environ.get('TEST_VAR', 'not-set')}")
time.sleep(1)
                """)
            
            # 创建配置文件
            config = {
                'test-service': {
                    'cmd': f'python {script_path}',
                    'env': {
                        'TEST_VAR': 'cli_integration_test'
                    }
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f)
                
            yield {
                'config_path': config_path,
                'temp_dir': temp_path
            }
    
    def test_cli_start_stop(self, cli_test_config):
        """测试 CLI 启动和停止服务的功能"""
        config_path = cli_test_config['config_path']
        
        # 创建服务管理器
        manager = ServiceManager(config_path=str(config_path))
        
        # 使用 CLI 函数启动服务
        result = handle_start(manager, 'test-service')
        assert result is True
        
        # 验证服务已启动
        time.sleep(1)
        pid = manager.get_service_pid('test-service')
        assert pid is not None
        
        # 使用 CLI 函数列出服务
        with patch('pmo.cli.print_service_table') as mock_print:
            handle_list(manager)
            # 验证列表中有服务并且状态为运行中
            mock_print.assert_called()
            # 由于修改了mock对象，我们需要调整断言方式
            mock_print.assert_called_once()
            # 检查传递给print_service_table的参数中是否包含我们的服务
            args, _ = mock_print.call_args
            services_list = args[0]
            test_service_exists = any(s['name'] == 'test-service' and s['status'] == 'running' for s in services_list)
            assert test_service_exists, "服务应该在列表中并且状态为运行中"
        
        # 使用 CLI 函数停止服务
        result = handle_stop(manager, 'test-service')
        assert result is True
        
        # 验证服务已停止
        time.sleep(1)
        assert not manager.is_running('test-service')
    
    def test_log_integration(self, cli_test_config):
        """测试日志查看功能的集成"""
        config_path = cli_test_config['config_path']
        
        # 创建服务管理器
        manager = ServiceManager(config_path=str(config_path))
        log_manager = LogManager(manager.log_dir)
        
        # 先启动服务
        manager.start('test-service')
        time.sleep(2)  # 给点时间让服务运行并产生日志
        
        # 模拟参数对象
        class Args:
            service = 'test-service'
            no_follow = True
            lines = 5
        
        args = Args()
        
        # 使用 CLI 函数查看日志
        with patch('pmo.logs.console.print') as mock_print:
            handle_log(manager, log_manager, args)
            
            # 验证日志内容已打印
            mock_print.assert_called()
            
            # 检查是否打印了与test-service相关的日志内容
            service_log_printed = False
            for call in mock_print.call_args_list:
                args = call[0]
                if args and 'test-service' in str(args):
                    service_log_printed = True
                    break
            assert service_log_printed, "应该打印服务的日志信息"
        
        # 停止服务
        manager.stop('test-service')

class TestErrorHandling:
    """测试在真实场景下的错误处理能力"""
    
    def test_missing_binary(self, temp_dir):
        """测试尝试启动不存在的二进制程序"""
        config_path = Path(temp_dir) / 'error_test.yml'
        
        # 创建一个指向不存在程序的配置
        config = {
            'broken-service': 'non_existent_binary --some-arg'
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # 创建服务管理器
        manager = ServiceManager(config_path=str(config_path))
        
        # 尝试启动不存在的程序
        result = manager.start('broken-service')
        assert result is True  # 应该返回True，因为进程已启动
        
        # 检查日志是否包含错误信息
        time.sleep(1)
        err_log_path = manager.log_dir / 'broken-service-error.log'
        assert err_log_path.exists()
        
        with open(err_log_path, 'r') as f:
            content = f.read()
            # 修改断言检查，使用更通用的匹配方式
            assert "not found" in content