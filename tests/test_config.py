"""
测试配置文件加载功能。
"""
import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open
from pmo.service import ServiceManager

class TestConfigLoading:
    """测试配置文件加载功能 (UT-CFG-001 - UT-CFG-011)"""
    
    def test_load_valid_simple_configuration(self, basic_config_file):
        """UT-CFG-001: 加载有效的简单格式配置"""
        manager = ServiceManager(config_path=basic_config_file)
        
        # 验证配置中的服务已正确加载
        service_names = manager.get_service_names()
        assert 'test-echo' in service_names
        
        # 验证简单格式已正确解析为规范化格式
        services = manager.services
        assert 'test-echo' in services
        assert 'cmd' in services['test-echo']
        assert services['test-echo']['cmd'] == 'echo "Hello from test service"'
    
    def test_load_valid_detailed_configuration(self, basic_config_file):
        """UT-CFG-002: 加载有效的详细格式配置"""
        manager = ServiceManager(config_path=basic_config_file)
        
        # 验证详细格式已正确解析
        services = manager.services
        assert 'test-sleep' in services
        assert 'cmd' in services['test-sleep']
        assert services['test-sleep']['cmd'] == 'sleep 300'
        assert 'env' in services['test-sleep']
        assert services['test-sleep']['env']['TEST_ENV'] == 'test_value'
    
    def test_load_mixed_format_configuration(self, mixed_format_config_file):
        """UT-CFG-003: 加载混合格式配置文件"""
        manager = ServiceManager(config_path=mixed_format_config_file)
        
        # 验证所有服务都已加载
        service_names = manager.get_service_names()
        assert 'simple-service' in service_names
        assert 'detailed-service' in service_names
        assert 'script-service' in service_names
        assert len(service_names) == 3
        
        # 验证每种格式都被正确规范化
        services = manager.services
        # 简单格式
        assert services['simple-service']['cmd'] == 'echo "Simple format service"'
        # 详细格式
        assert services['detailed-service']['cmd'] == 'echo "Detailed format service"'
        assert services['detailed-service']['cwd'] == '/tmp'
        assert services['detailed-service']['env']['VAR1'] == 'value1'
        # script格式（应该被转换为cmd格式）
        assert services['script-service']['cmd'] == 'echo "Script format service"'
        assert services['script-service']['env']['VAR2'] == 'value2'
    
    def test_handle_reserved_name(self, custom_config_file):
        """UT-CFG-004: 处理保留名称 'pmo'"""
        manager = ServiceManager(config_path=custom_config_file)
        
        # 验证保留名称被忽略
        service_names = manager.get_service_names()
        assert 'pmo' not in service_names
        assert 'custom-echo' in service_names
        assert 'custom-sleep' in service_names
    
    def test_handle_invalid_configuration(self, malformed_yaml_file):
        """UT-CFG-005: 处理无效的配置文件"""
        # 应该返回空配置而不是崩溃
        manager = ServiceManager(config_path=malformed_yaml_file)
        
        # 验证没有服务被加载
        service_names = manager.get_service_names()
        assert len(service_names) == 0
    
    def test_load_env_variables(self, basic_config_file, dotenv_file):
        """UT-CFG-006: 加载.env文件变量"""
        # 确保.env文件与配置文件在同一目录
        dotenv_dir = os.path.dirname(dotenv_file)
        config_path = Path(dotenv_dir) / 'pmo.yml'
        
        # 复制基本配置到dotenv_dir
        with open(basic_config_file, 'r') as src, open(config_path, 'w') as dst:
            dst.write(src.read())
        
        # 创建服务管理器
        manager = ServiceManager(config_path=config_path)
        
        # 验证.env变量已加载
        assert 'TEST_VAR1' in manager.dotenv_vars
        assert manager.dotenv_vars['TEST_VAR1'] == 'value1'
        assert 'TEST_VAR2' in manager.dotenv_vars
        assert manager.dotenv_vars['TEST_VAR2'] == 'value2'
        assert 'EMPTY_VAR' in manager.dotenv_vars
        assert manager.dotenv_vars['EMPTY_VAR'] == ''
    
    def test_handle_missing_config_file(self, temp_dir):
        """UT-CFG-007: 处理缺失的配置文件"""
        # 使用临时目录中的不存在的文件路径
        nonexistent_path = str(Path(temp_dir) / "does_not_exist.yml")
        
        # 加载不存在的配置文件应返回空配置
        manager = ServiceManager(config_path=nonexistent_path)
        
        # 验证没有服务被加载
        service_names = manager.get_service_names()
        assert len(service_names) == 0
    
    def test_handle_utf8_characters(self, unicode_config_file):
        """UT-CFG-008: 处理UTF-8字符的配置"""
        manager = ServiceManager(config_path=unicode_config_file)
        
        # 验证UTF-8服务名称正确加载
        service_names = manager.get_service_names()
        assert 'utf8-service' in service_names
        assert 'emoji-service' in service_names
        
        # 验证UTF-8内容正确解析
        services = manager.services
        assert '你好，世界' in services['utf8-service']['cmd']
        assert '🚀' in services['emoji-service']['cmd']
        assert services['emoji-service']['env']['EMOJI_VAR'] == '🎉'
    
    def test_handle_special_chars_in_names(self, special_chars_config_file):
        """UT-CFG-009: 处理服务名称中的特殊字符"""
        manager = ServiceManager(config_path=special_chars_config_file)
        
        # 验证特殊字符服务名称正确加载
        service_names = manager.get_service_names()
        assert 'service-with.dots' in service_names
        assert 'service-with-spaces and symbols!' in service_names
        
        # 验证服务配置正确加载
        services = manager.services
        assert services['service-with.dots']['cmd'] == 'echo "Service with dots"'
        assert services['service-with-spaces and symbols!']['cmd'] == 'echo "Service with spaces and symbols"'
    
    def test_handle_relative_path_resolution(self, relative_paths_config_file):
        """UT-CFG-010: 处理相对路径解析"""
        config_dir = os.path.dirname(relative_paths_config_file)
        manager = ServiceManager(config_path=relative_paths_config_file)
        
        # 验证服务已加载
        service_names = manager.get_service_names()
        assert 'relative-path-service' in service_names
        
        # 验证相对路径被解析（在dry_run模式下检查）
        with patch('pmo.logs.console.print') as mock_print:
            manager.start('relative-path-service', dry_run=True)
            
            # 检查命令包含了相对于配置文件位置的路径
            mock_print.assert_called()
            args = mock_print.call_args[0][0]
            assert 'cd ./subdir' in args
    
    def test_handle_empty_dotenv_file(self, empty_dotenv_file):
        """UT-CFG-011: 处理空的.env文件"""
        # 确保.env文件与配置文件在同一目录
        dotenv_dir = os.path.dirname(empty_dotenv_file)
        config_path = Path(dotenv_dir) / 'pmo.yml'
        
        # 创建简单配置
        config = {'test-service': 'echo "test"'}
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # 创建服务管理器
        manager = ServiceManager(config_path=config_path)
        
        # 验证空.env文件不会导致错误，且没有环境变量被添加
        assert len(manager.dotenv_vars) == 0