import asyncio
import base64
import json
import time

import websockets
from loguru import logger

from utils.xianyu_utils import generate_mid, generate_uuid


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.cookies_str = config_manager.get("cookies_str")
        self.base_url = config_manager.get("websocket.base_url")
        self.headers = self._get_headers()
        self.websocket = None
        self.connection_restart_flag = False

    def _get_headers(self):
        """获取WebSocket连接头"""
        headers = self.config_manager.get("websocket.headers", {}).copy()
        headers["Cookie"] = self.cookies_str
        return headers

    async def connect(self):
        """建立WebSocket连接"""
        try:
            self.websocket = await websockets.connect(
                self.base_url, additional_headers=self.headers
            )
            logger.info("WebSocket连接建立成功")
            return True
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            return False

    async def disconnect(self):
        """断开WebSocket连接"""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket连接已关闭")
            except Exception as e:
                logger.error(f"关闭WebSocket连接时出错: {e}")
            finally:
                self.websocket = None

    async def send_message(self, message):
        """发送消息"""
        if not self.websocket:
            logger.error("WebSocket未连接")
            return False

        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            await self.websocket.send(message)
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def send_registration(self, token, device_id):
        """发送注册消息"""
        api_config = self.config_manager.get_api_config()
        msg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": api_config.get(
                    "app_key", "444e9908a51d1cb236a27862abc769c9"
                ),
                "token": token,
                "ua": api_config.get(
                    "user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
                ),
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": device_id,
                "mid": generate_mid(),
            },
        }
        return await self.send_message(msg)

    async def send_sync_ack(self):
        """发送同步确认消息"""
        msg = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": "5701741704675979 0"},
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": int(time.time() * 1000) * 1000,
                    "seq": 0,
                    "timestamp": int(time.time() * 1000),
                }
            ],
        }
        return await self.send_message(msg)

    async def send_chat_message(self, cid, toid, text):
        """发送聊天消息"""
        text_content = {"contentType": 1, "text": {"text": text}}
        text_base64 = str(
            base64.b64encode(json.dumps(text_content).encode("utf-8")), "utf-8"
        )
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "uuid": generate_uuid(),
                    "cid": f"{cid}@goofish",
                    "conversationType": 1,
                    "content": {
                        "contentType": 101,
                        "custom": {"type": 1, "data": text_base64},
                    },
                    "redPointPolicy": 0,
                    "extension": {"extJson": "{}"},
                    "ctx": {"appVersion": "1.0", "platform": "web"},
                    "mtags": {},
                    "msgReadStatusSetting": 1,
                },
                {
                    "actualReceivers": [
                        f"{toid}@goofish",
                    ]
                },
            ],
        }
        return await self.send_message(msg)

    async def send_ack(self, message_data):
        """发送ACK响应"""
        try:
            ack = {
                "code": 200,
                "headers": {
                    "mid": (
                        message_data["headers"]["mid"]
                        if "mid" in message_data["headers"]
                        else generate_mid()
                    ),
                    "sid": (
                        message_data["headers"]["sid"]
                        if "sid" in message_data["headers"]
                        else ""
                    ),
                },
            }
            if "app-key" in message_data["headers"]:
                ack["headers"]["app-key"] = message_data["headers"]["app-key"]
            if "ua" in message_data["headers"]:
                ack["headers"]["ua"] = message_data["headers"]["ua"]
            if "dt" in message_data["headers"]:
                ack["headers"]["dt"] = message_data["headers"]["dt"]
            return await self.send_message(ack)
        except Exception as e:
            logger.error(f"发送ACK响应失败: {e}")
            return False

    async def listen(self):
        """监听消息"""
        if not self.websocket:
            logger.error("WebSocket未连接")
            return

        try:
            async for message in self.websocket:
                yield message
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket连接已关闭")
        except Exception as e:
            logger.error(f"监听消息时出错: {e}")

    def set_restart_flag(self):
        """设置连接重启标志"""
        self.connection_restart_flag = True

    def should_restart(self):
        """检查是否需要重启连接"""
        return self.connection_restart_flag

    def reset_restart_flag(self):
        """重置连接重启标志"""
        self.connection_restart_flag = False

    @property
    def is_connected(self):
        """检查连接状态"""
        return self.websocket is not None and not self.websocket.closed
