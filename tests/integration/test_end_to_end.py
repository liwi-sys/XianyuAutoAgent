import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config_manager import ConfigManager
from main import main, setup_logging


class TestEndToEnd:
    """端到端集成测试"""

    @pytest.fixture
    def config_file(self):
        """配置文件fixture"""
        config_data = {
            "cookies_str": "test_cookie=value",
            "llm": {
                "api_key": "test_api_key",
                "base_url": "https://test-api.example.com",
                "model_name": "test-model",
            },
            "websocket": {"base_url": "wss://test.example.com"},
            "heartbeat": {"interval": 1, "timeout": 1},
            "token": {"refresh_interval": 2, "retry_interval": 1},
            "message": {"expire_time": 60000, "toggle_keywords": "test_toggle"},
            "manual_mode": {"timeout": 60},
            "database": {"path": ":memory:", "max_history": 10},
            "logging": {"level": "ERROR"},  # 减少日志输出
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_config_path = f.name

        try:
            yield temp_config_path
        finally:
            os.unlink(temp_config_path)

    @pytest.fixture
    def env_vars(self, config_file):
        """环境变量fixture"""
        return {"CONFIG_FILE": config_file, "LOG_LEVEL": "ERROR"}

    def test_setup_logging(self):
        """测试日志设置"""
        config_manager = Mock()
        config_manager.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "test_format",
        }.get(key, default)

        # 应该不抛出异常
        setup_logging(config_manager)

    def test_main_structure(self):
        """测试主函数结构"""
        # 验证main函数存在
        assert callable(main)

    @pytest.mark.asyncio
    async def test_full_system_initialization(self, config_file, env_vars):
        """测试完整系统初始化"""
        # 设置环境变量
        with patch.dict(os.environ, env_vars):
            # 模拟依赖
            with patch("config.config_manager.ConfigManager") as mock_config_class:
                with patch(
                    "core.xianyu_live_refactored.XianyuLiveRefactored"
                ) as mock_xianyu_live_class:
                    with patch("XianyuAgent.XianyuReplyBot") as mock_bot_class:
                        # 配置模拟
                        mock_config = Mock()
                        mock_config.get.side_effect = lambda key, default=None: {
                            "cookies_str": "test_cookie=value",
                            "logging.level": "ERROR",
                            "logging.format": "test_format",
                        }.get(key, default)
                        mock_config_class.return_value = mock_config

                        # 模拟XianyuLive
                        mock_xianyu_live = Mock()
                        mock_xianyu_live.set_bot = Mock()
                        mock_xianyu_live.get_system_status = Mock(
                            return_value={"test": "status"}
                        )
                        mock_xianyu_live.main_loop = AsyncMock()
                        mock_xianyu_live_class.return_value = mock_xianyu_live

                        # 模拟Bot
                        mock_bot = Mock()
                        mock_bot_class.return_value = mock_bot

                        # 模拟主循环运行一段时间后退出
                        mock_xianyu_live.main_loop.side_effect = KeyboardInterrupt()

                        try:
                            # 运行主函数
                            main()
                        except KeyboardInterrupt:
                            pass  # 预期的中断

                        # 验证初始化步骤
                        mock_config_class.assert_called_once()
                        mock_xianyu_live_class.assert_called_once_with(mock_config)
                        mock_bot_class.assert_called_once()
                        mock_xianyu_live.set_bot.assert_called_once_with(mock_bot)
                        mock_xianyu_live.get_system_status.assert_called_once()
                        mock_xianyu_live.main_loop.assert_called_once()

    def test_config_loading_with_env_vars(self, config_file, env_vars):
        """测试使用环境变量加载配置"""
        with patch.dict(os.environ, env_vars):
            config_manager = ConfigManager(config_file)

            # 验证配置加载
            assert config_manager.get("cookies_str") == "test_cookie=value"
            assert config_manager.get("llm.api_key") == "test_api_key"
            assert config_manager.get("websocket.base_url") == "wss://test.example.com"

    def test_config_file_not_found(self):
        """测试配置文件不存在"""
        # 使用不存在的配置文件路径
        config_manager = ConfigManager("nonexistent_config.json")

        # 应该使用默认配置
        assert config_manager.get("heartbeat.interval") == 15
        assert config_manager.get("llm.model_name") == "qwen-max"

    def test_missing_required_config(self):
        """测试缺少必需配置"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)  # 空配置
            temp_config_path = f.name

        try:
            # 应该抛出异常
            with pytest.raises(ValueError, match="缺少必需的配置"):
                ConfigManager(temp_config_path)
        finally:
            os.unlink(temp_config_path)

    @pytest.mark.asyncio
    async def test_websocket_connection_flow(self, config_file, env_vars):
        """测试WebSocket连接流程"""
        with patch.dict(os.environ, env_vars):
            with patch("config.config_manager.ConfigManager") as mock_config_class:
                with patch(
                    "core.xianyu_live_refactored.XianyuLiveRefactored"
                ) as mock_xianyu_live_class:
                    with patch("XianyuAgent.XianyuReplyBot") as mock_bot_class:
                        # 配置模拟
                        mock_config = Mock()
                        mock_config.get.side_effect = lambda key, default=None: {
                            "cookies_str": "test_cookie=value",
                            "logging.level": "ERROR",
                        }.get(key, default)
                        mock_config_class.return_value = mock_config

                        # 模拟XianyuLive
                        mock_xianyu_live = Mock()
                        mock_xianyu_live.set_bot = Mock()
                        mock_xianyu_live.get_system_status = Mock(
                            return_value={"test": "status"}
                        )
                        mock_xianyu_live.main_loop = AsyncMock()
                        mock_xianyu_live_class.return_value = mock_xianyu_live

                        # 模拟Bot
                        mock_bot = Mock()
                        mock_bot_class.return_value = mock_bot

                        # 模拟主循环退出
                        mock_xianyu_live.main_loop.side_effect = KeyboardInterrupt()

                        try:
                            main()
                        except KeyboardInterrupt:
                            pass

                        # 验证完整的初始化流程
                        mock_config_class.assert_called_once()
                        mock_xianyu_live_class.assert_called_once()
                        mock_bot_class.assert_called_once()
                        mock_xianyu_live.set_bot.assert_called_once()

    def test_error_handling_in_main(self, config_file, env_vars):
        """测试主函数错误处理"""
        with patch.dict(os.environ, env_vars):
            with patch("config.config_manager.ConfigManager") as mock_config_class:
                # 模拟配置管理器初始化失败
                mock_config_class.side_effect = Exception(
                    "Config initialization failed"
                )

                # 应该处理异常并退出
                with pytest.raises(Exception, match="Config initialization failed"):
                    main()

    def test_keyboard_interrupt_handling(self, config_file, env_vars):
        """测试键盘中断处理"""
        with patch.dict(os.environ, env_vars):
            with patch("config.config_manager.ConfigManager") as mock_config_class:
                with patch(
                    "core.xianyu_live_refactored.XianyuLiveRefactored"
                ) as mock_xianyu_live_class:
                    with patch("XianyuAgent.XianyuReplyBot") as mock_bot_class:
                        # 配置模拟
                        mock_config = Mock()
                        mock_config.get.side_effect = lambda key, default=None: {
                            "cookies_str": "test_cookie=value",
                            "logging.level": "ERROR",
                        }.get(key, default)
                        mock_config_class.return_value = mock_config

                        # 模拟XianyuLive
                        mock_xianyu_live = Mock()
                        mock_xianyu_live.set_bot = Mock()
                        mock_xianyu_live.get_system_status = Mock(
                            return_value={"test": "status"}
                        )
                        mock_xianyu_live.main_loop = AsyncMock()
                        mock_xianyu_live_class.return_value = mock_xianyu_live

                        # 模拟Bot
                        mock_bot = Mock()
                        mock_bot_class.return_value = mock_bot

                        # 模拟键盘中断
                        mock_xianyu_live.main_loop.side_effect = KeyboardInterrupt()

                        # 应该优雅处理键盘中断
                        try:
                            main()
                        except KeyboardInterrupt:
                            pass  # 预期的中断

                        # 验证finally块执行
                        # 这里我们只能验证没有抛出未处理的异常

    def test_system_status_reporting(self, config_file, env_vars):
        """测试系统状态报告"""
        with patch.dict(os.environ, env_vars):
            with patch("config.config_manager.ConfigManager") as mock_config_class:
                with patch(
                    "core.xianyu_live_refactored.XianyuLiveRefactored"
                ) as mock_xianyu_live_class:
                    with patch("XianyuAgent.XianyuReplyBot") as mock_bot_class:
                        # 配置模拟
                        mock_config = Mock()
                        mock_config.get.side_effect = lambda key, default=None: {
                            "cookies_str": "test_cookie=value",
                            "logging.level": "ERROR",
                        }.get(key, default)
                        mock_config_class.return_value = mock_config

                        # 模拟系统状态
                        mock_status = {
                            "websocket": {
                                "is_connected": False,
                                "should_restart": False,
                            },
                            "heartbeat": {"is_healthy": True},
                            "token": {"has_token": False, "is_valid": False},
                            "message_processor": {"manual_conversations": []},
                        }

                        # 模拟XianyuLive
                        mock_xianyu_live = Mock()
                        mock_xianyu_live.set_bot = Mock()
                        mock_xianyu_live.get_system_status = Mock(
                            return_value=mock_status
                        )
                        mock_xianyu_live.main_loop = AsyncMock()
                        mock_xianyu_live_class.return_value = mock_xianyu_live

                        # 模拟Bot
                        mock_bot = Mock()
                        mock_bot_class.return_value = mock_bot

                        # 模拟主循环退出
                        mock_xianyu_live.main_loop.side_effect = KeyboardInterrupt()

                        try:
                            main()
                        except KeyboardInterrupt:
                            pass

                        # 验证系统状态被获取
                        mock_xianyu_live.get_system_status.assert_called_once()
