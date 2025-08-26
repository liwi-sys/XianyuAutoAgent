import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config_manager import ConfigManager


class TestConfigManager:
    """配置管理器单元测试"""

    def test_init_with_default_config(self):
        """测试默认配置初始化"""
        config_manager = ConfigManager()

        # 测试默认配置值
        assert config_manager.get("heartbeat.interval") == 15
        assert config_manager.get("llm.model_name") == "qwen-max"
        assert config_manager.get("message.expire_time") == 300000
        assert (
            config_manager.get("websocket.base_url")
            == "wss://wss-goofish.dingtalk.com/"
        )

    def test_init_with_custom_config_file(self):
        """测试自定义配置文件"""
        custom_config = {
            "heartbeat": {"interval": 30},
            "llm": {"model_name": "custom-model"},
            "message": {"expire_time": 600000},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom_config, f)
            temp_config_path = f.name

        try:
            config_manager = ConfigManager(temp_config_path)

            # 测试自定义配置值
            assert config_manager.get("heartbeat.interval") == 30
            assert config_manager.get("llm.model_name") == "custom-model"
            assert config_manager.get("message.expire_time") == 600000

            # 测试默认配置值保持不变
            assert (
                config_manager.get("websocket.base_url")
                == "wss://wss-goofish.dingtalk.com/"
            )
        finally:
            os.unlink(temp_config_path)

    @patch.dict(
        os.environ,
        {
            "HEARTBEAT_INTERVAL": "60",
            "MODEL_NAME": "env-model",
            "MESSAGE_EXPIRE_TIME": "900000",
        },
    )
    def test_environment_variables_override(self):
        """测试环境变量覆盖配置"""
        config_manager = ConfigManager()

        # 测试环境变量覆盖的值
        assert config_manager.get("heartbeat.interval") == 60
        assert config_manager.get("llm.model_name") == "env-model"
        assert config_manager.get("message.expire_time") == 900000

    def test_get_nested_config(self):
        """测试获取嵌套配置"""
        config_manager = ConfigManager()

        # 测试嵌套配置获取
        websocket_config = config_manager.get_websocket_config()
        assert "base_url" in websocket_config
        assert "headers" in websocket_config

        heartbeat_config = config_manager.get_heartbeat_config()
        assert "interval" in heartbeat_config
        assert "timeout" in heartbeat_config

        llm_config = config_manager.get_llm_config()
        assert "model_name" in llm_config
        assert "base_url" in llm_config

    def test_set_config(self):
        """测试设置配置值"""
        config_manager = ConfigManager()

        # 设置配置值
        config_manager.set("test.key", "test_value")
        assert config_manager.get("test.key") == "test_value"

        # 设置嵌套配置值
        config_manager.set("nested.deep.key", "nested_value")
        assert config_manager.get("nested.deep.key") == "nested_value"

    def test_get_with_default(self):
        """测试获取配置默认值"""
        config_manager = ConfigManager()

        # 测试不存在的配置返回默认值
        assert config_manager.get("nonexistent.key", "default_value") == "default_value"
        assert config_manager.get("nonexistent.key") is None

    def test_type_conversion(self):
        """测试类型转换"""
        config_manager = ConfigManager()

        # 测试整数转换
        assert isinstance(config_manager.get("heartbeat.interval"), int)
        assert isinstance(config_manager.get("message.expire_time"), int)

        # 测试浮点数转换
        assert isinstance(config_manager.get("llm.temperature"), float)
        assert isinstance(config_manager.get("llm.top_p"), float)

    def test_save_config(self):
        """测试保存配置"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_config_path = f.name

        try:
            config_manager = ConfigManager(temp_config_path)

            # 修改配置
            config_manager.set("test.key", "modified_value")

            # 保存配置
            config_manager.save_config()

            # 重新加载配置验证
            new_config_manager = ConfigManager(temp_config_path)
            assert new_config_manager.get("test.key") == "modified_value"
        finally:
            if os.path.exists(temp_config_path):
                os.unlink(temp_config_path)

    def test_config_validation(self):
        """测试配置验证"""
        # 测试缺少必需配置时的错误
        with patch.dict(
            os.environ,
            {"COOKIES_STR": "", "API_KEY": "", "MODEL_BASE_URL": "", "MODEL_NAME": ""},
            clear=True,
        ):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(
                    {"llm": {"model_name": "test"}}, f
                )  # 缺少 api_key 和 base_url
                temp_config_path = f.name

            try:
                with pytest.raises(ValueError, match="缺少必需的配置"):
                    ConfigManager(temp_config_path)
            finally:
                os.unlink(temp_config_path)

    def test_get_all_config(self):
        """测试获取所有配置"""
        config_manager = ConfigManager()

        all_config = config_manager.get_all_config()

        # 验证配置结构
        assert isinstance(all_config, dict)
        assert "websocket" in all_config
        assert "heartbeat" in all_config
        assert "llm" in all_config
        assert "message" in all_config

    def test_reload_config(self):
        """测试重新加载配置"""
        config_manager = ConfigManager()

        # 获取原始配置
        original_interval = config_manager.get("heartbeat.interval")

        # 修改配置文件
        config_manager.set("heartbeat.interval", 999)
        config_manager.save_config()

        # 重新加载配置
        config_manager.reload()

        # 验证配置重新加载
        assert config_manager.get("heartbeat.interval") == 999
