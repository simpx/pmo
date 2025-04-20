"""
测试配置文件加载功能。
"""
import pytest
import os
from pathlib import Path
from pmo.service import ServiceManager

class TestConfigLoading:
    """测试配置文件加载功能"""
    
    def test_default_config_loading(self, basic_config_file):
        """TC1.1: 验证默认配置文件 pmo.yml 加载"""
        # 创建服务管理器并加载配置
        manager = ServiceManager(config_path=basic_config_file)
        
        # 验证配置中的服务已正确加载
        service_names = manager.get_service_names()
        assert 'test-echo' in service_names
        assert 'test-sleep' in service_names
        assert len(service_names) == 2
    
    def test_custom_config_loading(self, custom_config_file):
        """TC1.2: 验证自定义配置文件加载 (-f 参数)"""
        # 创建服务管理器，使用自定义配置文件
        manager = ServiceManager(config_path=custom_config_file)
        
        # 验证自定义配置文件中的服务已正确加载
        service_names = manager.get_service_names()
        assert 'custom-echo' in service_names
        assert 'custom-sleep' in service_names
        # 保留名称 "pmo" 应被忽略
        assert 'pmo' not in service_names
        assert len(service_names) == 2
    
    def test_config_format_parsing(self, basic_config_file):
        """TC1.3: 验证不同格式的配置项解析"""
        manager = ServiceManager(config_path=basic_config_file)
        
        # 验证简单格式已正确解析
        services = manager.services
        assert 'test-echo' in services
        assert 'cmd' in services['test-echo']
        assert services['test-echo']['cmd'] == 'echo "Hello from test service"'
        
        # 验证详细格式已正确解析
        assert 'test-sleep' in services
        assert 'cmd' in services['test-sleep']
        assert services['test-sleep']['cmd'] == 'sleep 300'
        assert 'env' in services['test-sleep']
        assert services['test-sleep']['env']['TEST_ENV'] == 'test_value'