import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.config_manager import ConfigManager

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from managers.heartbeat_manager import HeartbeatManager
from managers.websocket_manager import WebSocketManager


class TestHeartbeatManager:
    """心跳管理器单元测试"""

    @pytest.fixture
    def config_manager(self):
        """配置管理器fixture"""
        config = ConfigManager()
        config.set("heartbeat.interval", 10)
        config.set("heartbeat.timeout", 3)
        return config

    @pytest.fixture
    def websocket_manager(self):
        """WebSocket管理器fixture"""
        return Mock(spec=WebSocketManager)

    @pytest.fixture
    def heartbeat_manager(self, websocket_manager, config_manager):
        """心跳管理器fixture"""
        return HeartbeatManager(websocket_manager, config_manager)

    def test_init(self, websocket_manager, config_manager):
        """测试初始化"""
        manager = HeartbeatManager(websocket_manager, config_manager)

        assert manager.websocket_manager == websocket_manager
        assert manager.config_manager == config_manager
        assert manager.heartbeat_interval == 10
        assert manager.heartbeat_timeout == 3
        assert manager.last_heartbeat_time == 0
        assert manager.last_heartbeat_response == 0
        assert manager.heartbeat_task is None

    def test_initialize_times(self, heartbeat_manager):
        """测试初始化时间"""
        heartbeat_manager.initialize_times()

        current_time = time.time()
        assert abs(heartbeat_manager.last_heartbeat_time - current_time) < 0.1
        assert abs(heartbeat_manager.last_heartbeat_response - current_time) < 0.1

    @pytest.mark.asyncio
    async def test_send_heartbeat_success(self, heartbeat_manager):
        """测试发送心跳成功"""
        # 模拟WebSocket管理器发送消息
        heartbeat_manager.websocket_manager.send_message = AsyncMock(return_value=True)

        result = await heartbeat_manager.send_heartbeat()

        assert result is not None  # 返回心跳ID
        heartbeat_manager.websocket_manager.send_message.assert_called_once()

        # 验证心跳时间更新
        assert heartbeat_manager.last_heartbeat_time > 0

    @pytest.mark.asyncio
    async def test_send_heartbeat_failure(self, heartbeat_manager):
        """测试发送心跳失败"""
        # 模拟WebSocket管理器发送消息失败
        heartbeat_manager.websocket_manager.send_message = AsyncMock(return_value=False)

        with pytest.raises(Exception, match="发送心跳包失败"):
            await heartbeat_manager.send_heartbeat()

    def test_handle_heartbeat_response_success(self, heartbeat_manager):
        """测试处理心跳响应成功"""
        message_data = {"headers": {"mid": "test_mid"}, "code": 200}

        result = heartbeat_manager.handle_heartbeat_response(message_data)

        assert result is True
        assert heartbeat_manager.last_heartbeat_response > 0

    def test_handle_heartbeat_response_failure(self, heartbeat_manager):
        """测试处理心跳响应失败"""
        # 测试缺少code字段
        message_data = {"headers": {"mid": "test_mid"}}
        result = heartbeat_manager.handle_heartbeat_response(message_data)
        assert result is False

        # 测试code不是200
        message_data = {"headers": {"mid": "test_mid"}, "code": 500}
        result = heartbeat_manager.handle_heartbeat_response(message_data)
        assert result is False

        # 测试异常情况
        result = heartbeat_manager.handle_heartbeat_response(None)
        assert result is False

    def test_is_healthy(self, heartbeat_manager):
        """测试健康状态检查"""
        # 初始化时间
        heartbeat_manager.initialize_times()

        # 初始状态应该是健康的
        assert heartbeat_manager.is_healthy()

        # 模拟心跳响应超时
        heartbeat_manager.last_heartbeat_response = time.time() - 20  # 20秒前
        assert not heartbeat_manager.is_healthy()

    def test_get_status(self, heartbeat_manager):
        """测试获取状态"""
        # 初始化时间
        heartbeat_manager.initialize_times()

        status = heartbeat_manager.get_status()

        assert "last_heartbeat_time" in status
        assert "last_heartbeat_response" in status
        assert "heartbeat_interval" in status
        assert "heartbeat_timeout" in status
        assert "is_healthy" in status
        assert "time_since_last_response" in status
        assert status["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_heartbeat_loop_normal(self, heartbeat_manager):
        """测试心跳循环正常情况"""
        # 初始化时间
        heartbeat_manager.initialize_times()

        # 模拟WebSocket管理器
        heartbeat_manager.websocket_manager.send_message = AsyncMock(return_value=True)

        # 模拟时间流逝
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                heartbeat_manager.last_heartbeat_time,  # 初始时间
                heartbeat_manager.last_heartbeat_time + 15,  # 需要发送心跳
                heartbeat_manager.last_heartbeat_time + 16,  # 检查超时
                heartbeat_manager.last_heartbeat_time + 20,  # 超时退出
            ]

            # 运行心跳循环（应该会因为超时而退出）
            with pytest.raises(Exception):  # 心跳循环会因为超时而退出
                await heartbeat_manager.heartbeat_loop()

    @pytest.mark.asyncio
    async def test_start_and_stop(self, heartbeat_manager):
        """测试启动和停止"""
        # 初始状态
        assert heartbeat_manager.heartbeat_task is None

        # 启动
        heartbeat_manager.start()
        assert heartbeat_manager.heartbeat_task is not None
        assert not heartbeat_manager.heartbeat_task.done()

        # 停止
        heartbeat_manager.stop()
        assert heartbeat_manager.heartbeat_task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self, heartbeat_manager):
        """测试启动已运行的任务"""
        # 启动任务
        heartbeat_manager.start()
        original_task = heartbeat_manager.heartbeat_task

        # 再次启动
        heartbeat_manager.start()

        # 应该重用现有任务
        assert heartbeat_manager.heartbeat_task == original_task

        # 清理
        heartbeat_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, heartbeat_manager):
        """测试停止未运行的任务"""
        # 停止未运行的任务
        heartbeat_manager.stop()
        assert heartbeat_manager.heartbeat_task is None

    @pytest.mark.asyncio
    async def test_heartbeat_loop_exception(self, heartbeat_manager):
        """测试心跳循环异常处理"""
        # 模拟发送心跳异常
        heartbeat_manager.websocket_manager.send_message = AsyncMock(
            side_effect=Exception("Send error")
        )

        # 初始化时间
        heartbeat_manager.initialize_times()

        # 模拟时间流逝
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                heartbeat_manager.last_heartbeat_time,  # 初始时间
                heartbeat_manager.last_heartbeat_time + 15,  # 需要发送心跳
                heartbeat_manager.last_heartbeat_time + 16,  # 异常后退出
            ]

            # 运行心跳循环（应该会因为异常而退出）
            with pytest.raises(Exception):  # 心跳循环会因为异常而退出
                await heartbeat_manager.heartbeat_loop()

    def test_heartbeat_timing(self, heartbeat_manager):
        """测试心跳时间计算"""
        # 初始化时间
        heartbeat_manager.initialize_times()

        # 测试心跳间隔
        assert heartbeat_manager.heartbeat_interval == 10
        assert heartbeat_manager.heartbeat_timeout == 3

        # 测试超时计算
        current_time = time.time()
        heartbeat_manager.last_heartbeat_response = current_time - 15  # 15秒前

        # 应该超时
        assert (current_time - heartbeat_manager.last_heartbeat_response) > (
            heartbeat_manager.heartbeat_interval + heartbeat_manager.timeout
        )
        assert not heartbeat_manager.is_healthy()
