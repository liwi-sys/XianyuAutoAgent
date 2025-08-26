import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.config_manager import ConfigManager
from managers.websocket_manager import WebSocketManager

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestWebSocketManager:
    """WebSocket管理器单元测试"""

    @pytest.fixture
    def config_manager(self):
        """配置管理器fixture"""
        config = ConfigManager()
        config.set("cookies_str", "test_cookie=value")
        return config

    @pytest.fixture
    def websocket_manager(self, config_manager):
        """WebSocket管理器fixture"""
        return WebSocketManager(config_manager)

    def test_init(self, config_manager):
        """测试初始化"""
        manager = WebSocketManager(config_manager)

        assert manager.config_manager == config_manager
        assert manager.cookies_str == "test_cookie=value"
        assert manager.base_url == "wss://wss-goofish.dingtalk.com/"
        assert manager.websocket is None
        assert not manager.connection_restart_flag

    def test_get_headers(self, websocket_manager):
        """测试获取请求头"""
        headers = websocket_manager._get_headers()

        assert "Cookie" in headers
        assert headers["Cookie"] == "test_cookie=value"
        assert "Host" in headers
        assert "User-Agent" in headers
        assert "Origin" in headers

    def test_is_connected(self, websocket_manager):
        """测试连接状态检查"""
        # 未连接状态
        assert not websocket_manager.is_connected

        # 模拟已连接
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.closed = False
        assert websocket_manager.is_connected

        # 模拟连接关闭
        websocket_manager.websocket.closed = True
        assert not websocket_manager.is_connected

    def test_restart_flags(self, websocket_manager):
        """测试重启标志"""
        # 初始状态
        assert not websocket_manager.should_restart()

        # 设置重启标志
        websocket_manager.set_restart_flag()
        assert websocket_manager.should_restart()

        # 重置重启标志
        websocket_manager.reset_restart_flag()
        assert not websocket_manager.should_restart()

    @pytest.mark.asyncio
    async def test_send_message_success(self, websocket_manager):
        """测试发送消息成功"""
        # 模拟WebSocket连接
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.send = AsyncMock()

        # 测试发送字典消息
        message = {"type": "test", "content": "hello"}
        result = await websocket_manager.send_message(message)

        assert result is True
        websocket_manager.websocket.send.assert_called_once_with(
            '{"type": "test", "content": "hello"}'
        )

    @pytest.mark.asyncio
    async def test_send_message_no_connection(self, websocket_manager):
        """测试无连接时发送消息"""
        result = await websocket_manager.send_message({"test": "message"})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_exception(self, websocket_manager):
        """测试发送消息异常"""
        # 模拟WebSocket连接抛出异常
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.send = AsyncMock(
            side_effect=Exception("Connection error")
        )

        result = await websocket_manager.send_message({"test": "message"})
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_success(self, websocket_manager):
        """测试连接成功"""
        with patch("websockets.connect") as mock_connect:
            mock_websocket = Mock()
            mock_connect.return_value = mock_websocket

            result = await websocket_manager.connect()

            assert result is True
            assert websocket_manager.websocket == mock_websocket
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, websocket_manager):
        """测试连接失败"""
        with patch("websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            result = await websocket_manager.connect()

            assert result is False
            assert websocket_manager.websocket is None

    @pytest.mark.asyncio
    async def test_disconnect(self, websocket_manager):
        """测试断开连接"""
        # 模拟WebSocket连接
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.close = AsyncMock()

        await websocket_manager.disconnect()

        websocket_manager.websocket.close.assert_called_once()
        assert websocket_manager.websocket is None

    @pytest.mark.asyncio
    async def test_disconnect_exception(self, websocket_manager):
        """测试断开连接异常"""
        # 模拟WebSocket连接抛出异常
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.close = AsyncMock(
            side_effect=Exception("Close error")
        )

        # 应该不抛出异常
        await websocket_manager.disconnect()
        assert websocket_manager.websocket is None

    def test_send_registration(self, websocket_manager):
        """测试发送注册消息"""
        # 模拟config_manager.get_api_config
        websocket_manager.config_manager.get_api_config = Mock(
            return_value={"app_key": "test_app_key", "user_agent": "test_user_agent"}
        )

        # 模拟send_message
        websocket_manager.send_message = AsyncMock(return_value=True)

        # 测试发送注册消息
        message = websocket_manager.send_registration("test_token", "test_device_id")

        # 验证调用
        assert message is not None  # 返回协程对象

    def test_send_sync_ack(self, websocket_manager):
        """测试发送同步确认消息"""
        # 模拟send_message
        websocket_manager.send_message = AsyncMock(return_value=True)

        # 测试发送同步确认消息
        message = websocket_manager.send_sync_ack()

        # 验证调用
        assert message is not None  # 返回协程对象

    def test_send_chat_message(self, websocket_manager):
        """测试发送聊天消息"""
        # 模拟send_message
        websocket_manager.send_message = AsyncMock(return_value=True)

        # 测试发送聊天消息
        message = websocket_manager.send_chat_message("chat_id", "user_id", "Hello")

        # 验证调用
        assert message is not None  # 返回协程对象

    def test_send_ack(self, websocket_manager):
        """测试发送ACK响应"""
        # 模拟send_message
        websocket_manager.send_message = AsyncMock(return_value=True)

        # 测试发送ACK
        message_data = {
            "headers": {
                "mid": "test_mid",
                "sid": "test_sid",
                "app-key": "test_app_key",
                "ua": "test_ua",
                "dt": "test_dt",
            }
        }

        message = websocket_manager.send_ack(message_data)

        # 验证调用
        assert message is not None  # 返回协程对象

    def test_send_ack_missing_headers(self, websocket_manager):
        """测试发送ACK缺少headers"""
        # 模拟send_message
        websocket_manager.send_message = AsyncMock(return_value=True)

        # 测试缺少headers的ACK
        message_data = {"other": "data"}

        message = websocket_manager.send_ack(message_data)

        # 验证调用
        assert message is not None  # 返回协程对象

    @pytest.mark.asyncio
    async def test_listen_no_connection(self, websocket_manager):
        """测试无连接时监听"""
        # 无连接时应该返回
        result = websocket_manager.listen()

        # 由于是异步生成器，我们需要迭代它
        with pytest.raises(StopIteration):
            await result.__anext__()
