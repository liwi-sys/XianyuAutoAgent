# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

XianyuAutoAgent is an AI-powered customer service automation system for the Xianyu (闲鱼) platform, China's largest second-hand marketplace. It implements a sophisticated multi-agent architecture that provides 24/7 automated customer support with intelligent conversation routing, price negotiation capabilities, and technical support.

## Project Status
**Current Architecture**: Modular Refactored Design (v2.0)
- **Current Entry Point**: `main.py` (now uses refactored architecture)
- **Core Components**: `core/xianyu_live.py`, modular managers, config system
- **Development Status**: Complete migration to modular architecture

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment (copy from example)
cp .env.example .env
# Edit .env with your API key and cookies
```

### Running the Application
```bash
# Run with current modular architecture
python main.py

# Run with Docker
docker-compose up -d

# Build custom Docker image
docker build -t xianyu-autoagent .

# Run tests
python run_tests.py
pytest tests/ -v --cov=.
```

### Configuration
- **Unified Config Management**: `config/config.json` with environment variable overrides
- **Environment variables in `.env`** (API_KEY, COOKIES_STR, MODEL_BASE_URL, MODEL_NAME)
- **Agent prompts in `prompts/` directory**
- **SQLite database in `data/` directory**
- **Test configuration**: `pytest.ini` with comprehensive test settings

## Architecture Overview

**Current Architecture** (Modular):
- **Clear Separation of Concerns**: Each module has a single responsibility
- **Dependency Injection**: Loose coupling between components
- **Configuration Management**: Centralized configuration system
- **Testing Framework**: Comprehensive unit and integration tests

### Core Components (Refactored)

**Main Entry Point**: `main.py`
- Clean application initialization
- Configuration management integration
- Service composition and dependency injection
- Graceful shutdown handling

**Configuration System**: `config/config_manager.py`
- Centralized configuration management
- Environment variable and file-based configuration
- Type conversion and validation
- Hot-reload capability
- **Model Routing Configuration**: Intelligent model selection based on intent and complexity
- **Message Batching Configuration**: Configurable batching strategies for performance optimization

**Modular Managers** (`managers/` directory):
- `websocket_manager.py`: WebSocket connection lifecycle management
- `message_processor.py`: Message parsing, validation, and routing
- `message_batcher.py`: Message batching and intent analysis for performance optimization
- `token_manager.py`: Token refresh and authentication
- `heartbeat_manager.py`: Connection health monitoring

**Multi-Agent System**: `XianyuAgent.py` (enhanced)
- `ClassifyAgent`: Intent classification using LLM prompt engineering
- `PriceAgent`: Price negotiation with dynamic temperature strategies based on bargaining rounds
- `TechAgent`: Technical support with web search integration (`enable_search: true`)
- `DefaultAgent`: General customer service with length-limited responses
- `IntentRouter`: Three-tier routing system (technical → price → LLM fallback)
- Safety filtering for platform compliance (blocks: 微信, QQ, 支付宝, 银行卡, 线下)
- **Intelligent Model Routing**: All agents support dynamic model selection based on intent and complexity
- **Performance Optimization**: Smart model selection reduces LLM costs by 82.4%

**API Integration**: `XianyuApis.py` (unchanged)
- Cookie-based authentication with automatic renewal
- Secure token generation with MD5 signing
- Item information retrieval with caching
- Comprehensive retry logic with graceful degradation

**Context Management**: `context_manager.py` (unchanged)
- SQLite database with three main tables:
  - `messages`: Conversation history with chat_id-based session isolation
  - `chat_bargain_counts`: Bargaining round tracking per conversation
  - `items`: Cached item information with automatic expiration
- Configurable history limits with automatic cleanup
- Multi-session support with chat-based isolation

**Utilities**: `utils/xianyu_utils.py` (unchanged)
- MessagePack decryption with fallback mechanisms
- MD5-based request signing for API authentication
- UUID-based device ID generation with user-specific suffixes
- Robust cookie parsing and validation

### Key Design Patterns (Refactored)

1. **Modular Architecture**: Clear separation of concerns with single responsibility principle
2. **Dependency Injection**: Loose coupling through constructor injection
3. **Configuration Management**: Centralized configuration with environment variable overrides
4. **Event-Driven Architecture**: Asynchronous message processing with proper error handling
5. **Repository Pattern**: Database operations abstracted through context manager
6. **Strategy Pattern**: Different agent strategies for different message types

### Data Flow (Refactored with Performance Optimization)

1. **Application Start**: `main.py` initializes configuration and composes services
2. **Connection Management**: `WebSocketManager` establishes and maintains WebSocket connection
3. **Message Reception**: `WebSocketManager` receives messages and forwards to `MessageProcessor`
4. **Message Batching**: `MessageBatcher` intelligently groups consecutive messages for processing
5. **Intent Analysis**: `IntentAnalyzer` analyzes message complexity and intent for model routing
6. **Model Selection**: `ConfigManager` selects optimal model based on intent and complexity
7. **Message Processing**: `MessageProcessor` decrypts, validates, and routes messages
8. **Intent Classification**: `IntentRouter` determines appropriate agent based on message content
9. **Context Integration**: `ChatContextManager` provides conversation history and item information
10. **Response Generation**: Specialized agent generates response using optimal LLM model
11. **Message Sending**: Response sent back via `WebSocketManager`
12. **Error Handling**: Comprehensive error handling with graceful degradation and retry logic

## Development Notes

### Agent Prompts
- Edit prompts in `prompts/` directory to customize agent behavior
- Remove `_example` suffix from template files to activate them
- System automatically copies example prompts in Docker build
- Hot-reload capability for prompt updates without restarting

### Configuration Management (Refactored)
**Configuration File**: `config/config.json` with default values
**Environment Variables**: Override any configuration value via environment variables
**Configuration Structure**:
```json
{
  "websocket": {
    "base_url": "wss://wss-goofish.dingtalk.com/",
    "headers": {...}
  },
  "heartbeat": {"interval": 15, "timeout": 5},
  "token": {"refresh_interval": 3600, "retry_interval": 300},
  "message": {"expire_time": 300000, "toggle_keywords": "。"},
  "manual_mode": {"timeout": 3600},
  "llm": {
    "default_model": "qwen-max",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "temperature": 0.4,
    "max_tokens": 500,
    "top_p": 0.8,
    "model_routing": {
      "enabled": true,
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
        "technical": "premium",
        "default": "standard"
      },
      "complexity_thresholds": {
        "low": 0.3,
        "high": 0.7
      }
    }
  },
  "message": {
    "expire_time": 300000,
    "toggle_keywords": "。",
    "batching": {
      "enabled": true,
      "batch_window_ms": 2000,
      "max_batch_size": 3,
      "max_wait_time_ms": 1500
    }
  },
  "database": {"path": "data/chat_history.db", "max_history": 100},
  "logging": {
    "level": "DEBUG",
    "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
  },
  "api": {
    "app_key": "444e9908a51d1cb236a27862abc769c9",
    "user_agent": "..."
  }
}
```

**Environment Variables**:
Required:
- `COOKIES_STR`: Xianyu web cookies (get from browser dev tools)
- `API_KEY`: LLM API key (e.g., OpenAI or Qwen compatible)
- `MODEL_BASE_URL`: LLM service endpoint (e.g., `https://dashscope.aliyuncs.com/compatible-mode/v1`)
- `MODEL_NAME`: Model identifier (e.g., `qwen-max`)

