import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class MessageBatch:
    """消息批次数据类"""
    chat_id: str
    messages: List[Dict[str, Any]]
    first_received_time: float
    last_received_time: float
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """添加消息到批次"""
        self.messages.append(message)
        self.last_received_time = time.time()
    
    def should_process(self, max_batch_size: int, max_wait_time_ms: int) -> bool:
        """判断是否应该处理此批次"""
        current_time = time.time()
        wait_time_ms = (current_time - self.first_received_time) * 1000
        
        # 达到最大批次大小或等待时间超限
        return len(self.messages) >= max_batch_size or wait_time_ms >= max_wait_time_ms


class MessageBatcher:
    """消息批处理器 - 实现消息缓冲和批处理"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.batches: Dict[str, MessageBatch] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        
        # 获取配置
        self.batching_config = config_manager.get_message_batching_config()
        self.enabled = self.batching_config.get("enabled", True)
        self.batch_window_ms = self.batching_config.get("batch_window_ms", 2000)
        self.max_batch_size = self.batching_config.get("max_batch_size", 3)
        self.max_wait_time_ms = self.batching_config.get("max_wait_time_ms", 1500)
        
        logger.info(f"消息批处理器初始化完成: enabled={self.enabled}, batch_window_ms={self.batch_window_ms}")
    
    async def add_message(self, message_data: Dict[str, Any], chat_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        添加消息到批处理器
        
        Args:
            message_data: 消息数据
            chat_id: 会话ID
            
        Returns:
            如果批次已满，返回批次消息列表；否则返回None
        """
        if not self.enabled:
            return [message_data]  # 如果未启用批处理，直接返回原消息
        
        async with self.lock:
            current_time = time.time()
            
            # 如果此会话没有批次，创建新批次
            if chat_id not in self.batches:
                self.batches[chat_id] = MessageBatch(
                    chat_id=chat_id,
                    messages=[],
                    first_received_time=current_time,
                    last_received_time=current_time
                )
                
                # 为此会话启动处理任务
                self.processing_tasks[chat_id] = asyncio.create_task(
                    self._process_batch_with_timeout(chat_id)
                )
            
            # 添加消息到批次
            batch = self.batches[chat_id]
            batch.add_message(message_data)
            
            logger.debug(f"添加消息到批次 {chat_id}, 当前批次大小: {len(batch.messages)}")
            
            # 检查是否应该立即处理批次
            if batch.should_process(self.max_batch_size, self.max_wait_time_ms):
                return await self._process_batch(chat_id)
            
            return None
    
    async def _process_batch_with_timeout(self, chat_id: str) -> None:
        """带超时的批次处理任务"""
        try:
            # 等待批处理窗口时间
            await asyncio.sleep(self.max_wait_time_ms / 1000)
            
            # 如果批次仍然存在，处理它
            if chat_id in self.batches:
                await self._process_batch(chat_id)
        except asyncio.CancelledError:
            logger.debug(f"批次处理任务被取消: {chat_id}")
        except Exception as e:
            logger.error(f"批次处理任务出错: {e}")
    
    async def _process_batch(self, chat_id: str) -> List[Dict[str, Any]]:
        """处理指定会话的消息批次"""
        async with self.lock:
            if chat_id not in self.batches:
                return []
            
            batch = self.batches.pop(chat_id)
            
            # 取消处理任务
            if chat_id in self.processing_tasks:
                task = self.processing_tasks.pop(chat_id)
                if not task.done():
                    task.cancel()
        
        if not batch.messages:
            return []
        
        # 记录批处理统计
        batch_size = len(batch.messages)
        processing_time_ms = (time.time() - batch.first_received_time) * 1000
        
        logger.info(f"处理消息批次: chat_id={chat_id}, size={batch_size}, processing_time={processing_time_ms:.1f}ms")
        
        return batch.messages
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """获取批处理统计信息"""
        return {
            "enabled": self.enabled,
            "active_batches": len(self.batches),
            "active_tasks": len(self.processing_tasks),
            "config": {
                "batch_window_ms": self.batch_window_ms,
                "max_batch_size": self.max_batch_size,
                "max_wait_time_ms": self.max_wait_time_ms
            }
        }
    
    async def cleanup(self) -> None:
        """清理资源，处理所有待处理的消息"""
        logger.info("清理消息批处理器...")
        
        # 处理所有待处理的批次
        for chat_id in list(self.batches.keys()):
            await self._process_batch(chat_id)
        
        # 取消所有处理任务
        for task in self.processing_tasks.values():
            if not task.done():
                task.cancel()
        
        self.batches.clear()
        self.processing_tasks.clear()
        logger.info("消息批处理器清理完成")


