import asyncio
import json
import time

from loguru import logger

from utils.xianyu_utils import generate_mid


class HeartbeatManager:
    """心跳管理器"""

    def __init__(self, websocket_manager, config_manager):
        self.websocket_manager = websocket_manager
        self.config_manager = config_manager
        self.heartbeat_interval = config_manager.get("heartbeat.interval", 15)
        self.heartbeat_timeout = config_manager.get("heartbeat.timeout", 5)
        self.last_heartbeat_time = 0
        self.last_heartbeat_response = 0
        self.heartbeat_task = None

    async def send_heartbeat(self):
        """发送心跳包并等待响应"""
        try:
            heartbeat_mid = generate_mid()
            heartbeat_msg = {"lwp": "/!", "headers": {"mid": heartbeat_mid}}

            success = await self.websocket_manager.send_message(heartbeat_msg)
            if success:
                self.last_heartbeat_time = time.time()
                logger.debug("心跳包已发送")
                return heartbeat_mid
            else:
                logger.error("发送心跳包失败")
                return None
        except Exception as e:
            logger.error(f"发送心跳包失败: {e}")
            raise

    def handle_heartbeat_response(self, message_data):
        """处理心跳响应"""
        try:
            if (
                isinstance(message_data, dict)
                and "headers" in message_data
                and "mid" in message_data["headers"]
                and "code" in message_data
                and message_data["code"] == 200
            ):
                self.last_heartbeat_response = time.time()
                logger.debug("收到心跳响应")
                return True
        except Exception as e:
            logger.error(f"处理心跳响应出错: {e}")
        return False

    async def heartbeat_loop(self):
        """心跳维护循环"""
        while True:
            try:
                current_time = time.time()

                # 检查是否需要发送心跳
                if current_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    await self.send_heartbeat()

                # 检查上次心跳响应时间，如果超时则认为连接已断开
                if (current_time - self.last_heartbeat_response) > (
                    self.heartbeat_interval + self.heartbeat_timeout
                ):
                    logger.warning("心跳响应超时，可能连接已断开")
                    break

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"心跳循环出错: {e}")
                break

    def start(self):
        """启动心跳任务"""
        if not self.heartbeat_task or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            logger.info("心跳任务已启动")

    def stop(self):
        """停止心跳任务"""
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                # 等待任务完成
                self.heartbeat_task = None
                logger.info("心跳任务已停止")
            except asyncio.CancelledError:
                pass

    def initialize_times(self):
        """初始化心跳时间"""
        current_time = time.time()
        self.last_heartbeat_time = current_time
        self.last_heartbeat_response = current_time

    def is_healthy(self):
        """检查心跳健康状态"""
        current_time = time.time()
        return (current_time - self.last_heartbeat_response) <= (
            self.heartbeat_interval + self.heartbeat_timeout
        )

    def get_status(self):
        """获取心跳状态信息"""
        current_time = time.time()
        return {
            "last_heartbeat_time": self.last_heartbeat_time,
            "last_heartbeat_response": self.last_heartbeat_response,
            "heartbeat_interval": self.heartbeat_interval,
            "heartbeat_timeout": self.heartbeat_timeout,
            "is_healthy": self.is_healthy(),
            "time_since_last_response": current_time - self.last_heartbeat_response,
        }
