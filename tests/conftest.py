"""
测试配置和夹具（fixtures）。
"""
import os
import shutil
import tempfile
import yaml
import pytest
from pathlib import Path

@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    tmp_dir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    os.chdir(tmp_dir)
    
    # 确保 .pmo 目录的父目录存在
    pmo_dir = Path(tmp_dir) / '.pmo'
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