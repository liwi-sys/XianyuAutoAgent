import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.config_manager import ConfigManager
from context_manager import ChatContextManager

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from managers.message_processor import MessageProcessor
from XianyuApis import XianyuApis


class TestMessageProcessor:
    """消息处理器单元测试"""

    @pytest.fixture
    def config_manager(self):
        """配置管理器fixture"""
        config = ConfigManager()
        config.set("message.expire_time", 300000)
        config.set("manual_mode.timeout", 3600)
        config.set("message.toggle_keywords", "。")
        return config

    @pytest.fixture
    def xianyu_apis(self):
        """闲鱼API fixture"""
        return Mock(spec=XianyuApis)

    @pytest.fixture
    def context_manager(self):
        """上下文管理器fixture"""
        return Mock(spec=ChatContextManager)

    @pytest.fixture
    def bot(self):
        """机器人fixture"""
        bot = Mock()
        bot.last_intent = None
        return bot

    @pytest.fixture
    def message_processor(self, xianyu_apis, context_manager, bot, config_manager):
        """消息处理器fixture"""
        return MessageProcessor(xianyu_apis, context_manager, bot, config_manager)

    def test_init(self, xianyu_apis, context_manager, bot, config_manager):
        """测试初始化"""
        processor = MessageProcessor(xianyu_apis, context_manager, bot, config_manager)

        assert processor.xianyu_apis == xianyu_apis
        assert processor.context_manager == context_manager
        assert processor.bot == bot
        assert processor.config_manager == config_manager
        assert processor.message_expire_time == 300000
        assert processor.manual_mode_timeout == 3600
        assert processor.toggle_keywords == "。"
        assert isinstance(processor.manual_mode_conversations, set)
        assert isinstance(processor.manual_mode_timestamps, dict)

    def test_is_chat_message(self, message_processor):
        """测试判断聊天消息"""
        # 有效聊天消息
        chat_message = {
            "1": {
                "5": 1234567890,
                "10": {
                    "reminderTitle": "用户",
                    "reminderContent": "你好",
                    "senderUserId": "user123",
                    "reminderUrl": "https://example.com?itemId=123",
                },
                "2": "chat123@goofish",
            }
        }

        assert message_processor.is_chat_message(chat_message)

        # 无效消息
        invalid_messages = [
            None,
            {},
            {"1": {}},
            {"1": {"10": {}}},
            {"1": {"10": {"reminderContent": "test"}}},
            {"1": {"10": {"reminderTitle": "test"}}},
        ]

        for msg in invalid_messages:
            assert not message_processor.is_chat_message(msg)

    def test_is_sync_package(self, message_processor):
        """测试判断同步包消息"""
        # 有效同步包
        sync_message = {"body": {"syncPushPackage": {"data": [{"test": "data"}]}}}

        assert message_processor.is_sync_package(sync_message)

        # 无效消息
        invalid_messages = [
            None,
            {},
            {"body": {}},
            {"body": {"syncPushPackage": {}}},
            {"body": {"syncPushPackage": {"data": []}}},
        ]

        for msg in invalid_messages:
            assert not message_processor.is_sync_package(msg)

    def test_is_typing_status(self, message_processor):
        """测试判断输入状态"""
        # 有效输入状态
        typing_message = {"1": [{"1": "user123@goofish"}]}

        assert message_processor.is_typing_status(typing_message)

        # 无效消息
        invalid_messages = [
            None,
            {},
            {"1": {}},
            {"1": []},
            {"1": [{}]},
            {"1": [{"1": "invalid"}]},
        ]

        for msg in invalid_messages:
            assert not message_processor.is_typing_status(msg)

    def test_is_system_message(self, message_processor):
        """测试判断系统消息"""
        # 有效系统消息
        system_message = {"3": {"needPush": "false"}}

        assert message_processor.is_system_message(system_message)

        # 无效消息
        invalid_messages = [
            None,
            {},
            {"3": {}},
            {"3": {"needPush": "true"}},
            {"3": {"needPush": False}},
        ]

        for msg in invalid_messages:
            assert not message_processor.is_system_message(msg)

    def test_check_toggle_keywords(self, message_processor):
        """测试检查切换关键词"""
        # 有效关键词
        assert message_processor.check_toggle_keywords("。")
        assert message_processor.check_toggle_keywords(" 。 ")
        assert message_processor.check_toggle_keywords("。")

        # 无效关键词
        assert not message_processor.check_toggle_keywords("hello")
        assert not message_processor.check_toggle_keywords("")
        assert not message_processor.check_toggle_keywords("test")

    def test_manual_mode_management(self, message_processor):
        """测试人工接管模式管理"""
        chat_id = "test_chat"

        # 初始状态
        assert not message_processor.is_manual_mode(chat_id)

        # 进入人工模式
        message_processor.enter_manual_mode(chat_id)
        assert message_processor.is_manual_mode(chat_id)
        assert chat_id in message_processor.manual_mode_conversations
        assert chat_id in message_processor.manual_mode_timestamps

        # 退出人工模式
        message_processor.exit_manual_mode(chat_id)
        assert not message_processor.is_manual_mode(chat_id)
        assert chat_id not in message_processor.manual_mode_conversations
        assert chat_id not in message_processor.manual_mode_timestamps

    def test_manual_mode_timeout(self, message_processor):
        """测试人工接管模式超时"""
        chat_id = "test_chat"

        # 设置较短的测试超时时间
        original_timeout = message_processor.manual_mode_timeout
        message_processor.manual_mode_timeout = 1  # 1秒超时

        try:
            # 进入人工模式
            message_processor.enter_manual_mode(chat_id)
            assert message_processor.is_manual_mode(chat_id)

            # 模拟时间流逝
            message_processor.manual_mode_timestamps[chat_id] = time.time() - 2  # 2秒前

            # 检查超时
            assert not message_processor.is_manual_mode(chat_id)
            assert chat_id not in message_processor.manual_mode_conversations
            assert chat_id not in message_processor.manual_mode_timestamps

        finally:
            # 恢复原始超时时间
            message_processor.manual_mode_timeout = original_timeout

    def test_toggle_manual_mode(self, message_processor):
        """测试切换人工接管模式"""
        chat_id = "test_chat"

        # 初始状态
        assert not message_processor.is_manual_mode(chat_id)

        # 切换到人工模式
        mode = message_processor.toggle_manual_mode(chat_id)
        assert mode == "manual"
        assert message_processor.is_manual_mode(chat_id)

        # 切换回自动模式
        mode = message_processor.toggle_manual_mode(chat_id)
        assert mode == "auto"
        assert not message_processor.is_manual_mode(chat_id)

    def test_extract_message_info(self, message_processor):
        """测试提取消息信息"""
        # 有效消息
        message = {
            "1": {
                "5": 1234567890,  # 创建时间
                "10": {
                    "reminderTitle": "测试用户",
                    "reminderContent": "你好，这个商品多少钱？",
                    "senderUserId": "user123",
                    "reminderUrl": "https://example.com?itemId=456&other=param",
                },
                "2": "chat789@goofish",
            }
        }

        info = message_processor.extract_message_info(message)

        assert info is not None
        assert info["send_user_name"] == "测试用户"
        assert info["send_message"] == "你好，这个商品多少钱？"
        assert info["send_user_id"] == "user123"
        assert info["item_id"] == "456"
        assert info["chat_id"] == "chat789"
        assert info["create_time"] == 1234567890

        # 过期消息
        old_message = message.copy()
        old_message["1"]["5"] = time.time() * 1000 - 400000  # 400秒前

        info = message_processor.extract_message_info(old_message)
        assert info is None  # 过期消息应该返回None

        # 缺少商品ID
        no_item_message = message.copy()
        no_item_message["1"]["10"]["reminderUrl"] = "https://example.com?other=param"

        info = message_processor.extract_message_info(no_item_message)
        assert info is None  # 缺少商品ID应该返回None

    def test_process_order_message(self, message_processor):
        """测试处理订单消息"""
        # 等待付款消息
        payment_message = {"1": "user123@goofish", "3": {"redReminder": "等待买家付款"}}

        result = message_processor.process_order_message(payment_message)
        assert result is True

        # 交易关闭消息
        close_message = {"1": "user123@goofish", "3": {"redReminder": "交易关闭"}}

        result = message_processor.process_order_message(close_message)
        assert result is True

        # 等待发货消息
        ship_message = {"1": "user123@goofish", "3": {"redReminder": "等待卖家发货"}}

        result = message_processor.process_order_message(ship_message)
        assert result is True

        # 非订单消息
        non_order_message = {"1": "user123@goofish", "3": {"redReminder": "其他消息"}}

        result = message_processor.process_order_message(non_order_message)
        assert result is False

    def test_get_manual_mode_status(self, message_processor):
        """测试获取人工接管状态"""
        chat_id = "test_chat"

        # 初始状态
        status = message_processor.get_manual_mode_status()
        assert status["manual_conversations"] == []
        assert status["manual_timestamps"] == {}
        assert status["manual_mode_timeout"] == 3600

        # 进入人工模式
        message_processor.enter_manual_mode(chat_id)

        status = message_processor.get_manual_mode_status()
        assert chat_id in status["manual_conversations"]
        assert chat_id in status["manual_timestamps"]
        assert status["manual_mode_timeout"] == 3600

    @pytest.mark.asyncio
    async def test_process_seller_message(self, message_processor):
        """测试处理卖家消息"""
        myid = "seller123"

        # 卖家控制命令
        control_message = {
            "send_user_id": myid,
            "send_message": "。",
            "chat_id": "test_chat",
            "item_id": "123",
        }

        result = await message_processor.process_seller_message(control_message, myid)
        assert result is True
        assert message_processor.is_manual_mode("test_chat")

        # 卖家普通消息
        normal_message = {
            "send_user_id": myid,
            "send_message": "你好，有什么可以帮助你的吗？",
            "chat_id": "test_chat",
            "item_id": "123",
        }

        result = await message_processor.process_seller_message(normal_message, myid)
        assert result is True
        # 验证调用了上下文管理器
        message_processor.context_manager.add_message_by_chat.assert_called()

        # 买家消息
        buyer_message = {
            "send_user_id": "buyer123",
            "send_message": "这个商品多少钱？",
            "chat_id": "test_chat",
            "item_id": "123",
        }

        result = await message_processor.process_seller_message(buyer_message, myid)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_item_info(self, message_processor):
        """测试获取商品信息"""
        item_id = "test_item"

        # 数据库中存在商品信息
        mock_item_info = {"soldPrice": 100, "desc": "测试商品"}
        message_processor.context_manager.get_item_info = Mock(
            return_value=mock_item_info
        )

        result = await message_processor.get_item_info(item_id)
        assert result == mock_item_info
        message_processor.context_manager.get_item_info.assert_called_once_with(item_id)

        # 数据库中不存在商品信息，从API获取
        message_processor.context_manager.get_item_info = Mock(return_value=None)
        api_result = {"data": {"itemDO": {"soldPrice": 200, "desc": "API商品"}}}
        message_processor.xianyu_apis.get_item_info = AsyncMock(return_value=api_result)

        result = await message_processor.get_item_info(item_id)
        assert result == api_result["data"]["itemDO"]
        message_processor.context_manager.save_item_info.assert_called_once_with(
            item_id, api_result["data"]["itemDO"]
        )

        # API获取失败
        message_processor.xianyu_apis.get_item_info = AsyncMock(
            return_value={"error": "API error"}
        )

        result = await message_processor.get_item_info(item_id)
        assert result is None
