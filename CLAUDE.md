# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# macOS/Linux - Automated setup
./setup.sh

# Windows - Automated setup
setup.bat

# Manual setup
python -m venv venv
source venv/bin/activate  # macOS/Linux: venv/bin/activate, Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Start with launcher script (recommended)
./start.sh              # macOS/Linux
start.bat               # Windows

# Manual start
source venv/bin/activate
python app.py

# Application runs on http://127.0.0.1:5000/
```

### Testing and Validation
```bash
# Test Google Cloud credentials
python test_credentials.py

# Test Claude API with current model configuration
python translate_claude.py --test

# Get available Claude models
python claude_models.py

# Test token counting and cost estimation
python claude_token_counter.py
```

## Architecture Overview

这是一个基于 Flask + Socket.IO 的实时翻译应用，支持 JavaScript/JSON 文件的多语言翻译。核心特点是双引擎架构（Google/Claude）和实时费用预估。

### Core Components

1. **app.py** (12.6 KB) - Flask 主应用
   - Socket.IO 实时通信（`/test` namespace）
   - 路由: `/` (上传), `/translate` (处理), `/success` (结果)
   - API 端点: `/api/claude-models`, `/api/estimate-cost`
   - 使用 `eventlet` 异步模式支持 WebSocket

2. **translate.py** - Google Translate 引擎
   - 嵌套 JSON 结构处理，保留格式和占位符
   - 批处理机制（BATCH_SIZE=10）
   - 重试逻辑处理 API 临时错误
   - 进度回调支持实时更新

3. **translate_claude.py** - Claude API 翻译引擎
   - 支持所有 Claude 模型（**Sonnet 4.5**⭐, Sonnet 4, Opus 4, 3.5/3 系列）
   - 语言特定优化：
     - 大写规则（英语 title case，罗曼语系 lowercase）
     - 温度设置（繁体中文 0.05，默认 0.1）
     - 语言代码映射（zh-TW → zh-Hant）
   - 翻译质量验证（检测英文混入）
   - 集成高级配置系统（translation_config.py）

4. **claude_token_counter.py** - Token 计算和费用预估
   - 两种计算模式：
     - 快速估算：基于字符数和经验系数
     - API 精确计算：使用 `messages.count_tokens()` API
   - 2025年完整定价支持（**Sonnet 4.5**, Sonnet 4, Opus 4, 3.5/3 系列）
   - 语言特定输出倍数（英文 0.5x，德语 1.0x 等）
   - 批处理感知计算
   - 双币种显示（USD/CNY，汇率 7.3）

5. **claude_models.py** - 模型配置管理
   - 实时获取可用模型列表
   - 1小时缓存机制
   - API 可用性验证
   - 支持最新 **Sonnet 4.5** 和 Opus 4

6. **translation_config.py** (高级配置) - 翻译系统优化参数
   - 批处理配置：批次大小、延迟、重试策略
   - 语言特定设置：温度、验证强度、术语表
   - 质量检查规则：英文关键词检测、容忍率
   - 后处理规则：罗曼语系小写、保留大写词汇

7. **translation_postprocess.py** - 翻译后处理
   - 三级验证：strict（繁体中文）、moderate（罗曼语系）、light
   - 术语一致性检查
   - 罗曼语系自动小写处理（es, fr, it, pt）
   - 质量报告生成

8. **Frontend** (`templates/upload.html`)
   - 无框架纯 JavaScript + Socket.IO 客户端
   - Material Design 风格
   - 拖拽上传 + 智能语言搜索
   - 实时费用预估（显示 tokens/cost）
   - WebSocket 进度追踪

### Key Design Patterns

1. **双引擎架构**
   - 通过 `config.TRANSLATION_ENGINE` 切换（'google'/'claude'）
   - 运行时模型选择（用户可在 UI 选择 Claude 模型）
   - 共享的进度回调接口

2. **实时通信**
   - Socket.IO 命名空间 `/test`
   - 事件: `connect`, `disconnect`, `progress`
   - 进度数据: `{progress: 0-100, message: str, error?: str, complete?: bool}`

3. **批处理策略**
   - 默认 BATCH_SIZE=10（Google），BATCH_SIZE=5（Claude）
   - REQUEST_DELAY=1.0s 避免速率限制
   - 渐进式重试延迟 [1.0s, 2.0s, 4.0s]

4. **配置系统层次**
   ```
   config.py (基础配置)
   ├── TRANSLATION_ENGINE, CLAUDE_API_KEY, CLAUDE_MODEL
   ├── BATCH_SIZE, REQUEST_DELAY, MAX_RETRIES
   └── 被 translation_config.py 覆盖（如果存在）

   translation_config.py (高级配置，可选)
   ├── BATCH_CONFIG, TEMPERATURE_BY_LANGUAGE
   ├── VALIDATION_STRENGTH, TERM_GLOSSARY
   └── QUALITY_CHECK_RULES, POST_PROCESSING_RULES
   ```

5. **费用预估流程**
   ```
   用户上传文件 + 选择语言
   → POST /api/estimate-cost
   → count_tokens_for_translation (快速) 或 count_tokens_with_api (精确)
   → 返回 JSON: {estimated_input_tokens, estimated_output_tokens, total_cost_usd, total_cost_cny}
   → 前端显示费用明细
   ```

### Configuration Files

- **config.py**: 基础配置
  - `TRANSLATION_ENGINE`: 'google' | 'claude'
  - `CLAUDE_API_KEY`: 从环境变量或 .env 加载
  - `CLAUDE_MODEL`: 默认 'claude-3-5-sonnet-latest'
  - `BATCH_SIZE`, `REQUEST_DELAY`, `MAX_RETRIES`
  - Google credentials: `./serviceKey.json`

- **translation_config.py** (可选高级配置):
  - `BATCH_CONFIG`: 覆盖批处理参数
  - `TEMPERATURE_BY_LANGUAGE`: 语言特定温度
  - `LANGUAGE_CODE_MAPPING`: API 兼容性映射
  - `TERM_GLOSSARY`: 术语一致性保证
  - `VALIDATION_STRENGTH`: 输出验证级别

- **.env** (可选):
  ```
  SECRET_KEY=your-secret-key
  TRANSLATION_ENGINE=claude
  CLAUDE_API_KEY=sk-ant-...
  CLAUDE_MODEL=claude-3-5-sonnet-latest
  ```

### Critical Implementation Details

1. **Socket.IO 异步模式**
   - 使用 `eventlet` 而非 `threading`
   - 避免在翻译循环中使用 `time.sleep()`（会阻塞 eventlet）
   - 使用 `eventlet.sleep()` 或移除不必要延迟

2. **Claude API 模型选择**
   - 必须在 `translate_json_file_claude()` 调用时传递 `model` 参数
   - 模型从前端表单 `request.form.get("claude_model")` 获取
   - 每次 API 调用记录使用的模型：`logger.info(f"使用模型: {selected_model}")`

3. **翻译质量保证**
   - 繁体中文（zh-TW）最容易出错，需特别检查
   - 使用 `_contains_too_much_english()` 检测英文混入
   - 失败重试时增加延迟（`REQUEST_DELAY * 2`）
   - 最终失败时保留原文而非丢弃

4. **费用估算准确性**
   - 快速估算：单语言约 94%，多语言约 78% 准确
   - API 计算：输入 tokens 100% 准确，输出基于经验倍数
   - 输出倍数根据语言调整（见 `claude_token_counter.py` L110-135）

5. **文件处理**
   - 上传: `uploads/` 目录（临时存储）
   - 输出: `output/` 目录
   - 最终 ZIP: `output/translations_{filename}.zip`
   - 个别文件在打包后删除

### Model Deprecation Notice

⚠️ **重要通知**：根据 [Anthropic 官方废弃政策](https://docs.claude.com/en/docs/about-claude/model-deprecations)：
- **claude-3-5-sonnet-20241022** 已被废弃，将于 **2025年10月22日** 退役
- 官方推荐迁移到 **Claude Sonnet 4.5** (`claude-sonnet-4-5-20250929`)
- 本项目已完全移除废弃模型，默认使用最新模型

### Common Development Tasks

**添加新的 Claude 模型**:
1. 在 `claude_token_counter.py` 的 `CLAUDE_PRICING` 添加定价
2. 在 `claude_models.py` 的 `get_claude_models()` 和 `get_default_models()` 添加模型信息
3. 更新 `config.py` 的 `CLAUDE_MODELS` 列表
4. 更新 `templates/upload.html` 的 `loadDefaultModels()` 函数

**修改批处理参数**:
- 首选：创建 `translation_config.py` 并设置 `BATCH_CONFIG`
- 或修改 `config.py` 中的 `BATCH_SIZE`, `REQUEST_DELAY`, `MAX_RETRIES`

**优化特定语言翻译**:
1. 在 `translation_config.py` 添加 `TEMPERATURE_BY_LANGUAGE` 条目
2. 在 `VALIDATION_STRENGTH` 设置验证级别
3. 在 `TERM_GLOSSARY` 添加常用术语
4. 在 `translate_claude.py` 的 `capitalization_rules` 添加大写规则

**添加新的费用估算功能**:
- 修改 `claude_token_counter.py` 中的输出倍数（`output_multipliers`）
- 调整 API 计数逻辑（`count_tokens_with_api()`）
- 更新前端显示（`templates/upload.html` 中的 JavaScript）

### Important Constraints

1. **仅处理 .js 和 .json 文件**
   - `ALLOWED_EXTENSIONS = {"json", "js"}`
   - 前端和后端双重验证

2. **支持 193 种语言**
   - 通过 Google Translate API 获取
   - 使用 `@lru_cache` 缓存语言列表

3. **无测试框架**
   - 依赖手动测试脚本（`test_credentials.py`, `translate_claude.py --test`）
   - 考虑添加 pytest 时需新增 `tests/` 目录

4. **无前端构建工具**
   - 所有 CSS/JS 内嵌在 HTML 模板
   - 修改 UI 需直接编辑 `templates/*.html`

5. **Session 管理**
   - Flask session 用于跟踪上传状态
   - `SECRET_KEY` 必须配置用于 session 加密

### Security Considerations

- **永远不要提交**:
  - `serviceKey.json` (Google credentials)
  - `.env` 文件（包含 API keys）
  - `uploads/` 和 `output/` 中的临时文件

- **API Key 管理**:
  - 使用环境变量或 .env
  - macOS 可使用 Keychain（`keychain_config.py`）

### Known Issues and Workarounds

1. **繁体中文翻译混入英文**:
   - 问题：Claude 可能返回英文翻译
   - 解决：设置极低温度（0.05），严格验证，自动重试

2. **罗曼语系大写问题**:
   - 问题：Claude 可能使用 title case
   - 解决：后处理自动小写（除专有名词）

3. **Google API "User Rate Limit Exceeded"**:
   - 问题：未启用计费账号
   - 解决：查看 `BILLING_TROUBLESHOOTING.md`

4. **Socket.IO 连接断开**:
   - 问题：长时间翻译任务超时
   - 解决：使用 eventlet 模式，避免阻塞操作

### Documentation References

项目包含详细文档：
- `README.md`: 用户使用指南
- `API_USAGE_TIPS.md`: API 使用建议
- `BILLING_TROUBLESHOOTING.md`: 计费问题排查
- `CLAUDE_API_SETUP.md`: Claude API 设置
- `CREATE_NEW_PROJECT.md`: 创建新项目指南

官方文档：
- [Claude Models](https://docs.claude.com/en/docs/about-claude/models)
- [Model Deprecations](https://docs.claude.com/en/docs/about-claude/model-deprecations)
- [API Documentation](https://docs.claude.com/en/api)

### Dependencies

关键依赖（见 `requirements.txt`）：
- Flask 3.1+ 和 Flask-SocketIO 5.5+
- google-cloud-translate 3.20+
- anthropic 0.39+ (Claude API)
- eventlet 0.40+ (异步支持)
- python-dotenv 1.0+ (环境变量)

### Development Notes

- **始终使用中文回复** (来自用户全局配置)
- 代码中英文注释混用，但用户文档全部中文
- 提交信息使用中文
- 最近提交主要优化了 Claude 翻译的首字母大写和语言混乱问题
