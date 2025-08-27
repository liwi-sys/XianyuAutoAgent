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
    
    def __init__(self, config_manager, message_processor=None, websocket_manager=None):
        self.config_manager = config_manager
        self.message_processor = message_processor
        self.websocket_manager = websocket_manager
        self.batches: Dict[str, MessageBatch] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        
        # 获取配置
        self._reload_config()
        
        logger.info(f"消息批处理器初始化完成: enabled={self.enabled}, max_batch_size={self.max_batch_size}, max_wait_time_ms={self.max_wait_time_ms}")
    
    def _reload_config(self):
        """重新加载配置"""
        old_config = {
            "enabled": self.enabled if hasattr(self, 'enabled') else None,
            "max_batch_size": self.max_batch_size if hasattr(self, 'max_batch_size') else None,
            "max_wait_time_ms": self.max_wait_time_ms if hasattr(self, 'max_wait_time_ms') else None
        }
        
        self.batching_config = self.config_manager.get_message_batching_config()
        self.enabled = self.batching_config.get("enabled", True)
        self.batch_window_ms = self.batching_config.get("batch_window_ms", 2000)
        self.max_batch_size = self.batching_config.get("max_batch_size", 2)
        self.max_wait_time_ms = self.batching_config.get("max_wait_time_ms", 1500)
        
        # 如果配置发生变化，记录日志
        if (old_config["enabled"] != self.enabled or 
            old_config["max_batch_size"] != self.max_batch_size or
            old_config["max_wait_time_ms"] != self.max_wait_time_ms):
            logger.info(f"批处理配置已更新: enabled={self.enabled}, max_batch_size={self.max_batch_size}, max_wait_time_ms={self.max_wait_time_ms}")
    
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
                logger.debug(f"创建新批次和超时任务: {chat_id}")
            
            # 添加消息到批次
            batch = self.batches[chat_id]
            batch.add_message(message_data)
            batch.last_received_time = current_time  # 更新最后接收时间
            
            logger.debug(f"添加消息到批次 {chat_id}, 当前批次大小: {len(batch.messages)}")
            
            # 检查是否应该立即处理批次（达到最大批次大小）
            if len(batch.messages) >= self.max_batch_size:
                logger.debug(f"批次达到最大大小，创建异步处理任务: {chat_id}")
                # 创建异步处理任务，不等待完成
                asyncio.create_task(self._process_batch_async(chat_id))
                return None  # 返回None表示消息已被异步处理，避免重复处理
            
            return None
    
    async def _process_batch_async(self, chat_id: str) -> None:
        """异步处理批次，不阻塞调用方"""
        try:
            # 延迟处理以避免与心跳冲突
            await asyncio.sleep(0.5)
            await self._process_batch(chat_id)
        except Exception as e:
            logger.error(f"异步批次处理失败: {e}")
    
    async def _process_batch_with_timeout(self, chat_id: str) -> None:
        """带超时的批次处理任务"""
        try:
            # 循环检查，直到需要处理批次
            while True:
                await asyncio.sleep(0.5)  # 每500ms检查一次
                
                # 如果批次不存在或任务被取消，退出
                if chat_id not in self.batches or chat_id not in self.processing_tasks:
                    logger.debug(f"批次或任务不存在，退出: {chat_id}")
                    return
                
                batch = self.batches[chat_id]
                current_time = time.time()
                wait_time_ms = (current_time - batch.last_received_time) * 1000
                
                # 如果等待时间超过阈值，处理批次
                if wait_time_ms >= self.max_wait_time_ms:
                    logger.debug(f"批次超时，开始处理: {chat_id}, 等待时间: {wait_time_ms:.1f}ms")
                    await self._process_batch(chat_id)
                    return
                
                # 如果批次大小达到上限，由add_message异步处理，退出超时任务
                if len(batch.messages) >= self.max_batch_size:
                    logger.debug(f"批次达到大小上限，由add_message异步处理，退出超时任务: {chat_id}")
                    # 清理超时任务，避免重复处理
                    if chat_id in self.processing_tasks:
                        task = self.processing_tasks.pop(chat_id)
                        if not task.done():
                            task.cancel()
                    return
                    
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
            
            # 清理处理任务
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
        
        # 如果有消息处理器和WebSocket管理器，则处理消息生成回复
        if self.message_processor and self.websocket_manager:
            try:
                # 创建低优先级后台任务处理批次，确保不阻塞心跳
                batch_task = asyncio.create_task(
                    self._process_batch_without_blocking(batch.messages, chat_id)
                )
                # 设置低优先级
                batch_task.add_done_callback(self._handle_batch_task_completion)
                logger.debug(f"创建低优先级后台处理任务: {chat_id}")
            except Exception as e:
                logger.error(f"批次消息处理失败: {e}")
        
        return batch.messages
    
    async def _process_batch_without_blocking(self, messages, chat_id):
        """非阻塞处理批次消息"""
        try:
            logger.debug(f"开始非阻塞处理批次: chat_id={chat_id}, size={len(messages)}")
            
            # 使用 asyncio.shield 确保任务不会被意外取消
            await asyncio.shield(
                self.message_processor._process_message_batch(messages, self.websocket_manager)
            )
            
            logger.debug(f"非阻塞批次处理完成: chat_id={chat_id}")
        except asyncio.CancelledError:
            logger.warning(f"非阻塞批次处理被取消: {chat_id}")
        except Exception as e:
            logger.error(f"非阻塞批次处理失败: chat_id={chat_id}, error={e}")
            # 不要重新抛出异常，避免影响其他任务
    
    def _handle_batch_task_completion(self, task):
        """处理批处理任务完成"""
        try:
            task.result()
        except asyncio.CancelledError:
            logger.debug("批处理任务被取消")
        except Exception as e:
            logger.error(f"批处理任务异常完成: {e}")
    
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
            logger.debug(f"清理时处理批次: {chat_id}")
            await self._process_batch(chat_id)
        
        # 等待一段时间让后台任务完成
        logger.debug("等待后台任务完成...")
        await asyncio.sleep(0.5)
        
        # 取消所有仍在运行的处理任务
        for chat_id, task in list(self.processing_tasks.items()):
            if not task.done():
                logger.debug(f"取消处理任务: {chat_id}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
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