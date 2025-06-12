"""
测试配置和夹具（fixtures）。
"""
import os
import shutil
import tempfile
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    tmp_dir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    os.chdir(tmp_dir)
    
    # 确保 .pmo 目录的父目录存在
    pmo_base_dir = Path(tmp_dir) / '.pmo'
    pmo_base_dir.mkdir(exist_ok=True)
    # 创建主机名特定的子目录
    import socket
    hostname = socket.gethostname()
    pmo_dir = pmo_base_dir / hostname
    pmo_dir.mkdir(exist_ok=True)
    logs_dir = pmo_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    pids_dir = pmo_dir / 'pids'
    pids_dir.mkdir(exist_ok=True)
    
    yield tmp_dir
    
    # 清理
    os.chdir(old_cwd)
    shutil.rmtree(tmp_dir)

@pytest.fixture
def basic_config_file(temp_dir):
    """创建基本的配置文件用于测试"""
    config = {
        'test-echo': 'echo "Hello from test service"',
        'test-sleep': {
            'cmd': 'sleep 300',
            'env': {'TEST_ENV': 'test_value'}
        }
    }
    
    config_path = Path(temp_dir) / 'pmo.yml'
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return config_path

@pytest.fixture
def custom_config_file(temp_dir):
    """创建自定义配置文件用于测试"""
    config = {
        'custom-echo': 'echo "Hello from custom service"',
        'custom-sleep': {
            'cmd': 'sleep 30',
            'cwd': '.',
            'env': {'CUSTOM_ENV': 'custom_value'}
        },
        'pmo': 'echo "This should be ignored"'  # 测试保留名称
    }
    
    config_path = Path(temp_dir) / 'custom.yml'
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return config_path

@pytest.fixture
def mixed_format_config_file(temp_dir):
    """创建混合格式的配置文件"""
    config = {
        'simple-service': 'echo "Simple format service"',
        'detailed-service': {
            'cmd': 'echo "Detailed format service"',
            'cwd': '/tmp',
            'env': {'VAR1': 'value1'}
        },
        'script-service': {
            'script': 'echo "Script format service"',
            'env': {'VAR2': 'value2'}
        }
    }
    
    config_path = Path(temp_dir) / 'mixed.yml'
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return config_path

@pytest.fixture
def unicode_config_file(temp_dir):
    """创建包含UTF-8字符的配置文件"""
    config = {
        'utf8-service': 'echo "你好，世界! こんにちは! 안녕하세요!"',
        'emoji-service': {
            'cmd': 'echo "🚀 🔥 🌍"',
            'env': {'EMOJI_VAR': '🎉'}
        }
    }
    
    config_path = Path(temp_dir) / 'unicode.yml'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    return config_path

@pytest.fixture
def special_chars_config_file(temp_dir):
    """创建包含特殊字符的服务名称的配置文件"""
    config = {
        'service-with.dots': 'echo "Service with dots"',
        'service-with-spaces and symbols!': {
            'cmd': 'echo "Service with spaces and symbols"'
        }
    }
    
    config_path = Path(temp_dir) / 'special_chars.yml'
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return config_path

@pytest.fixture
def relative_paths_config_file(temp_dir):
    """创建包含相对路径的配置文件"""
    # 创建子目录用于测试相对路径
    subdir = Path(temp_dir) / 'subdir'
    subdir.mkdir(exist_ok=True)
    
    config = {
        'relative-path-service': {
            'cmd': 'echo "Relative path service"',
            'cwd': './subdir'  # 相对路径
        }
    }
    
    config_path = Path(temp_dir) / 'relative_paths.yml'
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return config_path

@pytest.fixture
def dotenv_file(temp_dir):
    """创建.env文件用于测试"""
    env_content = """
# This is a comment
TEST_VAR1=value1
TEST_VAR2=value2
EMPTY_VAR=
# Another comment
PATH_VAR=./some/path
    """
    
    env_path = Path(temp_dir) / '.env'
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    return env_path

@pytest.fixture
def empty_dotenv_file(temp_dir):
    """创建空的.env文件"""
    env_path = Path(temp_dir) / '.env'
    with open(env_path, 'w') as f:
        f.write("# Just a comment\n\n")
    
    return env_path

@pytest.fixture
def malformed_yaml_file(temp_dir):
    """创建格式错误的YAML文件"""
    config_path = Path(temp_dir) / 'malformed.yml'
    with open(config_path, 'w') as f:
        f.write("""
        service1: echo "test"
        service2: {
          unclosed bracket
        service3: "missing quotes
        """)
    
    return config_path

@pytest.fixture
def mock_psutil():
    """模拟psutil进程操作"""
    with patch('pmo.service.psutil') as mock:
        mock_process = MagicMock()
        mock_process.cpu_percent.return_value = 5.0
        mock_process.memory_info.return_value.rss = 1024 * 1024 * 10  # 10MB
        mock_process.memory_percent.return_value = 1.5
        mock_process.children.return_value = []
        
        mock.Process.return_value = mock_process
        yield mock

@pytest.fixture
def sample_log_files(temp_dir):
    """创建样本日志文件用于测试"""
    logs_dir = Path(temp_dir) / '.pmo' / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建带时间戳的样本日志
    stdout_log = logs_dir / 'test-service-out.log'
    with open(stdout_log, 'w') as f:
        f.write("2025-04-21 10:00:00 Starting service\n")
        f.write("2025-04-21 10:00:01 Processing request\n")
        f.write("No timestamp line\n")
        f.write("2025-04-21 10:00:02 Request completed\n")
    
    stderr_log = logs_dir / 'test-service-error.log'
    with open(stderr_log, 'w') as f:
        f.write("2025-04-21 10:00:01 [ERROR] Something went wrong\n")
    
    return {'stdout': stdout_log, 'stderr': stderr_log}