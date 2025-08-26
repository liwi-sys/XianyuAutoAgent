import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from loguru import logger


class ConfigManager:
    """统一配置管理器"""

    def __init__(self, config_file: str = "config/config.json"):
        self.config_file = config_file
        self.config = {}
        self.load_config()

    def load_config(self):
        """加载配置"""
        # 首先加载环境变量
        load_dotenv()

        # 加载配置文件
        self.config = self._load_config_file()

        # 合并环境变量到配置中
        self._merge_env_variables()

        # 验证配置
        self._validate_config()

        logger.info("配置加载完成")

    def _load_config_file(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = self._get_default_config()

        if not os.path.exists(self.config_file):
            logger.warning(f"配置文件 {self.config_file} 不存在，使用默认配置")
            return default_config

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                file_config = json.load(f)

            # 合并默认配置和文件配置
            return {**default_config, **file_config}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return default_config

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            # WebSocket配置
            "websocket": {
                "base_url": "wss://wss-goofish.dingtalk.com/",
                "headers": {
                    "Host": "wss-goofish.dingtalk.com",
                    "Connection": "Upgrade",
                    "Pragma": "no-cache",
                    "Cache-Control": "no-cache",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                    "Origin": "https://www.goofish.com",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            },
            # 心跳配置
            "heartbeat": {"interval": 15, "timeout": 5},
            # Token配置
            "token": {"refresh_interval": 3600, "retry_interval": 300},
            # 消息配置
            "message": {
                "expire_time": 300000, 
                "toggle_keywords": "。",
                "batching": {
                    "enabled": True,
                    "batch_window_ms": 2000,
                    "max_batch_size": 3,
                    "max_wait_time_ms": 1500
                }
            },
            # 人工接管配置
            "manual_mode": {"timeout": 3600},
            # LLM配置
            "llm": {
                "default_model": "qwen-max",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "temperature": 0.4,
                "max_tokens": 500,
                "top_p": 0.8,
                "model_routing": {
                    "enabled": True,
                    "models": {
                        "economy": "qwen-turbo",
                        "standard": "qwen-plus",
                        "premium": "qwen-max"
                    },
                    "intent_mapping": {
                        "greeting": "economy",
                        "farewell": "economy",
                        "confirmation": "economy",
                        "price": "standard",
                        "default": "standard",
                        "technical": "premium"
                    },
                    "complexity_thresholds": {
                        "low": 0.3,
                        "high": 0.7
                    }
                }
            },
            # 数据库配置
            "database": {"path": "data/chat_history.db", "max_history": 100},
            # 日志配置
            "logging": {
                "level": "DEBUG",
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            },
            # API配置
            "api": {
                "app_key": "444e9908a51d1cb236a27862abc769c9",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
            },
        }

    def _merge_env_variables(self):
        """合并环境变量到配置中"""
        # 必需的环境变量
        env_mappings = {
            "COOKIES_STR": ["cookies_str"],
            "API_KEY": ["llm", "api_key"],
            "MODEL_BASE_URL": ["llm", "base_url"],
            "HEARTBEAT_INTERVAL": ["heartbeat", "interval"],
            "HEARTBEAT_TIMEOUT": ["heartbeat", "timeout"],
            "TOKEN_REFRESH_INTERVAL": ["token", "refresh_interval"],
            "TOKEN_RETRY_INTERVAL": ["token", "retry_interval"],
            "MESSAGE_EXPIRE_TIME": ["message", "expire_time"],
            "MANUAL_MODE_TIMEOUT": ["manual_mode", "timeout"],
            "TOGGLE_KEYWORDS": ["message", "toggle_keywords"],
            "LOG_LEVEL": ["logging", "level"],
            "MODEL_ROUTING_ENABLED": ["llm", "model_routing", "enabled"],
            "MESSAGE_BATCHING_ENABLED": ["message", "batching", "enabled"],
            "BATCH_WINDOW_MS": ["message", "batching", "batch_window_ms"],
            "MAX_BATCH_SIZE": ["message", "batching", "max_batch_size"],
        }

        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(
                    self.config, config_path, self._convert_env_value(env_value)
                )

    def _set_nested_value(self, config: Dict[str, Any], path: list, value: Any):
        """设置嵌套配置值"""
        for key in path[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # 类型转换
        if path[-1] in [
            "interval",
            "timeout",
            "expire_time",
            "max_history",
            "max_tokens",
        ]:
            config[path[-1]] = int(value)
        elif path[-1] in ["temperature", "top_p"]:
            config[path[-1]] = float(value)
        else:
            config[path[-1]] = value

    def _convert_env_value(self, value: str) -> Any:
        """转换环境变量值"""
        # 尝试转换为整数
        try:
            return int(value)
        except ValueError:
            pass

        # 尝试转换为浮点数
        try:
            return float(value)
        except ValueError:
            pass

        # 尝试转换为布尔值
        if value.lower() in ["true", "yes", "1"]:
            return True
        elif value.lower() in ["false", "no", "0"]:
            return False

        # 返回字符串
        return value

    def _validate_config(self):
        """验证配置"""
        required_fields = [
            ("cookies_str", "COOKIES_STR"),
            ("llm.api_key", "API_KEY"),
            ("llm.base_url", "MODEL_BASE_URL"),
        ]

        for field, env_var in required_fields:
            if not self.get(field):
                logger.error(f"缺少必需的配置: {field} (环境变量: {env_var})")
                logger.error(f"请在 .env 文件中设置 {env_var} 环境变量")
                logger.error(f"可以参考 .env.example 文件进行配置")
                raise ValueError(f"缺少必需的配置: {field}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save_config(self):
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logger.info(f"配置已保存到 {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def get_websocket_config(self) -> Dict[str, Any]:
        """获取WebSocket配置"""
        return self.get("websocket", {})

    def get_heartbeat_config(self) -> Dict[str, Any]:
        """获取心跳配置"""
        return self.get("heartbeat", {})

    def get_token_config(self) -> Dict[str, Any]:
        """获取Token配置"""
        return self.get("token", {})

    def get_message_config(self) -> Dict[str, Any]:
        """获取消息配置"""
        return self.get("message", {})

    def get_manual_mode_config(self) -> Dict[str, Any]:
        """获取人工接管配置"""
        return self.get("manual_mode", {})

    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self.get("llm", {})
    
    def get_model_routing_config(self) -> Dict[str, Any]:
        """获取模型路由配置"""
        return self.get("llm.model_routing", {})
    
    def get_message_batching_config(self) -> Dict[str, Any]:
        """获取消息批处理配置"""
        return self.get("message.batching", {})
    
    def get_model_for_intent(self, intent: str, complexity: float = 0.5) -> str:
        """根据意图和复杂度获取合适的模型"""
        routing_config = self.get_model_routing_config()
        
        if not routing_config.get("enabled", False):
            return self.get("llm.default_model", "qwen-max")
        
        # 获取意图映射的模型级别
        intent_mapping = routing_config.get("intent_mapping", {})
        model_level = intent_mapping.get(intent, "standard")
        
        # 根据复杂度调整模型级别
        thresholds = routing_config.get("complexity_thresholds", {})
        if complexity > thresholds.get("high", 0.7):
            model_level = "premium"
        elif complexity < thresholds.get("low", 0.3):
            model_level = "economy"
        
        # 获取对应的模型名称
        models = routing_config.get("models", {})
        selected_model = models.get(model_level, self.get("llm.default_model", "qwen-max"))
        
        # 如果路由配置不完整，使用默认模型
        if not selected_model or selected_model == "qwen-max":
            return self.get("llm.default_model", "qwen-max")
        
        return selected_model

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self.get("database", {})

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get("logging", {})

    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置"""
        return self.get("api", {})

    def reload(self):
        """重新加载配置"""
        logger.info("重新加载配置...")
        self.load_config()

    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()

    def __str__(self) -> str:
        return f"ConfigManager(config_file={self.config_file})"

    def __repr__(self) -> str:
        return self.__str__()
