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

# Application runs on http://127.0.0.1:5050/ (改自 5000 以避开 macOS AirPlay)
```

### Testing and Validation
```bash
# Test Google Cloud credentials (inline, 脚本已删除)
python -c "from google.cloud import translate_v2 as translate; c=translate.Client(); print(f'✅ {len(c.get_languages())} languages')"

# Test OpenRouter + default model
python translate_llm.py --test

# List available AI models (3 tiers: quality / alternative / economy)
python llm_models.py

# Estimate cost for a translation task
python cost_estimator.py uploads/your-file.json es,fr,de,ar,it,pt
```

## Architecture Overview

这是一个基于 Flask + Socket.IO 的实时翻译应用，支持 JavaScript/JSON 文件的多语言翻译。核心特点是双引擎架构（Google Translate / OpenRouter LLM）和实时费用预估。**LLM 引擎通过 OpenRouter 接入多 provider（Claude / GPT / Gemini），使用 structured output (`json_schema`) 保证返回有效 JSON，无需脆弱的 regex 清理。**

### Core Components

1. **app.py** (12.6 KB) - Flask 主应用
   - Socket.IO 实时通信（`/test` namespace）
   - 路由: `/` (上传), `/translate` (处理), `/success` (结果)
   - API 端点: `/api/claude-models`, `/api/estimate-cost`
   - 使用 `threading` 异步模式（stdlib，Miguel Grinberg 当前推荐姿势）

2. **translate.py** - Google Translate 引擎
   - 嵌套 JSON 结构处理，保留格式和占位符
   - 批处理机制（BATCH_SIZE=10）
   - 重试逻辑处理 API 临时错误
   - 进度回调支持实时更新

3. **translate_llm.py** - OpenRouter LLM 翻译引擎（替代旧 translate_claude.py）
   - 通过 `llm_client.py` 调 OpenRouter（OpenAI 兼容 API）
   - **使用 `response_format: json_schema` 结构化输出** —— 保证返回 `{"translations": [...]}` 合法 JSON，删除旧版 ~40 行 regex JSON 清理代码
   - 语言特定优化：
     - 大写规则（英语 title case，罗曼语系 lowercase，**阿拉伯语 N/A**）
     - 温度设置（繁体中文 0.05，默认 0.1）
     - 语言代码映射（zh-TW → zh-Hant）
   - 翻译质量验证（检测英文混入触发重试）
   - 集成高级配置系统（translation_config.py）

4. **llm_client.py** - OpenRouter 客户端层
   - `OpenAI(base_url="https://openrouter.ai/api/v1")` 单例 client
   - 注入 `HTTP-Referer` + `X-OpenRouter-Title` attribution headers
   - `translate_batch()` 封装 json_schema 请求
   - Fail-fast API key 缺失（指向 ~/.config/secrets.env 配置指引）

5. **cost_estimator.py** - 费用预估（替代旧 claude_token_counter.py）
   - 字符数估算（OpenRouter 不代理 `count_tokens` API，已移除 API 精确计算）
   - 多 provider 定价（Claude / GPT / Gemini 基于 llm_models.AVAILABLE_MODELS）
   - 语言特定输出倍数（英文 0.5x，德语 1.0x 等）
   - 典型误差 20-30%，UI 明确标注"估算值"

6. **llm_models.py** - AI 模型目录（替代旧 claude_models.py）
   - 硬编码 3 档模型（不做 runtime API 发现）：
     - 质量档: `anthropic/claude-sonnet-4.6` ⭐ ($3/$15 per MTok)
     - 备选档: `openai/gpt-5.4` ✨ ($2.50/$15)
     - 经济档: `google/gemini-3.1-flash-lite-preview` 💰 ($0.25/$1.50，比 Sonnet 便宜 12x)
   - 新增模型 = 改 AVAILABLE_MODELS 常量

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
   - 通过 `config.TRANSLATION_ENGINE` 切换（'google' / 'openrouter'）
   - 运行时 AI 模型选择（用户可在 UI 选择 3 档 AI 模型）
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
   ├── TRANSLATION_ENGINE, OPENROUTER_API_KEY, DEFAULT_MODEL
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

- **config.py**: 基础配置（遵循全局 secrets SoT —— 不用 .env 文件）
  - `TRANSLATION_ENGINE`: 'google' | 'openrouter'
  - `OPENROUTER_API_KEY`: 从 shell env 读取，来源 `~/.config/secrets.env`（详见 `~/claude-soul/protocols/secrets-management.md`）
  - `DEFAULT_MODEL`: 默认 `'anthropic/claude-sonnet-4.6'`
  - `BATCH_SIZE`, `REQUEST_DELAY`, `MAX_RETRIES`
  - Google credentials: `./serviceKey.json`

- **translation_config.py** (可选高级配置):
  - `BATCH_CONFIG`: 覆盖批处理参数
  - `TEMPERATURE_BY_LANGUAGE`: 语言特定温度
  - `LANGUAGE_CODE_MAPPING`: API 兼容性映射
  - `TERM_GLOSSARY`: 术语一致性保证
  - `VALIDATION_STRENGTH`: 输出验证级别

- **Secrets**（**不使用 .env 文件** —— 项目已采用全局 SoT）:
  ```bash
  # ~/.config/secrets.env (chmod 600, 不进任何 git)
  export OPENROUTER_API_KEY="sk-or-v1-..."

  # ~/.zshrc 末尾 source 该文件:
  [ -f ~/.config/secrets.env ] && source ~/.config/secrets.env
  ```
  必须**从 terminal** 启动 `python app.py`（不要从 Dock / Spotlight），保证 env 继承。详见 `~/claude-soul/protocols/secrets-management.md`。

### Critical Implementation Details

1. **Socket.IO 异步模式**
   - `async_mode='threading'`（`app.py:28`）走 Python stdlib 线程池
   - 对第三方 SDK（google-cloud / openai SDK）兼容性最好，无 monkey-patch 副作用
   - 本地单用户翻译场景足够；如未来扩展多用户 + 高并发 WebSocket，Miguel 推荐 `gevent`（非 eventlet，后者已 deprecated）
   - 参考：[Flask-SocketIO Discussion #2037](https://github.com/miguelgrinberg/Flask-SocketIO/discussions/2037)

2. **AI 模型选择**
   - 必须在 `translate_json_file_llm()` 调用时传递 `model` 参数（OpenRouter slug 如 `anthropic/claude-sonnet-4.6`）
   - 模型从前端表单 `request.form.get("ai_model")` 获取
   - 每次 API 调用记录使用的模型：`logger.info(f"[OpenRouter] 调用 {model}")`
   - 所有 3 档模型都需支持 `response_format: json_schema` —— Claude Sonnet 4.5+ / GPT-4o+ / Gemini 已确认支持

3. **翻译质量保证**
   - 繁体中文（zh-TW）最容易出错，需特别检查
   - 使用 `_contains_too_much_english()` 检测英文混入
   - 失败重试时增加延迟（`REQUEST_DELAY * 2`）
   - 最终失败时保留原文而非丢弃

4. **费用估算准确性**
   - 仅字符估算：OpenRouter 不代理 `count_tokens` API，无法精确算 tokens
   - 典型误差 20-30%（UI 明确标注"估算值"）
   - 输出倍数按语言调整（见 `cost_estimator.py` 的 `output_multipliers`）

5. **文件处理**
   - 上传: `uploads/` 目录（临时存储）
   - 输出: `output/` 目录
   - 最终 ZIP: `output/translations_{filename}.zip`
   - 个别文件在打包后删除

### Model Currency Notice（2026-04-22 校准）

- **Claude 当前生产推荐**: Sonnet 4.6 (`anthropic/claude-sonnet-4.6` 经 OR) / Opus 4.7
- **已变 legacy**: Sonnet 4.5 / Opus 4.5 / Opus 4.6（仍可用，有更优选）
- **Anthropic 直连付款卡问题**：本项目不再调 Anthropic 直连 SDK；全部走 OpenRouter 统一入口
- **OpenRouter 零加价** pass-through provider 原价（见 [openrouter.ai/pricing](https://openrouter.ai/pricing)）

### Common Development Tasks

**添加新的 AI 模型**:
1. 在 `llm_models.py` 的 `AVAILABLE_MODELS` 追加一条（含 id/name/tier/价格/context_length）
2. 更新 `static/js/upload.js` 的 `loadDefaultModels()` fallback 列表（同步 3 档）
3. 验证该模型支持 OpenRouter 的 `response_format: json_schema`（用 smoke test 跑一次）

**修改批处理参数**:
- 首选：创建 `translation_config.py` 并设置 `BATCH_CONFIG`
- 或修改 `config.py` 中的 `BATCH_SIZE`, `REQUEST_DELAY`, `MAX_RETRIES`

**优化特定语言翻译**:
1. 在 `translation_config.py` 添加 `TEMPERATURE_BY_LANGUAGE` 条目
2. 在 `VALIDATION_STRENGTH` 设置验证级别
3. 在 `TERM_GLOSSARY` 添加常用术语
4. 在 `translate_llm.py` 的 `capitalization_rules` 添加大写规则

**调整费用估算参数**:
- 修改 `cost_estimator.py` 的 `output_multipliers`（各语言 expansion factor）
- 更新 `llm_models.py` 的 `AVAILABLE_MODELS` 定价（来源：[openrouter.ai/pricing](https://openrouter.ai/pricing)）
- 前端显示逻辑在 `templates/upload.html` 内嵌 JS

### Important Constraints

1. **仅处理 .js 和 .json 文件**
   - `ALLOWED_EXTENSIONS = {"json", "js"}`
   - 前端和后端双重验证

2. **多语言支持**
   - 有 Google 凭证时通过 Translate API 拉取完整列表（当前约 195 种，会随 Google 变动）
   - 无凭证时降级到 `app.py` 内置的 `_FALLBACK_LANGUAGES`（20 种常用）
   - 使用 `@lru_cache` 缓存语言列表

3. **无测试框架**
   - 依赖手动验证（`python translate_llm.py --test` + `./setup.sh` 末尾 inline 凭证验证）
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
  - 本项目**不使用** `.env` 文件。走全局 secrets SoT：`~/.config/secrets.env` + shell env export
  - 详见 `~/claude-soul/protocols/secrets-management.md`

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
   - 解决：检查 Socket.IO 心跳参数（`ping_timeout` / `ping_interval`），确保翻译循环 yield 控制权

### Documentation References

项目包含详细文档：
- `README.md`: 用户使用指南
- `API_USAGE_TIPS.md`: API 使用建议
- `BILLING_TROUBLESHOOTING.md`: Google Cloud 计费问题排查
- `CREATE_NEW_PROJECT.md`: 创建新项目指南

官方文档：
- [Claude Models](https://docs.claude.com/en/docs/about-claude/models)
- [Model Deprecations](https://docs.claude.com/en/docs/about-claude/model-deprecations)
- [API Documentation](https://docs.claude.com/en/api)

### Dependencies

关键依赖（见 `requirements.txt`）：
- Flask 3.1+ 和 Flask-SocketIO 5.5+
- google-cloud-translate 3.20+
- **openai 1.50+**（OpenRouter 走 OpenAI 兼容层，替代 anthropic SDK）
- **httpx[socks]**（上海走 clash SOCKS 代理需要）
- async 模式：Flask-SocketIO `async_mode='threading'`（stdlib 线程池，不依赖 eventlet/gevent）
- 不再使用 python-dotenv（secrets.env + shell env 提供）

### Development Notes

- **始终使用中文回复** (来自用户全局配置)
- 代码中英文注释混用，但用户文档全部中文
- 提交信息使用中文
- 最近提交主要优化了 Claude 翻译的首字母大写和语言混乱问题
