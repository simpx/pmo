"""
测试高级功能和错误处理。
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import yaml
import subprocess
from pmo.service import ServiceManager

class TestAdvancedFeatures:
    """测试高级功能"""
    
    @patch('subprocess.Popen')
    def test_environment_variables(self, mock_popen, temp_dir):
        """TC4.1: 验证直接在配置中设置的环境变量"""
        # 创建具有环境变量的配置
        config = {
            'env-test': {
                'cmd': 'echo "Using env var: $TEST_VAR"',
                'env': {
                    'TEST_VAR': 'custom_value'
                }
            }
        }
        
        config_path = Path(temp_dir) / 'env_test.yml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        # 创建服务管理器
        manager = ServiceManager(config_path=config_path)
        
        # 启动服务
        with patch('os.environ.copy', return_value={}):
            result = manager.start('env-test')
            assert result is True
            
            # 验证环境变量是否传递给子进程
            _, kwargs = mock_popen.call_args
            assert 'env' in kwargs
            assert kwargs['env']['TEST_VAR'] == 'custom_value'
    
    @patch('subprocess.Popen')
    def test_working_directory(self, mock_popen, temp_dir):
        """TC4.2: 验证工作目录设置（cwd）"""
        # 创建测试目录
        test_dir = Path(temp_dir) / 'test_subdir'
        test_dir.mkdir(exist_ok=True)
        
        # 创建具有工作目录的配置
        config = {
            'cwd-test': {
                'cmd': 'echo "Working in custom directory"',
                'cwd': str(test_dir)
            }
        }
        
        config_path = Path(temp_dir) / 'cwd_test.yml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        # 创建服务管理器
        manager = ServiceManager(config_path=config_path)
        
        # 启动服务
        result = manager.start('cwd-test')
        assert result is True
        
        # 验证工作目录是否正确设置
        _, kwargs = mock_popen.call_args
        assert 'cwd' in kwargs
        assert kwargs['cwd'] == str(test_dir)
    
    @patch('subprocess.Popen')
    def test_multiline_command(self, mock_popen, temp_dir):
        """TC4.3: 测试长命令行使用换行符"""
        # 创建包含多行命令的配置
        config = {
            'multiline-cmd': {
                'cmd': """python -c "
