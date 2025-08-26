import asyncio
import json
import time

from loguru import logger

from config.config_manager import ConfigManager
from context_manager import ChatContextManager
from managers.heartbeat_manager import HeartbeatManager
from managers.message_processor import MessageProcessor
from managers.token_manager import TokenManager
from managers.websocket_manager import WebSocketManager
from utils.xianyu_utils import generate_device_id, trans_cookies
from XianyuApis import XianyuApis


class XianyuLiveRefactored:
    """重构后的闲鱼直播类 - 作为协调器管理各个管理器"""

    def __init__(self, config_manager=None):
        # 初始化配置管理器
        self.config_manager = config_manager or ConfigManager()

        # 基础配置
        self.cookies_str = self.config_manager.get("cookies_str")
        self.cookies = trans_cookies(self.cookies_str)
        self.myid = self.cookies["unb"]
        self.device_id = generate_device_id(self.myid)

        # 初始化各个管理器
        self.xianyu_apis = XianyuApis()
        self.xianyu_apis.session.cookies.update(self.cookies)

        self.context_manager = ChatContextManager(
            max_history=self.config_manager.get("database.max_history", 100),
            db_path=self.config_manager.get("database.path", "data/chat_history.db"),
        )

        self.websocket_manager = WebSocketManager(self.config_manager)

        self.heartbeat_manager = HeartbeatManager(
            websocket_manager=self.websocket_manager, config_manager=self.config_manager
        )

        self.token_manager = TokenManager(
            xianyu_apis=self.xianyu_apis,
            device_id=self.device_id,
            config_manager=self.config_manager,
        )

        # 注意：这里需要从外部传入bot实例
        self.bot = None
        self.message_processor = None

        # 任务管理
        self.heartbeat_task = None
        self.token_refresh_task = None

    def set_bot(self, bot):
        """设置机器人实例"""
        self.bot = bot
        self.message_processor = MessageProcessor(
            xianyu_apis=self.xianyu_apis,
            context_manager=self.context_manager,
            bot=bot,
            config_manager=self.config_manager,
        )

    async def initialize_connection(self):
        """初始化连接"""
        logger.info("初始化WebSocket连接...")

        # 建立WebSocket连接
        if not await self.websocket_manager.connect():
            raise Exception("WebSocket连接失败")

        # 初始化Token
        token = await self.token_manager.initialize_token()
        logger.info(f"Token初始化成功: {token[:20]}...")

        # 发送注册消息
        await self.websocket_manager.send_registration(token, self.device_id)
        await asyncio.sleep(1)  # 等待注册完成

        # 发送同步确认消息
        await self.websocket_manager.send_sync_ack()
        logger.info("连接注册完成")

        # 初始化心跳时间
        self.heartbeat_manager.initialize_times()

        return True

    async def handle_heartbeat_response(self, message_data):
        """处理心跳响应"""
        return self.heartbeat_manager.handle_heartbeat_response(message_data)

    async def send_ack(self, message_data):
        """发送ACK响应"""
        return await self.websocket_manager.send_ack(message_data)

    async def process_message(self, message_data):
        """处理消息"""
        if self.message_processor:
            await self.message_processor.process_message(
                message_data, self.websocket_manager, self.myid
            )

    async def start_managers(self):
        """启动所有管理器"""
        logger.info("启动所有管理器...")

        # 启动心跳管理器
        self.heartbeat_manager.start()

        # 启动Token管理器
        self.token_manager.start()

        logger.info("所有管理器已启动")

    async def stop_managers(self):
        """停止所有管理器"""
        logger.info("停止所有管理器...")

        # 停止心跳管理器
        self.heartbeat_manager.stop()

        # 停止Token管理器
        self.token_manager.stop()

        # 断开WebSocket连接
        await self.websocket_manager.disconnect()

        logger.info("所有管理器已停止")

    def check_token_restart(self):
        """检查Token管理器是否需要重启连接"""
        if (
            self.token_manager.token_refresh_task
            and self.token_manager.token_refresh_task.done()
        ):
            try:
                result = self.token_manager.token_refresh_task.result()
                if result:  # Token刷新成功，需要重启连接
                    logger.info("Token刷新成功，准备重新建立连接...")
                    self.websocket_manager.set_restart_flag()
                    return True
            except asyncio.CancelledError:
                pass
        return False

    async def main_loop(self):
        """主循环"""
        while True:
            try:
                # 重置连接重启标志
                self.websocket_manager.reset_restart_flag()

                # 初始化连接
                await self.initialize_connection()

                # 启动管理器
                await self.start_managers()

                # 主消息处理循环
                async for message in self.websocket_manager.listen():
                    try:
                        # 检查是否需要重启连接
                        if self.websocket_manager.should_restart():
                            logger.info("检测到连接重启标志，准备重新建立连接...")
                            break

                        # 检查Token是否需要重启
                        if self.check_token_restart():
                            break

                        # 解析消息
                        message_data = json.loads(message)

                        # 处理心跳响应
                        if await self.handle_heartbeat_response(message_data):
                            continue

                        # 发送通用ACK响应
                        if (
                            "headers" in message_data
                            and "mid" in message_data["headers"]
                        ):
                            await self.send_ack(message_data)

                        # 处理其他消息
                        await self.process_message(message_data)

                    except json.JSONDecodeError:
                        logger.error("消息解析失败")
                    except Exception as e:
                        logger.error(f"处理消息时发生错误: {str(e)}")
                        logger.debug(f"原始消息: {message}")

            except Exception as e:
                logger.error(f"连接发生错误: {e}")

            finally:
                # 清理资源
                await self.stop_managers()

                # 如果是主动重启，立即重连；否则等待5秒
                if self.websocket_manager.should_restart():
                    logger.info("主动重启连接，立即重连...")
                else:
                    logger.info("等待5秒后重连...")
                    await asyncio.sleep(5)

    def get_system_status(self):
        """获取系统状态"""
        return {
            "websocket": {
                "is_connected": self.websocket_manager.is_connected,
                "should_restart": self.websocket_manager.should_restart(),
            },
            "heartbeat": self.heartbeat_manager.get_status(),
            "token": self.token_manager.get_status(),
            "message_processor": (
                self.message_processor.get_performance_stats()
                if self.message_processor
                else {}
            ),
        }