class IntentAnalyzer:
    """意图分析器 - 分析消息意图和复杂度"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        
        # 意图关键词和模式
        self.intent_patterns = {
            "greeting": {
                "keywords": ["你好", "嗨", "hi", "hello", "在吗", "在不在", "早上好", "下午好", "晚上好"],
                "weight": 0.1
            },
            "farewell": {
                "keywords": ["再见", "bye", "拜拜", "88", "走了", "回聊", "晚安"],
                "weight": 0.1
            },
            "confirmation": {
                "keywords": ["好的", "ok", "行", "可以", "没问题", "是的", "对", "确认"],
                "weight": 0.2
            },
            "price": {
                "keywords": ["价格", "多少钱", "便宜", "贵", "砍价", "少点", "能少", "优惠", "折扣"],
                "weight": 0.5
            },
            "technical": {
                "keywords": ["参数", "规格", "型号", "连接", "对比", "怎么用", "安装", "配置", "兼容"],
                "weight": 0.8
            }
        }
    
    def analyze_intent(self, message: str, item_desc: str = "", context: str = "") -> tuple[str, float]:
        """
        分析消息意图和复杂度
        
        Args:
            message: 用户消息
            item_desc: 商品描述
            context: 对话上下文
            
        Returns:
            (意图类型, 复杂度分数)
        """
        message_lower = message.lower()
        
        # 计算每种意图的匹配分数
        intent_scores = {}
        for intent, pattern in self.intent_patterns.items():
            score = 0
            for keyword in pattern["keywords"]:
                if keyword in message_lower:
                    score += pattern["weight"]
            intent_scores[intent] = score
        
        # 找到得分最高的意图
        best_intent = max(intent_scores, key=intent_scores.get)
        best_score = intent_scores[best_intent]
        
        # 如果没有匹配到任何意图，使用默认意图
        if best_score == 0:
            best_intent = "default"
        
        # 计算复杂度分数
        complexity = self._calculate_complexity(message, item_desc, context, best_intent)
        
        return best_intent, complexity
    
    def _calculate_complexity(self, message: str, item_desc: str, context: str, intent: str) -> float:
        """计算消息复杂度"""
        complexity = 0.0
        
        # 基础复杂度（基于意图）
        intent_complexity = {
            "greeting": 0.1,
            "farewell": 0.1,
            "confirmation": 0.2,
            "price": 0.5,
            "technical": 0.8,
            "default": 0.4
        }
        complexity += intent_complexity.get(intent, 0.4)
        
        # 消息长度因子
        if len(message) > 50:
            complexity += 0.1
        if len(message) > 100:
            complexity += 0.1
        
        # 包含数字（可能涉及价格、规格等）
        import re
        if re.search(r'\d+', message):
            complexity += 0.1
        
        # 包含问题
        if "？" in message or "吗" in message or "怎么" in message:
            complexity += 0.1
        
        # 商品描述长度（如果涉及技术问题）
        if intent == "technical" and len(item_desc) > 200:
            complexity += 0.1
        
        # 上下文长度（复杂对话需要更多上下文理解）
        if len(context) > 500:
            complexity += 0.1
        
        return min(complexity, 1.0)  # 限制最大值为1.0