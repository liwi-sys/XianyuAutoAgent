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

from managers.token_manager import TokenManager
from XianyuApis import XianyuApis


class TestTokenManager:
    """Token管理器单元测试"""

    @pytest.fixture
    def config_manager(self):
        """配置管理器fixture"""
        config = ConfigManager()
        config.set("token.refresh_interval", 1800)  # 30分钟
        config.set("token.retry_interval", 60)  # 1分钟
        return config

    @pytest.fixture
    def xianyu_apis(self):
        """闲鱼API fixture"""
        return Mock(spec=XianyuApis)

    @pytest.fixture
    def token_manager(self, xianyu_apis, config_manager):
        """Token管理器fixture"""
        return TokenManager(xianyu_apis, "test_device_id", config_manager)

    def test_init(self, xianyu_apis, config_manager):
        """测试初始化"""
        manager = TokenManager(xianyu_apis, "test_device_id", config_manager)

        assert manager.xianyu_apis == xianyu_apis
        assert manager.device_id == "test_device_id"
        assert manager.config_manager == config_manager
        assert manager.token_refresh_interval == 1800
        assert manager.token_retry_interval == 60
        assert manager.last_token_refresh_time == 0
        assert manager.current_token is None
        assert manager.token_refresh_task is None

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, token_manager):
        """测试刷新Token成功"""
        # 模拟API返回成功
        mock_response = {"data": {"accessToken": "test_access_token"}}
        token_manager.xianyu_apis.get_token = AsyncMock(return_value=mock_response)

        result = await token_manager.refresh_token()

        assert result == "test_access_token"
        assert token_manager.current_token == "test_access_token"
        assert token_manager.last_token_refresh_time > 0
        token_manager.xianyu_apis.get_token.assert_called_once_with("test_device_id")

    @pytest.mark.asyncio
    async def test_refresh_token_failure(self, token_manager):
        """测试刷新Token失败"""
        # 模拟API返回失败
        mock_response = {"error": "Invalid credentials"}
        token_manager.xianyu_apis.get_token = AsyncMock(return_value=mock_response)

        result = await token_manager.refresh_token()

        assert result is None
        assert token_manager.current_token is None
        token_manager.xianyu_apis.get_token.assert_called_once_with("test_device_id")

    @pytest.mark.asyncio
    async def test_refresh_token_exception(self, token_manager):
        """测试刷新Token异常"""
        # 模拟API异常
        token_manager.xianyu_apis.get_token = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await token_manager.refresh_token()

        assert result is None
        assert token_manager.current_token is None

    @pytest.mark.asyncio
    async def test_initialize_token_success(self, token_manager):
        """测试初始化Token成功"""
        # 模拟Token刷新成功
        token_manager.refresh_token = AsyncMock(return_value="test_token")

        result = await token_manager.initialize_token()

        assert result == "test_token"
        assert token_manager.current_token == "test_token"
        token_manager.refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_token_failure(self, token_manager):
        """测试初始化Token失败"""
        # 模拟Token刷新失败
        token_manager.refresh_token = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="Token获取失败"):
            await token_manager.initialize_token()

    @pytest.mark.asyncio
    async def test_initialize_token_existing_valid(self, token_manager):
        """测试初始化已存在的有效Token"""
        # 设置现有Token
        token_manager.current_token = "existing_token"
        token_manager.last_token_refresh_time = time.time() - 100  # 100秒前

        # 模拟Token刷新间隔为1800秒
        token_manager.token_refresh_interval = 1800

        result = await token_manager.initialize_token()

        assert result == "existing_token"
        # 不应该调用refresh_token
        token_manager.refresh_token = AsyncMock()
        token_manager.refresh_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_token_existing_expired(self, token_manager):
        """测试初始化已存在的过期Token"""
        # 设置过期Token
        token_manager.current_token = "expired_token"
        token_manager.last_token_refresh_time = time.time() - 2000  # 2000秒前

        # 模拟Token刷新间隔为1800秒
        token_manager.token_refresh_interval = 1800

        # 模拟Token刷新成功
        token_manager.refresh_token = AsyncMock(return_value="new_token")

        result = await token_manager.initialize_token()

        assert result == "new_token"
        token_manager.refresh_token.assert_called_once()

    def test_get_current_token(self, token_manager):
        """测试获取当前Token"""
        # 无Token
        assert token_manager.get_current_token() is None

        # 有Token
        token_manager.current_token = "test_token"
        assert token_manager.get_current_token() == "test_token"

    def test_is_token_valid(self, token_manager):
        """测试Token有效性检查"""
        # 无Token
        assert not token_manager.is_token_valid()

        # 有Token但未设置时间
        token_manager.current_token = "test_token"
        assert not token_manager.is_token_valid()

        # 有效Token
        token_manager.current_token = "test_token"
        token_manager.last_token_refresh_time = time.time() - 100  # 100秒前
        token_manager.token_refresh_interval = 1800
        assert token_manager.is_token_valid()

        # 过期Token
        token_manager.last_token_refresh_time = time.time() - 2000  # 2000秒前
        assert not token_manager.is_token_valid()

    def test_get_status(self, token_manager):
        """测试获取状态"""
        # 初始状态
        status = token_manager.get_status()

        assert status["has_token"] is False
        assert status["last_refresh_time"] == 0
        assert status["token_refresh_interval"] == 1800
        assert status["is_valid"] is False
        assert status["time_until_expiry"] == -1800

        # 设置Token
        token_manager.current_token = "test_token"
        token_manager.last_token_refresh_time = time.time() - 100
        status = token_manager.get_status()

        assert status["has_token"] is True
        assert status["is_valid"] is True
        assert status["time_until_expiry"] > 0

    @pytest.mark.asyncio
    async def test_token_refresh_loop_normal(self, token_manager):
        """测试Token刷新循环正常情况"""
        # 设置初始Token时间
        token_manager.last_token_refresh_time = time.time()

        # 模拟时间流逝
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                token_manager.last_token_refresh_time,  # 初始时间
                token_manager.last_token_refresh_time + 1900,  # 需要刷新Token
                token_manager.last_token_refresh_time + 1901,  # 检查间隔
                token_manager.last_token_refresh_time + 1960,  # 重试间隔
            ]

            # 模拟Token刷新成功
            token_manager.refresh_token = AsyncMock(return_value="new_token")

            # 运行Token刷新循环（应该返回False，不需要重启连接）
            result = await token_manager.token_refresh_loop()

            assert result is False
            token_manager.refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_refresh_loop_restart_needed(self, token_manager):
        """测试Token刷新循环需要重启连接"""
        # 设置初始Token时间
        token_manager.last_token_refresh_time = time.time()

        # 模拟时间流逝
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                token_manager.last_token_refresh_time,  # 初始时间
                token_manager.last_token_refresh_time + 1900,  # 需要刷新Token
                token_manager.last_token_refresh_time + 1901,  # 检查间隔
            ]

            # 模拟Token刷新成功
            token_manager.refresh_token = AsyncMock(return_value="new_token")

            # 运行Token刷新循环（应该返回True，需要重启连接）
            result = await token_manager.token_refresh_loop()

            assert result is True
            token_manager.refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_refresh_loop_failure_retry(self, token_manager):
        """测试Token刷新失败重试"""
        # 设置初始Token时间
        token_manager.last_token_refresh_time = time.time()

        # 模拟时间流逝
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                token_manager.last_token_refresh_time,  # 初始时间
                token_manager.last_token_refresh_time + 1900,  # 需要刷新Token
                token_manager.last_token_refresh_time + 1901,  # 检查间隔
                token_manager.last_token_refresh_time + 1961,  # 重试间隔
                token_manager.last_token_refresh_time + 1962,  # 再次检查
            ]

            # 模拟Token刷新失败
            token_manager.refresh_token = AsyncMock(return_value=None)

            # 运行Token刷新循环（应该返回False，不重启连接）
            result = await token_manager.token_refresh_loop()

            assert result is False
            assert token_manager.refresh_token.call_count == 1  # 只调用一次

    @pytest.mark.asyncio
    async def test_start_and_stop(self, token_manager):
        """测试启动和停止"""
        # 初始状态
        assert token_manager.token_refresh_task is None

        # 启动
        token_manager.start()
        assert token_manager.token_refresh_task is not None
        assert not token_manager.token_refresh_task.done()

        # 停止
        token_manager.stop()
        assert token_manager.token_refresh_task is None

    @pytest.mark.asyncio
    async def test_token_refresh_loop_exception(self, token_manager):
        """测试Token刷新循环异常处理"""
        # 设置初始Token时间
        token_manager.last_token_refresh_time = time.time()

        # 模拟时间流逝
        with patch("time.time") as mock_time:
            mock_time.side_effect = [
                token_manager.last_token_refresh_time,  # 初始时间
                token_manager.last_token_refresh_time + 1900,  # 需要刷新Token
                token_manager.last_token_refresh_time + 1901,  # 检查间隔
                token_manager.last_token_refresh_time + 1902,  # 异常后退出
            ]

            # 模拟Token刷新异常
            token_manager.refresh_token = AsyncMock(
                side_effect=Exception("Refresh error")
            )

            # 运行Token刷新循环（应该会因为异常而退出）
            result = await token_manager.token_refresh_loop()

            assert result is False
            token_manager.refresh_token.assert_called_once()