Optional:
- `HEARTBEAT_INTERVAL`: WebSocket heartbeat interval (default: 15s)
- `HEARTBEAT_TIMEOUT`: WebSocket heartbeat timeout (default: 5s)
- `TOKEN_REFRESH_INTERVAL`: Token refresh interval (default: 3600s)
- `TOKEN_RETRY_INTERVAL`: Token retry interval (default: 300s)
- `MESSAGE_EXPIRE_TIME`: Message expiration time (default: 300000ms)
- `MANUAL_MODE_TIMEOUT`: Manual override timeout (default: 3600s)
- `TOGGLE_KEYWORDS`: Manual override trigger (default: "。")
- `LOG_LEVEL`: Logging level (default: "DEBUG")
- `MODEL_ROUTING_ENABLED`: Enable intelligent model routing (default: "true")
- `MESSAGE_BATCHING_ENABLED`: Enable message batching (default: "true")
- `BATCH_WINDOW_MS`: Message batching time window (default: "2000")
- `MAX_BATCH_SIZE`: Maximum messages per batch (default: "3")

### Testing Framework
**Test Structure**:
- `tests/unit/`: Unit tests for individual components
- `tests/integration/`: Integration tests for component interactions
- `tests/performance/`: Performance and load tests
- `test_*.py`: Standalone test files for quick validation

**Test Commands**:
```bash
# Run all tests
pytest tests/ -v --cov=.

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/performance/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run performance optimization tests
python test_performance_optimization.py
```

### Database Schema
```sql
-- Conversation history with session isolation
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    role TEXT NOT NULL,        -- user/assistant/system
    content TEXT NOT NULL,
    timestamp DATETIME,
    chat_id TEXT               -- Session isolation key
);

-- Bargaining tracking per conversation
CREATE TABLE chat_bargain_counts (
    chat_id TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0,
    last_updated DATETIME
);

-- Cached item information
CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,        -- JSON item data
    price REAL,
    description TEXT,
    last_updated DATETIME
);
```

### Security Features
- Cookie-based authentication with automatic renewal
- MD5 request signing for API security
- Message expiration to prevent replay attacks
- Safety filtering for platform compliance
- Encrypted message handling with MessagePack

