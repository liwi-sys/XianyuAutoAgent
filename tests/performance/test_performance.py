import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config_manager import ConfigManager
from managers.heartbeat_manager import HeartbeatManager
from managers.message_processor import MessageProcessor
from managers.token_manager import TokenManager
from managers.websocket_manager import WebSocketManager


class TestPerformance:
    """性能测试"""

    @pytest.fixture
    def config_manager(self):
        """配置管理器fixture"""
        config_data = {
            "cookies_str": "test_cookie=value",
            "heartbeat": {"interval": 1, "timeout": 1},
            "token": {"refresh_interval": 2, "retry_interval": 1},
            "message": {"expire_time": 60000, "toggle_keywords": "。"},
            "manual_mode": {"timeout": 60},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_config_path = f.name

        try:
            return ConfigManager(temp_config_path)
        finally:
            os.unlink(temp_config_path)

    @pytest.mark.performance
    def test_config_manager_performance(self, config_manager):
        """测试配置管理器性能"""
        # 测试大量配置读取操作
        start_time = time.time()

        for _ in range(1000):
            config_manager.get("heartbeat.interval")
            config_manager.get("llm.model_name")
            config_manager.get("message.expire_time")
            config_manager.get("websocket.base_url")
            config_manager.get("token.refresh_interval")

        end_time = time.time()
        execution_time = end_time - start_time

        # 1000次读取操作应该在1秒内完成
        assert (
            execution_time < 1.0
        ), f"配置读取性能测试失败: {execution_time:.3f}s > 1.0s"

        print(f"配置管理器性能: {execution_time:.3f}s (1000次读取)")

    @pytest.mark.performance
    def test_config_manager_set_performance(self, config_manager):
        """测试配置设置性能"""
        # 测试大量配置设置操作
        start_time = time.time()

        for i in range(1000):
            config_manager.set(f"test.key.{i}", f"value_{i}")
            config_manager.get(f"test.key.{i}")

        end_time = time.time()
        execution_time = end_time - start_time

        # 1000次设置和读取操作应该在2秒内完成
        assert (
            execution_time < 2.0
        ), f"配置设置性能测试失败: {execution_time:.3f}s > 2.0s"

        print(f"配置设置性能: {execution_time:.3f}s (1000次设置和读取)")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_websocket_manager_performance(self, config_manager):
        """测试WebSocket管理器性能"""
        websocket_manager = WebSocketManager(config_manager)

        # 模拟WebSocket连接
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.send = AsyncMock()

        # 测试大量消息发送操作
        start_time = time.time()

        messages = [{"type": "test", "id": i} for i in range(100)]

        for message in messages:
            await websocket_manager.send_message(message)

        end_time = time.time()
        execution_time = end_time - start_time

        # 100条消息发送应该在1秒内完成
        assert (
            execution_time < 1.0
        ), f"WebSocket消息发送性能测试失败: {execution_time:.3f}s > 1.0s"

        print(f"WebSocket消息发送性能: {execution_time:.3f}s (100条消息)")

    @pytest.mark.performance
    def test_heartbeat_manager_performance(self, config_manager):
        """测试心跳管理器性能"""
        websocket_manager = Mock()
        heartbeat_manager = HeartbeatManager(websocket_manager, config_manager)

        # 测试大量心跳响应处理
        start_time = time.time()

        responses = [{"headers": {"mid": f"mid_{i}"}, "code": 200} for i in range(1000)]

        for response in responses:
            heartbeat_manager.handle_heartbeat_response(response)

        end_time = time.time()
        execution_time = end_time - start_time

        # 1000次心跳响应处理应该在1秒内完成
        assert (
            execution_time < 1.0
        ), f"心跳响应处理性能测试失败: {execution_time:.3f}s > 1.0s"

        print(f"心跳响应处理性能: {execution_time:.3f}s (1000次响应)")

    @pytest.mark.performance
    def test_token_manager_performance(self, config_manager):
        """测试Token管理器性能"""
        xianyu_apis = Mock()
        token_manager = TokenManager(xianyu_apis, "test_device", config_manager)

        # 测试大量Token有效性检查
        start_time = time.time()

        # 设置Token
        token_manager.current_token = "test_token"
        token_manager.last_token_refresh_time = time.time()

        for _ in range(1000):
            token_manager.is_token_valid()
            token_manager.get_current_token()

        end_time = time.time()
        execution_time = end_time - start_time

        # 1000次Token检查应该在1秒内完成
        assert (
            execution_time < 1.0
        ), f"Token管理器性能测试失败: {execution_time:.3f}s > 1.0s"

        print(f"Token管理器性能: {execution_time:.3f}s (1000次检查)")

    @pytest.mark.performance
    def test_message_processor_performance(self, config_manager):
        """测试消息处理器性能"""
        xianyu_apis = Mock()
        context_manager = Mock()
        bot = Mock()
        message_processor = MessageProcessor(
            xianyu_apis, context_manager, bot, config_manager
        )

        # 测试大量消息类型判断
        start_time = time.time()

        chat_messages = [
            {
                "1": {
                    "5": 1234567890 + i,
                    "10": {
                        "reminderTitle": f"用户{i}",
                        "reminderContent": f"消息{i}",
                        "senderUserId": f"user{i}",
                        "reminderUrl": f"https://example.com?itemId={i}",
                    },
                    "2": f"chat{i}@goofish",
                }
            }
            for i in range(100)
        ]

        for message in chat_messages:
            message_processor.is_chat_message(message)
            message_processor.is_sync_package(message)
            message_processor.is_typing_status(message)
            message_processor.is_system_message(message)

        end_time = time.time()
        execution_time = end_time - start_time

        # 100条消息的类型判断应该在1秒内完成
        assert (
            execution_time < 1.0
        ), f"消息处理器性能测试失败: {execution_time:.3f}s > 1.0s"

        print(f"消息处理器性能: {execution_time:.3f}s (100条消息，4种类型判断)")

    @pytest.mark.performance
    def test_manual_mode_performance(self, config_manager):
        """测试人工接管模式性能"""
        xianyu_apis = Mock()
        context_manager = Mock()
        bot = Mock()
        message_processor = MessageProcessor(
            xianyu_apis, context_manager, bot, config_manager
        )

        # 测试大量人工接管模式操作
        start_time = time.time()

        chat_ids = [f"chat_{i}" for i in range(100)]

        # 进入人工模式
        for chat_id in chat_ids:
            message_processor.enter_manual_mode(chat_id)

        # 检查人工模式状态
        for chat_id in chat_ids:
            message_processor.is_manual_mode(chat_id)

        # 退出人工模式
        for chat_id in chat_ids:
            message_processor.exit_manual_mode(chat_id)

        end_time = time.time()
        execution_time = end_time - start_time

        # 100个会话的人工接管操作应该在1秒内完成
        assert (
            execution_time < 1.0
        ), f"人工接管模式性能测试失败: {execution_time:.3f}s > 1.0s"

        print(f"人工接管模式性能: {execution_time:.3f}s (100个会话)")

    @pytest.mark.performance
    def test_memory_usage(self, config_manager):
        """测试内存使用"""
        import gc

        import psutil

        # 获取初始内存使用
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 创建大量对象
        managers = []
        for i in range(100):
            websocket_manager = WebSocketManager(config_manager)
            heartbeat_manager = HeartbeatManager(websocket_manager, config_manager)
            token_manager = TokenManager(Mock(), f"device_{i}", config_manager)
            message_processor = MessageProcessor(Mock(), Mock(), Mock(), config_manager)

            managers.append(
                (websocket_manager, heartbeat_manager, token_manager, message_processor)
            )

        # 强制垃圾回收
        gc.collect()

        # 获取最终内存使用
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # 内存增加应该在50MB以内
        assert memory_increase < 50, f"内存使用测试失败: {memory_increase:.2f}MB > 50MB"

        print(
            f"内存使用: {initial_memory:.2f}MB -> {final_memory:.2f}MB (+{memory_increase:.2f}MB)"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, config_manager):
        """测试并发操作性能"""
        websocket_manager = WebSocketManager(config_manager)
        websocket_manager.websocket = Mock()
        websocket_manager.websocket.send = AsyncMock()

        # 测试并发消息发送
        start_time = time.time()

        async def send_messages(count):
            for i in range(count):
                await websocket_manager.send_message({"id": i, "data": f"message_{i}"})

        # 创建10个并发任务，每个发送10条消息
        tasks = [send_messages(10) for _ in range(10)]
        await asyncio.gather(*tasks)

        end_time = time.time()
        execution_time = end_time - start_time

        # 100条并发消息发送应该在2秒内完成
        assert (
            execution_time < 2.0
        ), f"并发操作性能测试失败: {execution_time:.3f}s > 2.0s"

        print(f"并发操作性能: {execution_time:.3f}s (10个并发任务，每个10条消息)")

    @pytest.mark.performance
    def test_config_file_loading_performance(self):
        """测试配置文件加载性能"""
        # 创建大型配置文件
        large_config = {"test_data": {f"key_{i}": f"value_{i}" for i in range(1000)}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(large_config, f)
            temp_config_path = f.name

        try:
            # 测试配置文件加载性能
            start_time = time.time()

            for _ in range(100):
                config_manager = ConfigManager(temp_config_path)
                config_manager.get("test_data.key_0")
                config_manager.get("test_data.key_999")

            end_time = time.time()
            execution_time = end_time - start_time

            # 100次配置文件加载应该在5秒内完成
            assert (
                execution_time < 5.0
            ), f"配置文件加载性能测试失败: {execution_time:.3f}s > 5.0s"

            print(f"配置文件加载性能: {execution_time:.3f}s (100次加载，1000个配置项)")

        finally:
            os.unlink(temp_config_path)
