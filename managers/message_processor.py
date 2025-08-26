import asyncio
import base64
import json
import re
import time

from loguru import logger

from utils.xianyu_utils import decrypt
from .message_batcher import MessageBatcher, IntentAnalyzer


class MessageProcessor:
    """消息处理器"""

    def __init__(self, xianyu_apis, context_manager, bot, config_manager):
        self.xianyu_apis = xianyu_apis
        self.context_manager = context_manager
        self.bot = bot
        self.config_manager = config_manager
        self.message_expire_time = config_manager.get("message.expire_time", 300000)

        # 人工接管相关配置
        self.manual_mode_conversations = set()  # 存储处于人工接管模式的会话ID
        self.manual_mode_timeout = config_manager.get("manual_mode.timeout", 3600)
        self.manual_mode_timestamps = {}  # 记录进入人工模式的时间
        self.toggle_keywords = config_manager.get("message.toggle_keywords", "。")
        
        # 性能优化组件
        self.message_batcher = MessageBatcher(config_manager)
        self.intent_analyzer = IntentAnalyzer(config_manager)

    def is_chat_message(self, message):
        """判断是否为用户聊天消息"""
        try:
            return (
                isinstance(message, dict)
                and "1" in message
                and isinstance(message["1"], dict)  # 确保是字典类型
                and "10" in message["1"]
                and isinstance(message["1"]["10"], dict)  # 确保是字典类型
                and "reminderContent" in message["1"]["10"]
            )
        except Exception:
            return False

    def is_sync_package(self, message_data):
        """判断是否为同步包消息"""
        try:
            return (
                isinstance(message_data, dict)
                and "body" in message_data
                and "syncPushPackage" in message_data["body"]
                and "data" in message_data["body"]["syncPushPackage"]
                and len(message_data["body"]["syncPushPackage"]["data"]) > 0
            )
        except Exception:
            return False

    def is_typing_status(self, message):
        """判断是否为用户正在输入状态消息"""
        try:
            return (
                isinstance(message, dict)
                and "1" in message
                and isinstance(message["1"], list)
                and len(message["1"]) > 0
                and isinstance(message["1"][0], dict)
                and "1" in message["1"][0]
                and isinstance(message["1"][0]["1"], str)
                and "@goofish" in message["1"][0]["1"]
            )
        except Exception:
            return False

    def is_system_message(self, message):
        """判断是否为系统消息"""
        try:
            return (
                isinstance(message, dict)
                and "3" in message
                and isinstance(message["3"], dict)
                and "needPush" in message["3"]
                and message["3"]["needPush"] == "false"
            )
        except Exception:
            return False

    def check_toggle_keywords(self, message):
        """检查消息是否包含切换关键词"""
        message_stripped = message.strip()
        return message_stripped in self.toggle_keywords

    def is_manual_mode(self, chat_id):
        """检查特定会话是否处于人工接管模式"""
        if chat_id not in self.manual_mode_conversations:
            return False

        # 检查是否超时
        current_time = time.time()
        if chat_id in self.manual_mode_timestamps:
            if (
                current_time - self.manual_mode_timestamps[chat_id]
                > self.manual_mode_timeout
            ):
                # 超时，自动退出人工模式
                self.exit_manual_mode(chat_id)
                return False

        return True

    def enter_manual_mode(self, chat_id):
        """进入人工接管模式"""
        self.manual_mode_conversations.add(chat_id)
        self.manual_mode_timestamps[chat_id] = time.time()

    def exit_manual_mode(self, chat_id):
        """退出人工接管模式"""
        self.manual_mode_conversations.discard(chat_id)
        if chat_id in self.manual_mode_timestamps:
            del self.manual_mode_timestamps[chat_id]

    def toggle_manual_mode(self, chat_id):
        """切换人工接管模式"""
        if self.is_manual_mode(chat_id):
            self.exit_manual_mode(chat_id)
            return "auto"
        else:
            self.enter_manual_mode(chat_id)
            return "manual"

    def decrypt_message(self, sync_data):
        """解密消息"""
        try:
            data = sync_data["data"]
            try:
                data = base64.b64decode(data).decode("utf-8")
                data = json.loads(data)
                # logger.info(f"无需解密 message: {data}")
                return None  # 返回None表示无需处理
            except Exception as e:
                # logger.info(f'加密数据: {data}')
                decrypted_data = decrypt(data)
                message = json.loads(decrypted_data)
                return message
        except Exception as e:
            logger.error(f"消息解密失败: {e}")
            return None

    def process_order_message(self, message):
        """处理订单消息"""
        try:
            if message["3"]["redReminder"] == "等待买家付款":
                user_id = message["1"].split("@")[0]
                user_url = f"https://www.goofish.com/personal?userId={user_id}"
                logger.info(f"等待买家 {user_url} 付款")
                return True
            elif message["3"]["redReminder"] == "交易关闭":
                user_id = message["1"].split("@")[0]
                user_url = f"https://www.goofish.com/personal?userId={user_id}"
                logger.info(f"买家 {user_url} 交易关闭")
                return True
            elif message["3"]["redReminder"] == "等待卖家发货":
                user_id = message["1"].split("@")[0]
                user_url = f"https://www.goofish.com/personal?userId={user_id}"
                logger.info(f"交易成功 {user_url} 等待卖家发货")
                return True
        except:
            pass
        return False

    def extract_message_info(self, message):
        """提取消息信息"""
        try:
            create_time = int(message["1"]["5"])
            send_user_name = message["1"]["10"]["reminderTitle"]
            send_user_id = message["1"]["10"]["senderUserId"]
            send_message = message["1"]["10"]["reminderContent"]

            # 时效性验证（过滤5分钟前消息）
            if (time.time() * 1000 - create_time) > self.message_expire_time:
                logger.debug("过期消息丢弃")
                return None

            # 获取商品ID和会话ID
            url_info = message["1"]["10"]["reminderUrl"]
            item_id = (
                url_info.split("itemId=")[1].split("&")[0]
                if "itemId=" in url_info
                else None
            )
            chat_id = message["1"]["2"].split("@")[0]

            if not item_id:
                logger.warning("无法获取商品ID")
                return None

            return {
                "create_time": create_time,
                "send_user_name": send_user_name,
                "send_user_id": send_user_id,
                "send_message": send_message,
                "item_id": item_id,
                "chat_id": chat_id,
            }
        except Exception as e:
            logger.error(f"提取消息信息失败: {e}")
            return None

    async def process_seller_message(self, message_info, myid):
        """处理卖家消息"""
        if message_info["send_user_id"] == myid:
            logger.debug("检测到卖家消息，检查是否为控制命令")

            # 检查切换命令
            if self.check_toggle_keywords(message_info["send_message"]):
                mode = self.toggle_manual_mode(message_info["chat_id"])
                if mode == "manual":
                    logger.info(
                        f"🔴 已接管会话 {message_info['chat_id']} (商品: {message_info['item_id']})"
                    )
                else:
                    logger.info(
                        f"🟢 已恢复会话 {message_info['chat_id']} 的自动回复 (商品: {message_info['item_id']})"
                    )
                return True  # 返回True表示已处理

            # 记录卖家人工回复
            self.context_manager.add_message_by_chat(
                message_info["chat_id"],
                myid,
                message_info["item_id"],
                "assistant",
                message_info["send_message"],
            )
            logger.info(
                f"卖家人工回复 (会话: {message_info['chat_id']}, 商品: {message_info['item_id']}): {message_info['send_message']}"
            )
            return True

        return False

    async def get_item_info(self, item_id):
        """获取商品信息"""
        # 从数据库中获取商品信息，如果不存在则从API获取并保存
        item_info = self.context_manager.get_item_info(item_id)
        if not item_info:
            logger.info(f"从API获取商品信息: {item_id}")
            api_result = self.xianyu_apis.get_item_info(item_id)
            if "data" in api_result and "itemDO" in api_result["data"]:
                item_info = api_result["data"]["itemDO"]
                # 保存商品信息到数据库
                self.context_manager.save_item_info(item_id, item_info)
            else:
                logger.warning(f"获取商品信息失败: {api_result}")
                return None
        else:
            logger.info(f"从数据库获取商品信息: {item_id}")

        return item_info

    async def generate_bot_reply(self, message_info, item_info):
        """生成机器人回复"""
        item_description = (
            f"{item_info['desc']};当前商品售卖价格为:{str(item_info['soldPrice'])}"
        )

        # 获取完整的对话上下文
        context = self.context_manager.get_context_by_chat(message_info["chat_id"])
        formatted_context = self.bot.format_history(context)

        # 分析意图和复杂度
        intent, complexity = self.intent_analyzer.analyze_intent(
            message_info["send_message"], item_description, formatted_context
        )
        
        # 根据意图和复杂度选择模型
        selected_model = self.config_manager.get_model_for_intent(intent, complexity)
        
        logger.info(f"意图分析: intent={intent}, complexity={complexity:.2f}, selected_model={selected_model}")

        # 使用选定的模型生成回复
        bot_reply = self.bot.generate_reply_with_model(
            message_info["send_message"], item_description, context=context, model_name=selected_model
        )

        # 检查是否为价格意图，如果是则增加议价次数
        if self.bot.last_intent == "price":
            self.context_manager.increment_bargain_count_by_chat(
                message_info["chat_id"]
            )
            bargain_count = self.context_manager.get_bargain_count_by_chat(
                message_info["chat_id"]
            )
            logger.info(
                f"用户 {message_info['send_user_name']} 对商品 {message_info['item_id']} 的议价次数: {bargain_count}"
            )

        # 添加机器人回复到上下文
        self.context_manager.add_message_by_chat(
            message_info["chat_id"],
            "bot",
            message_info["item_id"],
            "assistant",
            bot_reply,
        )

        return bot_reply

    async def process_message(self, message_data, websocket_manager, myid):
        """处理消息的主入口"""
        try:
            # 如果不是同步包消息，直接返回
            if not self.is_sync_package(message_data):
                return

            # 获取并解密数据
            sync_data = message_data["body"]["syncPushPackage"]["data"][0]

            # 检查是否有必要的字段
            if "data" not in sync_data:
                logger.debug("同步包中无data字段")
                return

            # 解密数据
            message = self.decrypt_message(sync_data)
            if message is None:
                return

            # 判断是否为订单消息
            if self.process_order_message(message):
                return

            # 判断消息类型
            if self.is_typing_status(message):
                logger.debug("用户正在输入")
                return
            elif not self.is_chat_message(message):
                logger.debug("其他非聊天消息")
                logger.debug(f"原始消息: {message}")
                return

            # 提取消息信息
            message_info = self.extract_message_info(message)
            if not message_info:
                return

            # 处理卖家消息
            if await self.process_seller_message(message_info, myid):
                return

            # 使用消息批处理器处理消息
            await self._process_message_with_batching(message_info, websocket_manager)

        except Exception as e:
            logger.error(f"处理消息时发生错误: {str(e)}")
            logger.debug(f"原始消息: {message_data}")
    
    async def _process_message_with_batching(self, message_info, websocket_manager):
        """使用批处理机制处理消息"""
        # 将消息信息添加到批处理器
        batch_result = await self.message_batcher.add_message(message_info, message_info["chat_id"])
        
        # 如果返回None，说明消息被加入批次等待处理
        if batch_result is None:
            logger.debug(f"消息已加入批次等待处理: {message_info['chat_id']}")
            return
        
        # 如果是单个消息（批处理未启用），直接处理
        if isinstance(batch_result, dict):
            await self._process_single_message(message_info, websocket_manager)
            return
        
        # 如果是批次消息，批量处理
        if isinstance(batch_result, list):
            await self._process_message_batch(batch_result, websocket_manager)
    
    async def _process_single_message(self, message_info, websocket_manager):
        """处理单个消息"""
        logger.info(
            f"用户: {message_info['send_user_name']} (ID: {message_info['send_user_id']}), 商品: {message_info['item_id']}, 会话: {message_info['chat_id']}, 消息: {message_info['send_message']}"
        )

        # 添加用户消息到上下文
        self.context_manager.add_message_by_chat(
            message_info["chat_id"],
            message_info["send_user_id"],
            message_info["item_id"],
            "user",
            message_info["send_message"],
        )

        # 如果当前会话处于人工接管模式，不进行自动回复
        if self.is_manual_mode(message_info["chat_id"]):
            logger.info(
                f"🔴 会话 {message_info['chat_id']} 处于人工接管模式，跳过自动回复"
            )
            return

        if self.is_system_message_from_info(message_info):
            logger.debug("系统消息，跳过处理")
            return

        # 获取商品信息
        item_info = await self.get_item_info(message_info["item_id"])
        if not item_info:
            return

        # 生成机器人回复
        bot_reply = await self.generate_bot_reply(message_info, item_info)

        logger.info(f"机器人回复: {bot_reply}")
        await websocket_manager.send_chat_message(
            message_info["chat_id"], message_info["send_user_id"], bot_reply
        )
    
    async def _process_message_batch(self, message_batch, websocket_manager):
        """批量处理消息"""
        logger.info(f"批量处理 {len(message_batch)} 条消息")
        
        # 按会话分组处理
        chat_groups = {}
        for msg_info in message_batch:
            chat_id = msg_info["chat_id"]
            if chat_id not in chat_groups:
                chat_groups[chat_id] = []
            chat_groups[chat_id].append(msg_info)
        
        # 处理每个会话的消息
        for chat_id, messages in chat_groups.items():
            if self.is_manual_mode(chat_id):
                logger.info(f"🔴 会话 {chat_id} 处于人工接管模式，跳过自动回复")
                continue
            
            # 添加所有用户消息到上下文
            for msg_info in messages:
                self.context_manager.add_message_by_chat(
                    msg_info["chat_id"],
                    msg_info["send_user_id"],
                    msg_info["item_id"],
                    "user",
                    msg_info["send_message"],
                )
            
            # 获取商品信息（使用第一条消息的商品信息）
            item_info = await self.get_item_info(messages[0]["item_id"])
            if not item_info:
                continue
            
            # 生成回复（使用最后一条消息作为主要输入）
            last_message = messages[-1]
            bot_reply = await self.generate_bot_reply(last_message, item_info)
            
            logger.info(f"批量处理机器人回复: {bot_reply}")
            await websocket_manager.send_chat_message(
                chat_id, last_message["send_user_id"], bot_reply
            )
    
    def is_system_message_from_info(self, message_info):
        """从消息信息判断是否为系统消息"""
        # 这里可以添加系统消息的判断逻辑
        return False

    def get_manual_mode_status(self):
        """获取人工接管状态"""
        return {
            "manual_conversations": list(self.manual_mode_conversations),
            "manual_timestamps": self.manual_mode_timestamps,
            "manual_mode_timeout": self.manual_mode_timeout,
        }
    
    def get_performance_stats(self):
        """获取性能统计信息"""
        return {
            "message_batcher": self.message_batcher.get_batch_stats(),
            "manual_conversations_count": len(self.manual_mode_conversations),
        }