import sys
import time
print('Testing multiline command')
time.sleep(0.1)
sys.stdout.flush()
print('Command executed successfully')
"
"""
            },
            'multiline-cmd-with-env': {
                'cmd': """
                    PYTHONPATH=/path/to/lib \
                    DEBUG=true \
                    LOG_LEVEL=debug \
                    python -m complex_script \
                        --arg1=value1 \
                        --arg2=value2 \
                        --enabled \
                        --config=/etc/config.json
                """
            }
        }
        
        config_path = Path(temp_dir) / 'multiline_cmd_test.yml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        # 创建服务管理器
        manager = ServiceManager(config_path=config_path)
        
        # 启动第一个多行脚本服务
        result1 = manager.start('multiline-cmd')
        assert result1 is True
        
        # 验证命令是否被正确传递，保留换行符
        call1_args, call1_kwargs = mock_popen.call_args_list[0]
        assert call1_kwargs.get('shell') is True, "命令应该以 shell=True 模式执行"
        cmd1 = call1_args[0]
        
        # 验证多行命令中的关键部分
        assert "import sys" in cmd1
        assert "import time" in cmd1
        assert "Testing multiline command" in cmd1
        
        # 重置模拟并设置新的返回值
        mock_popen.reset_mock()
        mock_process2 = MagicMock()
        mock_process2.pid = 12346
        mock_popen.return_value = mock_process2
        
        # 启动第二个带环境变量和行连接符的服务
        result2 = manager.start('multiline-cmd-with-env')
        assert result2 is True
        
        # 验证带续行符的命令是否被正确处理
        call2_args, call2_kwargs = mock_popen.call_args_list[0]
        assert call2_kwargs.get('shell') is True, "命令应该以 shell=True 模式执行"
        cmd2 = call2_args[0]
        
        # 验证包含续行符和缩进的命令中的关键部分
        assert "python -m complex_script" in cmd2
        assert "--arg1=value1" in cmd2
        assert "--arg2=value2" in cmd2
        assert "--enabled" in cmd2
        assert "--config=/etc/config.json" in cmd2
        
        # 验证环境变量是否在命令字符串中
        assert "PYTHONPATH=/path/to/lib" in cmd2
        assert "DEBUG=true" in cmd2
        assert "LOG_LEVEL=debug" in cmd2

class TestErrorHandling:
    """测试错误处理"""
    
    def test_nonexistent_service(self, basic_config_file):
        """TC5.1: 处理不存在的服务"""
        manager = ServiceManager(config_path=basic_config_file)
        
        # 尝试启动不存在的服务
        with patch('logging.Logger.error') as mock_log:
            result = manager.start('non-existent-service')
            assert result is False
            
            # 验证是否记录了错误
            mock_log.assert_called_once()
            assert "not found" in mock_log.call_args[0][0]
    
    def test_already_running_service(self, basic_config_file):
        """TC5.2: 处理已经运行的服务"""
        manager = ServiceManager(config_path=basic_config_file)
        
        # 模拟服务已在运行
        with patch.object(manager, 'is_running', return_value=True), \
             patch('logging.Logger.info') as mock_log:
            result = manager.start('test-echo')
            assert result is True  # 应该返回成功，因为服务"已经"在运行
            
            # 验证是否记录了信息
            mock_log.assert_called_once()
            assert "already running" in mock_log.call_args[0][0]
    
    def test_invalid_config_file(self, temp_dir):
        """TC5.3: 处理配置文件错误"""
        # 创建格式错误的配置文件
        invalid_config_path = Path(temp_dir) / 'invalid.yml'
        with open(invalid_config_path, 'w') as f:
            f.write("invalid: yaml: content: -")
        
        with patch('logging.Logger.error') as mock_log:
            manager = ServiceManager(config_path=invalid_config_path)
            
            # 验证是否记录了错误
            mock_log.assert_called()
            assert "Error loading configuration" in mock_log.call_args[0][0]
            
            # 验证服务列表为空
            assert len(manager.get_service_names()) == 0

class TestReservedName:
    """测试保留名称限制"""
    
    def test_reserved_name(self, temp_dir):
        """TC6.1: 验证保留名称限制"""
        # 创建带有保留名称的配置
        config = {
            'normal-service': 'echo "Normal service"',
            'pmo': 'echo "Reserved name service"'
        }
        
        config_path = Path(temp_dir) / 'reserved_test.yml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        with patch('logging.Logger.warning') as mock_log:
            manager = ServiceManager(config_path=config_path)
            
            # 验证保留名称服务被忽略
            service_names = manager.get_service_names()
            assert 'normal-service' in service_names
            assert 'pmo' not in service_names
            
            # 验证是否记录了警告
            mock_log.assert_called_once()
            assert "reserved name" in mock_log.call_args[0][0]

class TestDirectoryStructure:
    """测试目录结构验证"""
    
    def test_directory_structure(self, temp_dir):
        """TC7.1: 验证 .pmo 目录结构"""
        # 创建服务管理器
        manager = ServiceManager()
        
        # 验证目录结构是否正确
        assert manager.pmo_dir.exists()
        assert manager.pid_dir.exists()
        assert manager.log_dir.exists()
    
    @patch('subprocess.Popen')
    def test_pid_file_creation(self, mock_popen, basic_config_file):
        """TC7.2: 验证 PID 文件创建"""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        manager = ServiceManager(config_path=basic_config_file)
        
        # 创建一个计数器来跟踪对 open 的调用
        open_calls = {}
        original_open = open
        
        # 模拟 open 函数，以便我们可以单独测试 PID 文件写入
        def mock_open_function(file_path, mode='r', *args, **kwargs):
            file_path_str = str(file_path)
            if 'pids' in file_path_str and mode == 'w':
                # 如果是 PID 文件的写入操作
                mock_file = MagicMock()
                open_calls[file_path_str] = mock_file
                return mock_file
            # 对其他文件操作使用实际的 open 函数
            return original_open(file_path, mode, *args, **kwargs)
        
        # 启动服务
        with patch('builtins.open', side_effect=mock_open_function):
            manager.start('test-sleep')
            
            # 验证是否创建了 PID 文件并写入了正确的 PID
            pid_file_path = str(manager.get_pid_file('test-sleep'))
            assert pid_file_path in open_calls, "PID 文件没有被创建"
            
            # 获取 PID 文件的模拟文件对象并验证写入
            mock_file = open_calls[pid_file_path]
            mock_file.__enter__.return_value.write.assert_called_once_with(str(mock_process.pid))
    
    @patch('subprocess.Popen')
    def test_log_file_creation(self, mock_popen, basic_config_file):
        """TC7.3: 验证日志文件创建"""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        manager = ServiceManager(config_path=basic_config_file)
        
        # 启动服务
        with patch('builtins.open') as mock_open:
            manager.start('test-echo')
            
            # 验证是否创建/打开了日志文件
            expected_stdout_path = manager.log_dir / 'test-echo-out.log'
            expected_stderr_path = manager.log_dir / 'test-echo-error.log'
            
            # 应该有对日志文件的写入操作
            open_calls = [call[0][0] for call in mock_open.call_args_list]
            assert str(expected_stdout_path) in str(open_calls)
            assert str(expected_stderr_path) in str(open_calls)