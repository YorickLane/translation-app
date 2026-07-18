# 更新日志 (CHANGELOG)

## [1.5.0] - 2026-07-18

### 模型升级
- 🤖 **质量档升级 Claude Sonnet 5**（`anthropic/claude-sonnet-5`，$2/$10 per MTok 首发优惠至 2026-08-31，之后 $3/$15，1M 上下文）
  - `ModelInfo` 新增 `supports_temperature` 目录标记；Sonnet 5 拒绝非默认 temperature/top_p/top_k（400），`llm_client` 按标记条件传参
  - 语言温度调优兜底改由 prompt 规则 + 验证重试承担（GPT-5.4 / Gemini 档不受影响）

### 安全修复
- 🔒 **ZIP 任意文件外泄**：`extract_zip_files` 重写为逐成员 realpath 校验 + 拒绝符号链接 + 只解压落在解压目录内的成员（不再 `extractall`）；附 ZIP 炸弹防护（解压总量 / 条目数 / 单成员压缩比上限）
- 🔒 **`/success` 反射 XSS + 开放跳转**：`zip_path` 用 `^/output/[\w.\-]+\.zip$` 白名单校验，挡 `javascript:` URI / 外链 / 路径穿越 / 换行注入
- 🔒 **前端 innerHTML XSS**：新增 `escapeHtml()`，转义所有拼入 innerHTML 的不可控字符串（文件名 / 后端错误 / ZIP 成员名经 warnings 回传）
- 🔒 **凭证保护**：`.gitignore` 保留裸 `*.json` 安全网（GCP 控制台下载的密钥默认随机命名、无关键词可匹配，只有 `*.json` 兜底能挡）；`SECRET_KEY` 删除可猜的硬编码默认，改 env 或随机值 + 警告；`FLASK_DEBUG` env 开关（默认 False，不再硬编码 `debug=True`）

### 修复
- 🐛 **LLM 引擎嵌套 JSON 静默损坏**：`translate_json_file_llm` 用 `_flatten`/`_rebuild` 递归处理任意嵌套 dict/list，完整保留结构 / 键序 / 非字符串叶子（此前嵌套值被序列化成字符串，结构被毁且无报错）
- 🐛 **后端错误对前端不可见**：`/translate` 改统一 JSON 契约（客户端错误 400 / 服务端错误 500 / 成功 200 带部分失败 `errors` 数组），不再 flash+redirect 导致前端静默等待至 10 分钟超时
- 🐛 **多客户端进度串台**：Socket.IO progress 事件定向到 `socket_sid`，不再全局广播（多用户同时翻译不再互相串进度 / 下载错文件）
- 🐛 **QA 复审 sidecar 未交付**：`<base>_<lang>.needs_review.json` 此前写出后随 `output_dir` 被清掉、对用户不可见，现纳入交付 ZIP（保持目录结构）
- 🐛 **费用预估**：数据源改用文件队列（拖拽 / 文件夹导入的文件不再误报"未选择"）、仅对 JSON 估算、多文件汇总；文件夹拖拽循环 `readEntries` 修复 >100 文件被截断
- 🐛 **空 `ai_model` / 无效引擎**：落回默认模型 + OpenRouter slug 与引擎白名单校验
- 🐛 **`js_locale` 转义不全**：`dump_js_locale` 改用 `json.dumps`（反斜杠 / 换行 / `</script>` 均安全，不再产出非法 JS）
- 🐛 **`/api/estimate-cost` 临时文件泄漏**：改 `try/finally` 保证清理

### 改进
- 🔧 **代码收敛（DRY）**：`_get_translate_client` 归一到 `translate.py` 单一来源（`app.py` 改 import）；英文关键词检测收敛到 `contains_english_keywords` 单一实现（批级重试闸复用，与逐项 QA 闸职责 / 粒度刻意分离并加注释说明）
- 🔧 **`safe_translate_text`**：深递归重试改写为有界循环（语义等价）
- 🔧 **费用估算准确性**：补 `zh` 输出倍数（原 zh / zh-TW / zh-CN 全落默认值 0.85，高估中文费用）
- 🔧 **前端网络**：Socket.IO 改相对连接 `io("/test")`（修 HTTPS / 反代下失效，去掉已废弃的 `document.domain`）；CDN 加 SRI（sha384）+ crossorigin
- 🔧 **依赖钉版**：`requirements{,-dev}.txt` 直接依赖全部 `>=` 改为 `==` 钉到实测版本，`pip check` 无冲突

