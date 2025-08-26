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
from core.xianyu_live import XianyuLiveRefactored


class TestXianyuLiveIntegration:
    """闲鱼直播集成测试"""

    @pytest.fixture
    def config_manager(self):
        """配置管理器fixture"""
        # 创建临时配置文件
        config_data = {
            "websocket": {
                "base_url": "wss://test.example.com",
                "headers": {"User-Agent": "Test Agent"},
            },
            "heartbeat": {"interval": 5, "timeout": 2},
            "token": {"refresh_interval": 60, "retry_interval": 10},
            "message": {"expire_time": 60000, "toggle_keywords": "test_toggle"},
            "manual_mode": {"timeout": 1800},
            "llm": {
                "model_name": "test-model",
                "base_url": "https://test-api.example.com",
                "api_key": "test-api-key",
            },
            "database": {"path": ":memory:", "max_history": 50},
            "cookies_str": "test_cookie=value",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_config_path = f.name

        try:
            config_manager = ConfigManager(temp_config_path)
            yield config_manager
        finally:
            os.unlink(temp_config_path)

    @pytest.fixture
    def bot(self):
        """机器人fixture"""
        bot = Mock()
        bot.last_intent = None
        return bot

    @pytest.fixture
    def xianyu_live(self, config_manager):
        """闲鱼直播实例fixture"""
        return XianyuLiveRefactored(config_manager)

    def test_init(self, xianyu_live, config_manager):
        """测试初始化"""
        assert xianyu_live.config_manager == config_manager
        assert xianyu_live.cookies_str == "test_cookie=value"
        assert xianyu_live.device_id is not None
        assert xianyu_live.xianyu_apis is not None
        assert xianyu_live.context_manager is not None
        assert xianyu_live.websocket_manager is not None
        assert xianyu_live.heartbeat_manager is not None
        assert xianyu_live.token_manager is not None
        assert xianyu_live.bot is None
        assert xianyu_live.message_processor is None

    def test_set_bot(self, xianyu_live, bot):
        """测试设置机器人"""
        xianyu_live.set_bot(bot)

        assert xianyu_live.bot == bot
        assert xianyu_live.message_processor is not None
        assert xianyu_live.message_processor.bot == bot

    def test_get_system_status(self, xianyu_live):
        """测试获取系统状态"""
        status = xianyu_live.get_system_status()

        assert "websocket" in status
        assert "heartbeat" in status
        assert "token" in status
        assert "message_processor" in status

        # 检查WebSocket状态
        assert "is_connected" in status["websocket"]
        assert "should_restart" in status["websocket"]

        # 检查心跳状态
        assert "is_healthy" in status["heartbeat"]
        assert "last_heartbeat_time" in status["heartbeat"]

        # 检查Token状态
        assert "has_token" in status["token"]
        assert "is_valid" in status["token"]

        # 检查消息处理器状态
        assert "manual_conversations" in status["message_processor"]
        assert "manual_timestamps" in status["message_processor"]

    @pytest.mark.asyncio
    async def test_initialize_connection(self, xianyu_live):
        """测试初始化连接"""
        # 模拟WebSocket连接成功
        with patch("websockets.connect") as mock_connect:
            mock_websocket = Mock()
            mock_websocket.send = AsyncMock()
            mock_connect.return_value = mock_websocket

            # 模拟Token获取成功
            xianyu_live.token_manager.initialize_token = AsyncMock(
                return_value="test_token"
            )

            result = await xianyu_live.initialize_connection()

            assert result is True
            mock_connect.assert_called_once()
            mock_websocket.send.assert_called()  # 注册消息
            mock_websocket.send.assert_called()  # 同步确认消息

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, xianyu_live):
        """测试初始化连接失败"""
        # 模拟WebSocket连接失败
        with patch("websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="WebSocket连接失败"):
                await xianyu_live.initialize_connection()

    @pytest.mark.asyncio
    async def test_initialize_connection_token_failure(self, xianyu_live):
        """测试初始化连接Token失败"""
        # 模拟WebSocket连接成功
        with patch("websockets.connect") as mock_connect:
            mock_websocket = Mock()
            mock_connect.return_value = mock_websocket

            # 模拟Token获取失败
            xianyu_live.token_manager.initialize_token = AsyncMock(
                side_effect=Exception("Token error")
            )

            with pytest.raises(Exception, match="Token获取失败"):
                await xianyu_live.initialize_connection()

    @pytest.mark.asyncio
    async def test_handle_heartbeat_response(self, xianyu_live):
        """测试处理心跳响应"""
        # 有效心跳响应
        heartbeat_response = {"headers": {"mid": "test_mid"}, "code": 200}

        result = await xianyu_live.handle_heartbeat_response(heartbeat_response)
        assert result is True

        # 无效心跳响应
        invalid_response = {"headers": {"mid": "test_mid"}, "code": 500}

        result = await xianyu_live.handle_heartbeat_response(invalid_response)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_ack(self, xianyu_live):
        """测试发送ACK"""
        # 模拟WebSocket发送成功
        xianyu_live.websocket_manager.send_ack = AsyncMock(return_value=True)

        message_data = {
            "headers": {"mid": "test_mid", "sid": "test_sid", "app-key": "test_key"}
        }

        result = await xianyu_live.send_ack(message_data)
        assert result is True
        xianyu_live.websocket_manager.send_ack.assert_called_once_with(message_data)

    @pytest.mark.asyncio
    async def test_process_message(self, xianyu_live, bot):
        """测试处理消息"""
        # 设置机器人
        xianyu_live.set_bot(bot)

        # 模拟消息处理器处理成功
        xianyu_live.message_processor.process_message = AsyncMock()

        message_data = {"test": "message"}

        await xianyu_live.process_message(message_data)
        xianyu_live.message_processor.process_message.assert_called_once_with(
            message_data, xianyu_live.websocket_manager, xianyu_live.myid
        )

    @pytest.mark.asyncio
    async def test_start_managers(self, xianyu_live):
        """测试启动管理器"""
        # 启动管理器
        await xianyu_live.start_managers()

        # 验证管理器已启动
        assert xianyu_live.heartbeat_manager.heartbeat_task is not None
        assert xianyu_live.token_manager.token_refresh_task is not None

    @pytest.mark.asyncio
    async def test_stop_managers(self, xianyu_live):
        """测试停止管理器"""
        # 启动管理器
        await xianyu_live.start_managers()

        # 停止管理器
        await xianyu_live.stop_managers()

        # 验证管理器已停止
        assert xianyu_live.heartbeat_manager.heartbeat_task is None
        assert xianyu_live.token_manager.token_refresh_task is None

    @pytest.mark.asyncio
    async def test_check_token_restart(self, xianyu_live):
        """测试检查Token重启"""
        # 模拟Token任务已完成并返回需要重启
        mock_task = Mock()
        mock_task.done.return_value = True
        mock_task.result.return_value = True
        xianyu_live.token_manager.token_refresh_task = mock_task

        result = xianyu_live.check_token_restart()
        assert result is True
        assert xianyu_live.websocket_manager.should_restart()

    @pytest.mark.asyncio
    async def test_main_loop_structure(self, xianyu_live):
        """测试主循环结构"""
        # 模拟WebSocket连接
        with patch("websockets.connect") as mock_connect:
            mock_websocket = Mock()
            mock_websocket.send = AsyncMock()
            mock_connect.return_value = mock_websocket

            # 模拟Token初始化
            xianyu_live.token_manager.initialize_token = AsyncMock(
                return_value="test_token"
            )

            # 模拟消息监听
            mock_websocket.__aiter__ = Mock(
                return_value=iter(
                    [
                        '{"headers": {"mid": "test1"}, "code": 200}',  # 心跳响应
                        '{"test": "message"}',  # 普通消息
                    ]
                )
            )

            # 模拟管理器
            xianyu_live.heartbeat_manager.heartbeat_loop = AsyncMock(
                side_effect=Exception("Heartbeat loop ended")
            )
            xianyu_live.token_manager.token_refresh_loop = AsyncMock(
                side_effect=Exception("Token loop ended")
            )

            # 模拟消息处理
            xianyu_live.handle_heartbeat_response = AsyncMock(return_value=False)
            xianyu_live.send_ack = AsyncMock()
            xianyu_live.process_message = AsyncMock()

            # 运行主循环（应该会因为管理器异常而退出）
            with pytest.raises(Exception):
                await xianyu_live.main_loop()

    def test_config_integration(self, xianyu_live, config_manager):
        """测试配置集成"""
        # 验证配置传递
        assert xianyu_live.websocket_manager.config_manager == config_manager
        assert xianyu_live.heartbeat_manager.config_manager == config_manager
        assert xianyu_live.token_manager.config_manager == config_manager

        # 验证配置值
        assert xianyu_live.heartbeat_manager.heartbeat_interval == 5
        assert xianyu_live.token_manager.token_refresh_interval == 60
        assert xianyu_live.message_processor.message_expire_time == 60000

    def test_dependency_injection(self, xianyu_live):
        """测试依赖注入"""
        # 验证所有依赖都已正确注入
        assert xianyu_live.xianyu_apis is not None
        assert xianyu_live.context_manager is not None
        assert xianyu_live.websocket_manager is not None
        assert xianyu_live.heartbeat_manager is not None
        assert xianyu_live.token_manager is not None

        # 验证管理器之间的依赖关系
        assert (
            xianyu_live.heartbeat_manager.websocket_manager
            == xianyu_live.websocket_manager
        )
        assert xianyu_live.token_manager.xianyu_apis == xianyu_live.xianyu_apis

    @pytest.mark.asyncio
    async def test_error_handling(self, xianyu_live):
        """测试错误处理"""
        # 设置机器人
        xianyu_live.set_bot(Mock())

        # 模拟WebSocket连接失败
        with patch("websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            # 应该能够处理连接失败并重试
            with patch("asyncio.sleep") as mock_sleep:
                mock_sleep.return_value = None

                with pytest.raises(Exception):
                    await xianyu_live.main_loop()

                # 验证错误被正确处理
                mock_sleep.assert_called()
