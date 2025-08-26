import asyncio
import sys
import time

from loguru import logger

from XianyuApis import XianyuApis


class TokenManager:
    """Token管理器"""

    def __init__(self, xianyu_apis, device_id, config_manager):
        self.xianyu_apis = xianyu_apis
        self.device_id = device_id
        self.config_manager = config_manager
        self.token_refresh_interval = config_manager.get("token.refresh_interval", 3600)
        self.token_retry_interval = config_manager.get("token.retry_interval", 300)
        self.last_token_refresh_time = 0
        self.current_token = None
        self.token_refresh_task = None

    async def refresh_token(self):
        """刷新token"""
        try:
            logger.info("开始刷新token...")

            # 获取新token（如果Cookie失效，get_token会直接退出程序）
            token_result = self.xianyu_apis.get_token(self.device_id)
            if "data" in token_result and "accessToken" in token_result["data"]:
                new_token = token_result["data"]["accessToken"]
                self.current_token = new_token
                self.last_token_refresh_time = time.time()
                logger.info("Token刷新成功")
                return new_token
            else:
                logger.error(f"Token刷新失败: {token_result}")
                return None

        except Exception as e:
            logger.error(f"Token刷新异常: {str(e)}")
            return None

    async def token_refresh_loop(self):
        """Token刷新循环"""
        while True:
            try:
                current_time = time.time()

                # 检查是否需要刷新token
                if (
                    current_time - self.last_token_refresh_time
                    >= self.token_refresh_interval
                ):
                    logger.info("Token即将过期，准备刷新...")

                    new_token = await self.refresh_token()
                    if new_token:
                        logger.info("Token刷新成功，准备重新建立连接...")
                        # 设置连接重启标志
                        return True  # 返回True表示需要重启连接
                    else:
                        logger.error(
                            "Token刷新失败，将在{}分钟后重试".format(
                                self.token_retry_interval // 60
                            )
                        )
                        await asyncio.sleep(
                            self.token_retry_interval
                        )  # 使用配置的重试间隔
                        continue

                # 每分钟检查一次
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Token刷新循环出错: {e}")
                await asyncio.sleep(60)

        return False  # 返回False表示不需要重启连接

    def start(self):
        """启动token刷新任务"""
        if not self.token_refresh_task or self.token_refresh_task.done():
            self.token_refresh_task = asyncio.create_task(self.token_refresh_loop())
            logger.info("Token刷新任务已启动")

    def stop(self):
        """停止token刷新任务"""
        if self.token_refresh_task and not self.token_refresh_task.done():
            self.token_refresh_task.cancel()
            try:
                # 等待任务完成
                self.token_refresh_task = None
                logger.info("Token刷新任务已停止")
            except asyncio.CancelledError:
                pass

    async def initialize_token(self):
        """初始化token"""
        if (
            not self.current_token
            or (time.time() - self.last_token_refresh_time)
            >= self.token_refresh_interval
        ):
            logger.info("获取初始token...")
            await self.refresh_token()

        if not self.current_token:
            logger.error("无法获取有效token，初始化失败")
            raise Exception("Token获取失败")

        return self.current_token

    def get_current_token(self):
        """获取当前token"""
        return self.current_token

    def is_token_valid(self):
        """检查token是否有效"""
        if not self.current_token:
            return False

        current_time = time.time()
        return (
            current_time - self.last_token_refresh_time
        ) < self.token_refresh_interval

    def get_status(self):
        """获取token状态信息"""
        current_time = time.time()
        return {
            "has_token": self.current_token is not None,
            "last_refresh_time": self.last_token_refresh_time,
            "token_refresh_interval": self.token_refresh_interval,
            "is_valid": self.is_token_valid(),
            "time_until_expiry": self.token_refresh_interval
            - (current_time - self.last_token_refresh_time),
        }
