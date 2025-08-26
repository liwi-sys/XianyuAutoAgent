# XianyuAutoAgent

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

XianyuAutoAgent 是一个为闲鱼平台打造的AI智能客服自动化系统，闲鱼是中国最大的二手商品交易平台。该系统采用先进的多智能体架构，提供24/7自动化客服支持，具备智能对话路由、价格协商和技术支持等功能。

## ✨ 核心功能

### 🤖 多智能体系统
- **ClassifyAgent**: 基于LLM提示工程的智能意图分类
- **PriceAgent**: 动态价格协商，支持自适应温度策略
- **TechAgent**: 技术支持，集成网络搜索功能
- **DefaultAgent**: 通用客服，限制回复长度的智能响应
- **IntentRouter**: 三层路由系统（技术 → 价格 → LLM回退）

### 🚀 性能优化
- **智能模型路由**: 通过智能模型选择降低LLM成本82.4%
- **消息批处理**: 对连续消息的API调用减少30-50%
- **实时监控**: 全面的性能指标和成本分析

### 🏗️ 系统架构
- **模块化设计**: 单一职责原则，清晰的关注点分离
- **依赖注入**: 组件间松耦合设计
- **配置管理**: 集中化配置，支持环境变量覆盖
- **事件驱动架构**: 异步消息处理，完善的错误处理机制

## 🛠️ 安装指南

### 系统要求
- Python 3.12 或更高版本
- pip 包管理器

### 快速开始
```bash
# 克隆仓库
git clone https://github.com/liwi-sys/XianyuAutoAgent.git
cd XianyuAutoAgent

# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env
# 编辑 .env 文件，填入您的API密钥和Cookie
```

### Docker 部署
```bash
# 构建镜像
docker build -t xianyu-autoagent .

# 使用 Docker Compose 启动
docker-compose up -d
```

## ⚙️ 配置说明

### 环境变量
基于 `.env.example` 创建 `.env` 文件：

```bash
# 必需配置
API_KEY="您的qwen-api密钥"
COOKIES_STR="您的闲鱼cookie字符串"

# 可选配置
MODEL_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME="qwen-max"
HEARTBEAT_INTERVAL="15"
LOG_LEVEL="DEBUG"
MODEL_ROUTING_ENABLED="true"
MESSAGE_BATCHING_ENABLED="true"
```

### 配置文件
系统使用 `config/config.json` 进行高级配置：

```json
{
  "llm": {
    "default_model": "qwen-max",
    "model_routing": {
      "enabled": true,
      "models": {
        "economy": "qwen-turbo",
        "standard": "qwen-plus", 
        "premium": "qwen-max"
      }
    }
  },
  "message": {
    "batching": {
      "enabled": true,
      "batch_window_ms": 2000,
      "max_batch_size": 3
    }
  }
}
```

## 🚀 使用说明

### 运行应用程序
```bash
# 启动应用
python main.py

# 运行测试
pytest tests/ -v --cov=.

# 运行性能优化测试
python test_performance_optimization.py
```

### 智能体定制
编辑 `prompts/` 目录中的提示词来自定义智能体行为：
- `prompts/classify_prompt.txt` - 意图分类提示词
- `prompts/price_prompt.txt` - 价格协商提示词  
- `prompts/tech_prompt.txt` - 技术支持提示词
- `prompts/default_prompt.txt` - 通用客服提示词

## 📊 性能指标

系统包含全面的性能监控功能：

- **模型使用统计**: 跟踪不同模型层级的使用情况
- **成本分析**: 实时成本跟踪和投资回报率计算
- **消息批处理效率**: 监控批处理性能收益
- **响应时间指标**: 跟踪智能体响应时间

## 🏗️ 项目结构

```
XianyuAutoAgent/
├── main.py                    # 主应用程序入口
├── core/
│   └── xianyu_live.py        # 核心服务编排
├── config/
│   ├── config.json           # 配置文件
│   └── config_manager.py     # 配置管理
├── managers/
│   ├── websocket_manager.py  # WebSocket连接管理
│   ├── message_processor.py  # 消息解析和路由
│   ├── message_batcher.py    # 消息批处理优化
│   ├── token_manager.py      # 令牌刷新和认证
│   └── heartbeat_manager.py # 连接健康监控
├── XianyuAgent.py            # 多智能体系统
├── XianyuApis.py             # API集成
├── context_manager.py        # 数据库操作
├── utils/
│   └── xianyu_utils.py       # 工具函数
├── prompts/                  # 智能体行为配置
├── tests/                    # 测试套件
├── data/                     # 数据库和存储
└── requirements.txt          # Python依赖
```

## 🧪 测试

### 运行测试
```bash
# 运行所有测试
pytest tests/ -v --cov=.

# 运行特定测试类别
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/performance/ -v

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

### 测试结构
- `tests/unit/` - 单元测试，针对单个组件
- `tests/integration/` - 集成测试，测试组件交互
- `tests/performance/` - 性能和负载测试

## 🔒 安全特性

- **Cookie认证**: 自动续期和安全令牌生成
- **MD5请求签名**: API安全性，请求完整性验证
- **消息过期**: 防止重放攻击
- **安全过滤**: 平台合规性内容过滤
- **加密通信**: MessagePack加密安全消息处理

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

### 开发指南
- 遵循现有的代码风格和模式
- 为新功能添加测试
- 根据需要更新文档
- 提交前确保所有测试通过

## 📄 许可证

本项目基于 GNU General Public License v3.0 许可 - 详情请查看 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- **Qwen (通义千问)**: 提供强大的大语言模型能力
- **Xianyu (闲鱼)**: 启发此自动化系统的平台
- **OpenAI**: 提供兼容的API接口
- **XianYuAutoAgent**: 参考了 https://github.com/shaxiu/XianyuAutoAgent

## 📞 技术支持

如果您遇到任何问题或有疑问：

1. 查看 [Issues](https://github.com/your-username/XianyuAutoAgent/issues) 页面
2. 创建包含详细信息的新问题
3. 加入我们的社区讨论

## 🔮 发展路线图

- [ ] Web仪表板，用于监控和配置
- [ ] 更多智能体专门化
- [ ] 多语言支持
- [ ] 高级分析和报告
- [ ] 可扩展的插件系统

---

**用 ❤️ 为闲鱼社区打造**