### 技术更新
- ✅ **测试补强**：新增 `test_app_routes.py`（路由契约）/ `test_zip_security.py`（ZIP 穿越/炸弹）/ `test_nested_json.py`（嵌套展平重建）/ `test_cost_estimator.py`；扩展 `test_js_locale.py` / `test_sot_invariants.py`（单一来源不变量）——全套 159 passed
- 📝 更新 `CLAUDE.md` / `README.md` 反映 Sonnet 5、secrets SoT、`/translate` JSON 契约与安全约定

## [1.4.0] - 2025-07-04

### 新增功能
- 💰 **费用预估功能**：为 Claude API 添加实时 token 计算和费用预估
  - 创建 `claude_token_counter.py` 模块
  - 支持所有 Claude 模型的最新定价（2025年）
  - 显示美元和人民币费用
  - 提供详细的 token 使用预估
- 🔍 **API 端点**：新增 `/api/estimate-cost` 端点提供费用计算
- 🎨 **界面优化**：添加"预估费用"按钮（仅 Claude API 时显示）

### 修复
- 🐛 **前端表单问题**：修复选择翻译引擎和模型未正确传递到后端的问题
- 🔧 **HTML 实体编码**：修复 Google Translate 返回的 HTML 实体（如 `&#39;`）
- 📝 **文档命令**：更新所有文档中的 `python3` 命令为 `python`

### 改进
- 📊 **日志增强**：增加 Claude API 模型选择的详细日志记录
- 🎯 **用户体验**：选择 Claude API 时自动显示费用预估选项
- 💡 **模型推荐**：提供不同使用场景的模型选择建议

### 技术更新
- 添加 `html.unescape()` 处理 Google Translate 的输出
- 改进前端 FormData 构建逻辑
- 完善 Claude API 请求日志

## [1.3.0] - 2025-05-26

### 修复
- 🐛 **修复翻译完成后卡住问题**：解决了BrokenPipeError导致的页面卡顿
- 🔧 **优化表单提交流程**：改为AJAX异步提交，避免Socket.IO连接中断

### 改进
- ⚡ **性能优化**：
  - 移除了批量处理的休息延迟，提升翻译速度
  - 对于660个项目，可节省约66秒的等待时间
- 🎯 **用户体验提升**：
  - 提交按钮显示"翻译中..."状态和旋转图标
  - 翻译完成后自动跳转到成功页面
  - 页面加载时自动重置进度条状态
- 🧹 **界面优化**：
  - 移除了成功页面无用的"刷新页面"按钮
  - 改进了进度显示的即时性

### 技术更新
- 使用Fetch API替代传统表单提交
- 添加了`/success`路由处理成功页面
- 通过Socket.IO发送完成信号和重定向URL
- 优化了错误处理机制

## [1.2.0] - 2025-05-26

### 新增功能
- 🎯 **详细进度追踪**：实现了项目级的翻译进度追踪
  - 显示当前翻译的具体键值对
  - 显示已完成项数和总项数
  - 实时更新翻译进度百分比
  - 为每种语言计算独立的进度范围

### 改进
- 📊 **进度显示优化**：
  - 添加了进度回调函数到所有翻译函数
  - 改进了Socket.IO进度消息格式
  - 提供更详细的状态信息

### 技术更新
- 修改了 `translate.py` 中的翻译函数，添加了 `progress_callback` 参数
- 更新了 `app.py` 中的进度处理逻辑
- 改进了多语言翻译时的进度计算算法

## [1.1.0] - 2025-05-26

### 修复
- 🐛 **移除文件大小限制**：删除了500项的文件大小限制
- 🔧 **优化API参数**：恢复正常的批处理大小和请求间隔
- 💰 **计费问题处理**：更新错误消息，指向计费账号检查

### 新增
- 📚 **文档完善**：
  - 添加了 `BILLING_TROUBLESHOOTING.md` 计费问题排查指南
  - 添加了 `CLAUDE_API_SETUP.md` Claude API使用指南
  - 添加了 `CREATE_NEW_PROJECT.md` 新项目创建指南
  - 添加了 `API_USAGE_TIPS.md` API使用建议

### 功能
- 🤖 **Claude API支持**：添加了使用Claude API作为翻译引擎的选项
- 🔍 **API状态检查**：添加了 `check_api_status.py` 工具
- ✂️ **文件分割工具**：添加了 `split_json.py` 用于分割大文件

## [1.0.0] - 2025-05-25

### 初始发布
- 🎯 **核心功能**：
  - 支持JavaScript和JSON文件翻译
  - 使用Google Cloud Translation API
  - 支持193种语言
  - 批量翻译和ZIP打包下载

- 🎨 **用户界面**：
  - 现代化Material Design界面
  - 拖拽上传支持
  - 智能语言搜索
  - 常用语言快选
  - 响应式设计

- 🚀 **性能特性**：
  - Socket.IO实时进度显示
  - 语言列表缓存
  - 异步处理
  - 错误重试机制 