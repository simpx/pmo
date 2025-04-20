"""
测试日志管理功能。
"""
import pytest
import os
import io
import sys
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock, call
from servly.logs import LogManager
from servly.service import ServiceManager

class TestLogging:
    """测试日志功能"""
    
    def setup_method(self):
        """设置基本测试环境"""
        self.temp_dir = Path(os.getcwd())
        self.log_dir = self.temp_dir / '.servly' / 'logs'
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # 创建测试日志文件
        with open(self.log_dir / 'test-service-out.log', 'w') as f:
            f.write("Line 1: Standard output\nLine 2: More output\n")
        
        with open(self.log_dir / 'test-service-error.log', 'w') as f:
            f.write("Line 1: Error message\nLine 2: Another error\n")
    
    def test_log_single_service(self):
        """TC3.1: 测试查看单个服务的日志"""
        log_manager = LogManager(self.log_dir)
        
        # 测试获取日志文件
        log_files = log_manager.get_log_files('test-service')
        assert log_files['stdout'] == self.log_dir / 'test-service-out.log'
        assert log_files['stderr'] == self.log_dir / 'test-service-error.log'
        assert log_files['stdout'].exists()
        assert log_files['stderr'].exists()
    
    @patch('servly.logs.LogManager._follow_logs')
    @patch('servly.logs.LogManager._display_recent_logs')
    def test_log_all_services(self, mock_display, mock_follow, basic_config_file):
        """TC3.2: 测试查看所有服务的日志"""
        manager = ServiceManager(config_path=basic_config_file)
        
        # 创建测试日志文件
        for service in ['test-echo', 'test-sleep']:
            with open(manager.log_dir / f'{service}-out.log', 'w') as f:
                f.write(f"Test output from {service}\n")
            with open(manager.log_dir / f'{service}-error.log', 'w') as f:
                f.write(f"Test error from {service}\n")
        
        # 修改测试方法，直接验证服务管理器和日志功能的交互
        # 模拟命令行参数
        args = MagicMock()
        args.service = 'all'
        args.no_follow = False
        args.lines = 10
        
        # 打补丁到 LogManager 的 tail_logs 方法
        with patch('servly.logs.LogManager.tail_logs') as mock_tail_logs:
            from servly.cli import handle_log
            
            # 创建一个真实的 LogManager 对象
            log_manager = LogManager(manager.log_dir)
            
            # 调用处理日志的函数
            result = handle_log(manager, log_manager, args)
            
            # 验证结果和方法调用
            assert result is True
            mock_tail_logs.assert_called_once()
            
            # 验证传递给 tail_logs 的参数
            call_args = mock_tail_logs.call_args[0][0]
            assert set(call_args) == {'test-echo', 'test-sleep'}
    
    @patch('servly.logs.LogManager._follow_logs')
    @patch('servly.logs.LogManager._display_recent_logs')
    def test_no_follow_option(self, mock_display, mock_follow):
        """TC3.3: 测试不跟随日志的选项（--no-follow）"""
        log_manager = LogManager(self.log_dir)
        
        # 测试不跟随模式显示日志
        log_manager.tail_logs(['test-service'], follow=False, lines=10)
        
        # 验证调用了 _display_recent_logs 而不是 _follow_logs
        mock_display.assert_called_once()
        mock_follow.assert_not_called()
        
        # 验证传递给 _display_recent_logs 的参数
        args, kwargs = mock_display.call_args
        assert len(args) > 0
        assert args[1] == 10  # 验证行数参数
    
    @patch('servly.logs.LogManager._follow_logs')
    @patch('servly.logs.LogManager._display_recent_logs')
    def test_lines_option(self, mock_display, mock_follow):
        """TC3.4: 测试指定显示行数（--lines）"""
        log_manager = LogManager(self.log_dir)
        
        # 测试指定显示 20 行日志
        log_manager.tail_logs(['test-service'], follow=False, lines=20)
        
        # 验证调用 _display_recent_logs 并传递正确的行数
        mock_display.assert_called_once()
        args, kwargs = mock_display.call_args
        assert len(args) > 0
        assert args[1] == 20  # 验证行数参数