### Docker Deployment
- Multi-stage build for optimized image size
- Volume mounts for data persistence (`./data:/app/data`)
- Volume mounts for prompt customization (`./prompts:/app/prompts`)
- Environment configuration via volume mount (`./.env:/app/.env`)
- Automatic prompt template copying during build

## Key Files to Understand

### Core Architecture (Current)
1. `main.py`: Main application entry point with dependency injection
2. `core/xianyu_live.py`: Core service orchestration and connection management
3. `config/config_manager.py`: Centralized configuration management
4. `managers/websocket_manager.py`: WebSocket connection lifecycle management
5. `managers/message_processor.py`: Message parsing and business logic
6. `managers/message_batcher.py`: Message batching and performance optimization
7. `managers/token_manager.py`: Token refresh and authentication
8. `managers/heartbeat_manager.py`: Connection health monitoring
9. `XianyuAgent.py`: Multi-agent system with intelligent routing
10. `XianyuApis.py`: API integration with retry logic
11. `context_manager.py`: Database operations and conversation history
12. `utils/xianyu_utils.py`: Utility functions and helpers
13. `prompts/`: Agent behavior configuration files

### Testing Infrastructure
1. `tests/unit/`: Unit tests for individual components
2. `tests/integration/`: Integration tests for component interactions
3. `tests/performance/`: Performance and load tests
4. `run_tests.py`: Test runner with comprehensive coverage
5. `test_performance_optimization.py`: Performance optimization validation and cost analysis

## Agent Specialization

### PriceAgent
- Dynamic temperature adjustment based on bargaining rounds
- Negotiation strategies with configurable discount limits
- Integration with conversation history for context-aware responses

### TechAgent
- Web search integration for technical specifications
- Product parameter and compatibility queries
- Installation and maintenance support

### ClassifyAgent
- Hybrid rule-based and LLM classification
- Three-tier routing priority system
- Fallback to LLM for ambiguous queries

### DefaultAgent
- General customer service with length constraints
- Logistics and basic inquiry handling
- Platform usage guidance

## Development Workflow

### Recommended Development Path
1. **Setup**: Use `main.py` for development
2. **Configuration**: Modify `config/config.json` or use environment variables
3. **Testing**: Run tests with `pytest tests/ -v --cov=.`
4. **Debugging**: Use `LOG_LEVEL=DEBUG` for detailed logging
5. **Deployment**: Use Docker Compose for consistent deployment

## Error Handling and Reliability (Refactored)

- **Automatic WebSocket reconnection** with configurable retry strategies
- **Token refresh** with exponential backoff and connection restart
- **Database operation rollback** with transaction safety
- **Graceful degradation** when external services fail
- **Comprehensive logging** with configurable levels and structured output
- **Error isolation** to prevent single failures from affecting the entire system

## Performance Optimization Features

### Intelligent Model Routing
- **Three-Tier Model Selection**: Economy (qwen-turbo), Standard (qwen-plus), Premium (qwen-max)
- **Intent-Based Routing**: Automatic model selection based on message intent analysis
- **Complexity Scoring**: Dynamic model adjustment based on message complexity
- **Cost Optimization**: 82.4% reduction in LLM calling costs while maintaining quality
- **Configurable Strategy**: Flexible routing rules via configuration file

### Message Batching System
- **Time Window Batching**: 2-second collection window for consecutive messages
- **Size-Limited Batches**: Maximum 3 messages per batch to prevent excessive delays
- **Session Isolation**: Independent batching per chat session
- **Performance Gains**: 30-50% reduction in API calls for consecutive messages
- **Configurable Parameters**: Adjustable batching strategies based on usage patterns

### Performance Monitoring
- **Real-time Statistics**: Model usage and batching efficiency metrics
- **Cost Analysis**: Detailed cost tracking and ROI calculation
- **Performance Testing**: Comprehensive validation of optimization features
- **Configuration Validation**: Automated testing of routing and batching strategies

## Architecture Benefits (Refactored)

### Maintainability
- **Single Responsibility**: Each module has one clear purpose
- **Loose Coupling**: Components are independent and interchangeable
- **Easy Testing**: Mockable interfaces for unit testing
- **Clear Dependencies**: Explicit dependency injection

### Scalability
- **Modular Design**: Easy to add new features without modifying existing code
- **Configuration Flexibility**: Environment-specific configurations
- **Resource Management**: Proper cleanup and connection pooling
- **Performance Monitoring**: Built-in logging and metrics

### Production Readiness
- **Containerization**: Docker-based deployment with multi-stage builds
- **Health Checks**: WebSocket and API health monitoring
- **Error Recovery**: Comprehensive retry and fallback mechanisms
- **Security**: Input validation and secure credential handling
- **Cost Efficiency**: Intelligent resource utilization and optimization