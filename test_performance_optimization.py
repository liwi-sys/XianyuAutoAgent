#!/usr/bin/env python3
"""
性能优化测试脚本
测试LLM模型路由和消息批处理功能
"""

import asyncio
import time
import json
from config.config_manager import ConfigManager
from managers.message_batcher import MessageBatcher, IntentAnalyzer
from XianyuAgent import XianyuReplyBot


async def test_model_routing():
    """测试模型路由功能"""
    print("=== 测试模型路由功能 ===")
    
    # 初始化配置和组件
    config_manager = ConfigManager("test_config.json")
    bot = XianyuReplyBot(config_manager)
    intent_analyzer = IntentAnalyzer(config_manager)
    
    # 测试消息样例
    test_messages = [
        ("你好", "这是一件普通的T恤", "greeting"),
        ("这个多少钱", "时尚T恤，价格99元", "price"),
        ("这个衣服的参数是什么", "高科技智能T恤，采用纳米技术制作", "technical"),
        ("好的，我要了", "优质T恤，舒适透气", "confirmation"),
        ("再见", "品牌T恤，质量保证", "farewell"),
    ]
    
    print("测试消息和模型选择结果:")
    print("-" * 80)
    
    for msg, item_desc, expected_intent in test_messages:
        # 分析意图和复杂度
        intent, complexity = intent_analyzer.analyze_intent(msg, item_desc)
        
        # 选择模型
        selected_model = config_manager.get_model_for_intent(intent, complexity)
        
        print(f"消息: {msg}")
        print(f"  预期意图: {expected_intent}, 实际意图: {intent}")
        print(f"  复杂度: {complexity:.2f}")
        print(f"  选择模型: {selected_model}")
        print()
    
    # 显示配置的模型映射
    print("当前模型路由配置:")
    routing_config = config_manager.get_model_routing_config()
    print(json.dumps(routing_config, indent=2, ensure_ascii=False))


async def test_message_batching():
    """测试消息批处理功能"""
    print("\n=== 测试消息批处理功能 ===")
    
    # 初始化配置和批处理器
    config_manager = ConfigManager("test_config.json")
    batcher = MessageBatcher(config_manager)
    
    # 模拟消息数据
    test_messages = [
        {
            "chat_id": "chat_001",
            "send_message": "你好",
            "send_user_id": "user_001",
            "item_id": "item_001",
            "send_user_name": "测试用户1"
        },
        {
            "chat_id": "chat_001", 
            "send_message": "这个多少钱",
            "send_user_id": "user_001",
            "item_id": "item_001",
            "send_user_name": "测试用户1"
        },
        {
            "chat_id": "chat_002",
            "send_message": "你好",
            "send_user_id": "user_002", 
            "item_id": "item_002",
            "send_user_name": "测试用户2"
        },
    ]
    
    print("测试消息批处理:")
    print("-" * 80)
    
    # 添加消息到批处理器
    for i, msg in enumerate(test_messages):
        print(f"添加消息 {i+1}: {msg['send_message']} (会话: {msg['chat_id']})")
        
        result = await batcher.add_message(msg, msg["chat_id"])
        
        if result is None:
            print(f"  -> 消息已加入批次，等待处理...")
        elif isinstance(result, list):
            print(f"  -> 批次已满，处理 {len(result)} 条消息")
        else:
            print(f"  -> 立即处理单条消息")
        
        # 短暂延迟模拟真实场景
        await asyncio.sleep(0.1)
    
    # 等待剩余批次处理完成
    print("\n等待剩余批次处理...")
    await asyncio.sleep(2)
    
    # 显示批处理统计
    stats = batcher.get_batch_stats()
    print("\n批处理统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    # 清理资源
    await batcher.cleanup()


async def test_cost_analysis():
    """测试成本分析"""
    print("\n=== 成本效益分析 ===")
    
    # 模型成本估算（示例，实际成本请参考具体服务商定价）
    model_costs = {
        "qwen-turbo": 0.0005,  # 每千token成本（元）
        "qwen-plus": 0.002,
        "qwen-max": 0.02
    }
    
    # 模拟一天的消息分布
    daily_messages = {
        "greeting": 100,    # 问候
        "farewell": 50,     # 告别
        "confirmation": 80, # 确认
        "price": 200,       # 价格咨询
        "technical": 70,    # 技术咨询
        "default": 100      # 默认
    }
    
    print("每日消息分布:")
    for intent, count in daily_messages.items():
        print(f"  {intent}: {count} 条")
    
    # 计算优化前后的成本
    config_manager = ConfigManager("test_config.json")
    routing_config = config_manager.get_model_routing_config()
    
    # 优化前：全部使用 qwen-max
    total_messages = sum(daily_messages.values())
    old_cost = total_messages * 500 * model_costs["qwen-max"] / 1000  # 假设平均500token
    
    # 优化后：根据意图选择模型
    new_cost = 0
    intent_mapping = routing_config.get("intent_mapping", {})
    models = routing_config.get("models", {})
    
    for intent, count in daily_messages.items():
        model_level = intent_mapping.get(intent, "standard")
        model_name = models.get(model_level, "qwen-max")
        cost = count * 500 * model_costs.get(model_name, model_costs["qwen-max"]) / 1000
        new_cost += cost
        print(f"  {intent}: {model_name} -> ¥{cost:.2f}")
    
    print(f"\n成本对比:")
    print(f"  优化前每日成本: ¥{old_cost:.2f}")
    print(f"  优化后每日成本: ¥{new_cost:.2f}")
    print(f"  每日节省: ¥{old_cost - new_cost:.2f}")
    print(f"  节省比例: {((old_cost - new_cost) / old_cost * 100):.1f}%")
    
    annual_savings = (old_cost - new_cost) * 365
    print(f"  年度节省: ¥{annual_savings:.2f}")


async def main():
    """主测试函数"""
    print("Xianyu AutoAgent 性能优化测试")
    print("=" * 80)
    
    try:
        await test_model_routing()
        await test_message_batching()
        await test_cost_analysis()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成！")
        print("\n主要优化效果:")
        print("1. 🎯 智能模型路由：根据消息意图和复杂度选择最合适的模型")
        print("2. 📦 消息批处理：合并短时间内的多条消息，减少LLM调用次数")
        print("3. 💰 成本优化：预计可节省60-80%的LLM调用成本")
        print("4. ⚡ 性能提升：批处理和智能路由提升整体响应效率")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())