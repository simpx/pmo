"""
测试CLI接口功能。
"""
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from pmo.cli import (
    setup_arg_parser, main, handle_start, handle_stop, handle_restart,
    handle_log, handle_flush, handle_list, resolve_service_id, resolve_multiple_services
)
from pmo.service import ServiceManager
from pmo.logs import LogManager

class TestCLIInterface:
    """测试命令行接口功能 (UT-CLI-001 - UT-CLI-010)"""
    
    def test_parse_valid_command_arguments(self):
        """UT-CLI-001: 解析有效的命令行参数"""
        # 测试不同的命令参数解析
        test_cases = [
            # 基本命令
            (["pmo.py", "ls"], "ls"),
            # 启动命令
            (["pmo.py", "start", "service1"], "start"),
            # 停止命令
            (["pmo.py", "stop", "all"], "stop"),
            # 配置文件参数
            (["pmo.py", "-f", "custom.yml", "ls"], "ls"),
            # 带多个服务的参数
            (["pmo.py", "restart", "service1", "service2"], "restart"),
            # 日志命令带参数
            (["pmo.py", "log", "service1", "--lines", "50"], "log"),
            # 刷新日志命令
            (["pmo.py", "flush", "all"], "flush"),
        ]
        
        parser = setup_arg_parser()
        
        for cmd_args, expected_command in test_cases:
            # 保存原始参数
            old_argv = sys.argv.copy()
            try:
                # 设置命令参数
                sys.argv = cmd_args
                args = parser.parse_args(cmd_args[1:])
                
                # 验证命令正确解析
                assert args.command == expected_command
                
                # 验证其他参数
                if expected_command == "start" and len(cmd_args) > 2:
                    assert args.service == ["service1"]
                elif expected_command == "log" and "--lines" in cmd_args:
                    assert args.lines == 50
                elif "-f" in cmd_args:
                    assert args.config == "custom.yml"
            finally:
                # 恢复原始参数
                sys.argv = old_argv
    
    def test_handle_missing_subcommand(self):
        """UT-CLI-002: 处理缺少子命令的情况"""
        parser = setup_arg_parser()
        
        # 保存原始参数
        old_argv = sys.argv.copy()
        try:
            # 设置无子命令参数
            test_args = ["pmo.py"]
            sys.argv = test_args
            
            with patch('sys.stdout'), patch('sys.stderr'):
                # 解析参数 - 应该没有命令
                args = parser.parse_args([])
                
                # 验证未设置命令
                assert not hasattr(args, "command") or args.command is None
        finally:
            # 恢复原始参数
            sys.argv = old_argv
        
        # 测试main函数在无命令时显示帮助
        with patch('sys.stdout'), patch('sys.stderr'), \
             patch('pmo.cli.setup_arg_parser') as mock_parser:
             
            # 模拟解析器和参数
            mock_parser.return_value = parser
            mock_args = MagicMock()
            mock_args.command = None
            parser.parse_args = MagicMock(return_value=mock_args)
            
            # 运行main函数
            result = main()
            
            # 验证返回码为错误
            assert result == 1
    
    def test_list_command(self, temp_dir, basic_config_file):
        """UT-CLI-003: 测试列表命令"""
        # 模拟服务管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls:
            # 创建模拟的ServiceManager实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            
            # 设置服务名称和运行状态
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            mock_manager.get_running_services.return_value = ["service1"]
            mock_manager.is_running.side_effect = lambda name: name == "service1"
            mock_manager.get_service_pid.side_effect = lambda name: 12345 if name == "service1" else None
            mock_manager.get_uptime.return_value = 3600  # 1小时
            mock_manager.format_uptime.return_value = "1h 0m"
            mock_manager.get_process_stats.return_value = {
                "cpu_percent": 5.0,
                "memory_mb": 100,
                "memory_percent": 1.0,
                "gpu_memory": None,
                "gpu_id": None
            }
            mock_manager.format_cpu_percent.return_value = "5.0%"
            mock_manager.format_memory.return_value = "100mb"
            mock_manager.get_restarts_count.return_value = 0
            
            # 模拟print_service_table函数
            with patch('pmo.cli.print_service_table') as mock_table:
                # 执行列表命令
                result = handle_list(mock_manager)
                
                # 验证服务表显示被调用
                mock_table.assert_called_once()
                
                # 检查传递给表的数据
                services_data = mock_table.call_args[0][0]
                assert len(services_data) == 2
                
                # 验证服务数据正确
                running_service = next(s for s in services_data if s["name"] == "service1")
                assert running_service["status"] == "running"
                assert running_service["uptime"] == "1h 0m"
                assert running_service["cpu"] == "5.0%"
                assert running_service["memory"] == "100mb"
                
                # 验证结果为成功
                assert result is True
    
    def test_start_command(self, temp_dir, basic_config_file):
        """UT-CLI-004: 测试启动命令"""
        # 模拟服务管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls:
            # 创建模拟实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            
            # 设置服务列表
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            
            # 设置start方法行为
            mock_manager.start.return_value = True
            
            # 设置服务解析行为
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1", "service2"]) as mock_resolve:
                # 执行启动命令
                result = handle_start(mock_manager, ["service1", "service2"])
                
                # 验证服务解析被正确调用
                mock_resolve.assert_called_once_with(mock_manager, ["service1", "service2"])
                
                # 验证启动方法被分别调用
                assert mock_manager.start.call_count == 2
                mock_manager.start.assert_has_calls([
                    call("service1", dry_run=False),
                    call("service2", dry_run=False)
                ])
                
                # 验证返回成功
                assert result is True
                
            # 测试dry_run参数
            mock_manager.start.reset_mock()
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1"]) as mock_resolve:
                # 执行带dry_run的启动命令
                result = handle_start(mock_manager, ["service1"], dry_run=True)
                
                # 验证启动方法被调用且传递了dry_run参数
                mock_manager.start.assert_called_once_with("service1", dry_run=True)
    
    def test_stop_command(self, temp_dir, basic_config_file):
        """UT-CLI-005: 测试停止命令"""
        # 模拟服务管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls:
            # 创建模拟实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            
            # 设置服务列表
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            mock_manager.get_running_services.return_value = ["service1", "service2"]
            mock_manager.is_running.return_value = True
            
            # 设置stop方法行为
            mock_manager.stop.return_value = True
            
            # 测试停止特定服务
            with patch('pmo.cli.resolve_service_id', side_effect=lambda _, name: name):
                # 执行停止命令
                result = handle_stop(mock_manager, ["service1"])
                
                # 验证停止方法被调用
                mock_manager.stop.assert_called_once_with("service1")
                
                # 验证返回成功
                assert result is True
            
            # 测试停止所有服务
            mock_manager.stop.reset_mock()
            result = handle_stop(mock_manager, ["all"])
            
            # 验证为所有运行的服务调用了停止方法
            assert mock_manager.stop.call_count == 2
            mock_manager.stop.assert_has_calls([
                call("service1"),
                call("service2")
            ])
            
            # 验证返回成功
            assert result is True
    
    def test_restart_command(self, temp_dir, basic_config_file):
        """UT-CLI-006: 测试重启命令"""
        # 模拟服务管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls:
            # 创建模拟实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            
            # 设置服务列表
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            
            # 设置restart方法行为
            mock_manager.restart.return_value = True
            
            # 设置服务解析行为
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1", "service2"]) as mock_resolve:
                # 执行重启命令
                result = handle_restart(mock_manager, ["service1", "service2"])
                
                # 验证服务解析被正确调用
                mock_resolve.assert_called_once_with(mock_manager, ["service1", "service2"])
                
                # 验证重启方法被分别调用
                assert mock_manager.restart.call_count == 2
                mock_manager.restart.assert_has_calls([
                    call("service1"),
                    call("service2")
                ])
                
                # 验证返回成功
                assert result is True
                
            # 测试重启所有服务
            mock_manager.restart.reset_mock()
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1", "service2"]) as mock_resolve:
                # 执行重启所有命令
                result = handle_restart(mock_manager, ["all"])
                
                # 验证解析为所有服务
                mock_resolve.assert_called_once_with(mock_manager, ["all"])
                
                # 验证重启方法被分别调用
                assert mock_manager.restart.call_count == 2
    
    def test_log_command(self, temp_dir, basic_config_file):
        """UT-CLI-007: 测试日志命令"""
        # 模拟服务管理器和日志管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls, \
             patch('pmo.cli.LogManager') as mock_log_manager_cls:
            
            # 创建模拟实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            mock_log_manager = MagicMock()
            mock_log_manager_cls.return_value = mock_log_manager
            
            # 设置服务列表
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            
            # 创建模拟参数
            args = MagicMock()
            args.service = ["service1"]
            args.no_follow = False
            args.lines = 20
            
            # 设置服务解析行为
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1"]) as mock_resolve:
                # 执行日志命令
                result = handle_log(mock_manager, mock_log_manager, args)
                
                # 验证服务解析被正确调用
                mock_resolve.assert_called_once_with(mock_manager, ["service1"])
                
                # 验证日志查看方法被调用
                # 使用灵活断言，只检查关心的参数
                mock_log_manager.tail_logs.assert_called_once()
                margs, mkwargs = mock_log_manager.tail_logs.call_args
                assert margs[0] == ["service1"]
                assert mkwargs.get('follow') is True
                assert mkwargs.get('lines') == 20
                
                # 验证返回成功
                assert result is True
                
            # 测试不跟随模式
            args.no_follow = True
            mock_log_manager.tail_logs.reset_mock()
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1"]) as mock_resolve:
                # 执行日志命令
                result = handle_log(mock_manager, mock_log_manager, args)
                
                # 验证日志查看方法被调用且follow=False
                # 同样使用灵活断言方式
                mock_log_manager.tail_logs.assert_called_once()
                margs, mkwargs = mock_log_manager.tail_logs.call_args
                assert margs[0] == ["service1"]
                assert mkwargs.get('follow') is False
                assert mkwargs.get('lines') == 20
    
    def test_flush_command(self, temp_dir, basic_config_file):
        """UT-CLI-008: 测试刷新日志命令"""
        # 模拟服务管理器和日志管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls, \
             patch('pmo.cli.LogManager') as mock_log_manager_cls:
            
            # 创建模拟实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            mock_log_manager = MagicMock()
            mock_log_manager_cls.return_value = mock_log_manager
            
            # 设置服务列表
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            mock_manager.get_running_services.return_value = ["service1"]
            
            # 设置flush_logs方法行为
            mock_log_manager.flush_logs.return_value = {
                "service1": {"deleted": 0, "cleared": 2},
                "service2": {"deleted": 2, "cleared": 0}
            }
            
            # 设置服务解析行为
            with patch('pmo.cli.resolve_multiple_services', 
                       return_value=["service1", "service2"]) as mock_resolve:
                # 执行刷新命令
                result = handle_flush(mock_manager, mock_log_manager, ["service1", "service2"])
                
                # 验证服务解析被正确调用
                mock_resolve.assert_called_once_with(mock_manager, ["service1", "service2"])
                
                # 验证flush_logs方法被调用
                mock_log_manager.flush_logs.assert_called_once_with(
                    ["service1", "service2"],
                    running_services=["service1"]
                )
                
                # 验证返回成功
                assert result is True
                
            # 测试刷新所有日志
            mock_log_manager.flush_logs.reset_mock()
            # 返回刷新所有日志的结果
            mock_log_manager.flush_logs.return_value = {
                "deleted": 2,
                "cleared": 1
            }
            
            # 执行刷新所有命令
            result = handle_flush(mock_manager, mock_log_manager, ["all"])
            
            # 验证flush_logs方法被调用
            mock_log_manager.flush_logs.assert_called_once_with(
                running_services=["service1"]
            )
    
    def test_handle_custom_config_path(self, temp_dir):
        """UT-CLI-009: 处理自定义配置路径"""
        # 创建自定义配置文件
        custom_config_path = Path(temp_dir) / "custom.yml"
        with open(custom_config_path, 'w') as f:
            f.write("service1: echo 1")
        
        # 模拟main函数中的参数解析
        with patch('sys.argv', ['pmo.py', '-f', str(custom_config_path), 'ls']), \
             patch('pmo.cli.handle_list', return_value=True) as mock_handle_list, \
             patch('pmo.cli.LogManager'):
            
            # 运行main函数
            result = main()
            
            # 验证ServiceManager使用了正确的配置路径
            mock_handle_list.assert_called_once()
            service_manager = mock_handle_list.call_args[0][0]
            assert service_manager.config_path == str(custom_config_path)
            
            # 验证返回码为成功
            assert result == 0
    
    def test_handle_non_existent_service(self, temp_dir, basic_config_file):
        """UT-CLI-010: 处理不存在的服务"""
        # 模拟服务管理器
        with patch('pmo.cli.ServiceManager') as mock_service_manager_cls:
            # 创建模拟实例
            mock_manager = MagicMock()
            mock_service_manager_cls.return_value = mock_manager
            
            # 设置服务列表
            mock_manager.get_service_names.return_value = ["service1", "service2"]
            
            # 测试解析无效的服务ID
            invalid_id = "999"
            with patch('pmo.cli.print_error') as mock_print_error:
                result = resolve_service_id(mock_manager, invalid_id)
                
                # 验证返回None且显示错误
                assert result is None
                mock_print_error.assert_called_once()
                assert "Invalid service ID" in str(mock_print_error.call_args)
            
            # 测试解析无效的服务名
            invalid_name = "non-existent-service"
            with patch('pmo.cli.print_error') as mock_print_error:
                result = resolve_service_id(mock_manager, invalid_name)
                
                # 验证返回None且显示错误
                assert result is None
                mock_print_error.assert_called_once()
                assert "Service not found" in str(mock_print_error.call_args)
            
            # 测试启动不存在的服务
            with patch('pmo.cli.resolve_multiple_services', return_value=[]), \
                 patch('pmo.cli.print_warning') as mock_print_warning:
                # 执行启动命令
                result = handle_start(mock_manager, ["non-existent-service"])
                
                # 验证显示警告且返回失败
                mock_print_warning.assert_called_once()
                assert "No valid services specified" in str(mock_print_warning.call_args)
                assert result is False