import os
import sys

from loguru import logger

from config.config_manager import ConfigManager
from core.xianyu_live import XianyuLiveRefactored
from XianyuAgent import XianyuReplyBot


def setup_logging(config_manager):
    """设置日志配置"""
    # 配置日志级别
    log_level = config_manager.get("logging.level", "DEBUG").upper()
    log_format = config_manager.get(
        "logging.format",
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    logger.remove()  # 移除默认handler
    logger.add(sys.stderr, level=log_level, format=log_format)
    logger.info(f"日志级别设置为: {log_level}")


def main():
    """主函数"""
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()

        # 设置日志
        setup_logging(config_manager)

        # 创建机器人实例
        bot = XianyuReplyBot()

        # 创建重构后的XianyuLive实例
        xianyu_live = XianyuLiveRefactored(config_manager)

        # 设置机器人实例
        xianyu_live.set_bot(bot)

        # 显示系统状态
        logger.info("系统启动中...")
        status = xianyu_live.get_system_status()
        logger.info(f"系统状态: {status}")

        # 启动主循环
        logger.info("启动主循环...")
        import asyncio

        asyncio.run(xianyu_live.main_loop())

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭系统...")
    except Exception as e:
        logger.error(f"系统运行出错: {e}")
    finally:
        logger.info("系统已关闭")


if __name__ == "__main__":
    main()
