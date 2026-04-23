# 翻译工具 (Translation Utility)

## 概述
这是一个基于 Flask 的翻译应用，专门用于自动翻译 JavaScript 和 JSON 文件中的语言字符串。支持 **Google Cloud Translation API** 和 **OpenRouter AI（Claude / GPT / Gemini 3 档模型）** 双引擎，使用 structured output (json_schema) 保证返回有效 JSON，提供实时费用预估功能。

## 功能特性
- 🎯 **智能文件上传**：支持拖拽和点击上传，实时文件验证
- 🌍 **多语言支持**：Google Translate 全量语言（当前约 195 种，会随 Google 变动），智能搜索和常用语言快选；无 Google 凭证时降级到 20 种常用语言
- 🔍 **模糊搜索**：支持中文、英文、语言代码的模糊匹配
- 📱 **响应式设计**：完美适配桌面端和移动端
- ⚡ **实时进度**：Socket.IO实时显示翻译进度，精确到每个键值对
- 📊 **详细进度反馈**：显示当前翻译的具体项目和完成百分比
- 🚀 **异步处理**：AJAX提交，避免页面卡顿，流畅的用户体验
- 📦 **批量输出**：一键下载包含所有语言的ZIP文件
- 🎨 **现代化UI**：Material Design风格，优雅的动画效果
- 💰 **费用预估**：AI 翻译实时字符估算和费用预估（支持美元/人民币）
- 🤖 **多引擎支持**：Google Translate API 和 OpenRouter AI（3 档模型：Claude Sonnet 4.6 / GPT-5.4 / Gemini Flash Lite）
- 🚀 **用户体验**：智能表单验证，一键操作

## 系统要求
- Python 3.8+ (推荐 Python 3.10+)
- Google Cloud Translation API 凭证 **或** OpenRouter API Key
- 稳定的网络连接（国内访问 openrouter.ai 建议挂代理）

### OpenRouter API Key 配置（secrets SoT 模式）

本项目**不使用** `.env` 文件管理 secrets。配置方式：

```bash
# 1. 创建或编辑 ~/.config/secrets.env（chmod 600，不进 git）
echo 'export OPENROUTER_API_KEY="sk-or-v1-..."' >> ~/.config/secrets.env

# 2. ~/.zshrc 末尾加入（已加过可跳）
echo '[ -f ~/.config/secrets.env ] && source ~/.config/secrets.env' >> ~/.zshrc

# 3. 重新 source 或开新 terminal
source ~/.zshrc

# 4. 验证
echo ${OPENROUTER_API_KEY:0:12}  # 应输出 "sk-or-v1-xxx"
```

**必须从 terminal 启动 `python app.py`**（不要 Dock / Spotlight），GUI 启动不继承 shell env。

## 🚀 快速开始

### 方法一：一键安装（推荐）

**macOS/Linux:**
```bash
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

### 方法二：手动安装

#### 1. 环境准备
确保您的系统已安装Python 3.8+：
```bash
python --version
```

#### 2. 创建虚拟环境（推荐）
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

#### 3. 安装依赖包
```bash
pip install -r requirements.txt
```

#### 4. 配置凭证（至少一个）

**OpenRouter（推荐，LLM 主引擎）** — 见上方「OpenRouter API Key 配置」节

**Google Cloud Translation（可选 — 提供完整语言列表 + Google 引擎回退）**:
1. 在 Google Cloud Console 创建项目
2. 启用 Cloud Translation API
3. 创建 service account 并授予 `roles/cloudtranslate.user` role
4. 下载 JSON key 文件，重命名为 `serviceKey.json` 放项目根目录

无 `serviceKey.json` 时：app 自动使用内置 20 种常用语言 fallback，Google 引擎不可用但 LLM 引擎正常。

#### 5. 验证配置
```bash
# Google 凭证（若有 serviceKey.json）
python -c "from google.cloud import translate_v2 as translate; c=translate.Client(); print(f'✅ 拉到 {len(c.get_languages())} 种语言')"

# OpenRouter
python translate_llm.py --test
```

`./setup.sh` 会在安装末尾自动跑这两项。

#### 6. 启动应用
```bash
# 方法一：使用启动脚本（推荐）
./start.sh          # macOS/Linux
start.bat           # Windows

# 方法二：手动启动
source venv/bin/activate  # 激活虚拟环境
python app.py            # 启动应用
```
应用将在 `http://127.0.0.1:5000/` 启动

## 📖 使用方法

### 1. 访问应用
在浏览器中打开 `http://127.0.0.1:5000/`

### 2. 上传文件
- **拖拽上传**：直接将 `.js` 或 `.json` 文件拖拽到上传区域
- **点击上传**：点击上传区域选择文件
- 支持文件格式：JavaScript (.js) 和 JSON (.json)
- 实时显示文件信息（文件名、大小）

### 3. 选择目标语言
#### 🚀 常用语言快选
- 预设10种常用语言：中文(简/繁)、英语、日语、韩语、法语、德语、西班牙语、俄语、阿拉伯语
- 点击语言标签即可快速选择/取消

#### 🔍 智能搜索
- 在搜索框中输入语言名称、中文名或语言代码
- 支持模糊匹配：例如输入"法语"、"French"或"fr"都能找到法语
- 实时显示搜索结果，最多显示10个匹配项
- 点击搜索结果即可选择语言

#### 📋 已选语言管理
- 实时显示已选择的语言数量
- 可视化展示所有已选语言
- 点击语言标签上的"×"可快速删除

### 4. 选择翻译引擎（可选）
- **OpenRouter AI**（默认，推荐）：3 档 AI 模型，统一 OpenAI 兼容 API，零 markup 透传 provider 价格
  - 质量档 ⭐：`anthropic/claude-sonnet-4.6` — $3/$15 per MTok（生产推荐）
  - 备选档 ✨：`openai/gpt-5.4` — $2.50/$15 per MTok（同价位替代）
  - 经济档 💰：`google/gemini-3.1-flash-lite-preview` — $0.25/$1.50 per MTok（比 Sonnet 便宜 12x）
- **Google Translate**：免费额度内无需付费，作为 fallback

### 5. 费用预估（仅限 OpenRouter 引擎）
- 上传文件并选择语言后，点击"预估费用"按钮
- 基于字符数估算，显示详细费用明细：
  - 输入/输出 tokens 数量
  - 各部分费用（美元/人民币）
  - 批处理信息
- 典型误差 20-30%（OpenRouter 不代理 count_tokens API，仅字符估算）

### 6. 开始翻译
- 选择文件和目标语言后，"开始翻译"按钮自动启用
- 点击按钮开始翻译过程
- 实时进度条显示翻译进度
- 详细进度信息显示：
  - 总体进度百分比
  - 当前翻译的语言
  - 正在翻译的具体键值对
  - 已完成项数/总项数
- Socket.IO实时通信确保进度准确更新

### 7. 下载结果
- 翻译完成后自动跳转到结果页面
- 大型下载按钮，支持一键下载ZIP压缩包
- ZIP文件包含所有目标语言的翻译版本
- 保持原始文件格式和结构

## ✨ 界面特性

### 🎨 现代化设计
- **渐变背景**：优雅的紫色渐变背景
- **卡片式布局**：圆角卡片设计，层次分明
- **动画效果**：流畅的hover动画和过渡效果
- **图标支持**：Font Awesome图标库，视觉效果更佳

### 📱 响应式适配
- **桌面端**：宽屏布局，充分利用屏幕空间
- **平板端**：适中布局，保持良好可读性
- **手机端**：紧凑布局，触摸友好的按钮大小

### 🔍 智能交互
- **拖拽上传**：支持文件拖拽，视觉反馈明确
- **实时搜索**：输入即搜索，无需等待
- **状态反馈**：按钮状态、选择状态实时更新
- **错误提示**：友好的错误信息和操作指导

### 🚀 性能优化
- **懒加载**：搜索结果按需显示
- **防抖处理**：避免频繁API调用
- **缓存机制**：语言列表本地缓存
- **异步处理**：非阻塞的用户界面，AJAX提交避免页面卡顿
- **进度回调**：翻译过程中实时更新进度，不影响性能
- **优化延迟**：移除不必要的休息时间，提升翻译速度

## 📁 项目结构
```
translation-app/
├── app.py                 # Flask主应用文件
├── translate.py           # Google Translate 引擎实现
├── config.py             # 配置文件
├── translate_llm.py      # OpenRouter AI 翻译模块（主引擎）
├── llm_client.py         # OpenRouter 客户端层（OpenAI SDK + json_schema）
├── cost_estimator.py     # 费用估算（字符数）
├── llm_models.py         # AI 模型目录（3 档：Claude/GPT/Gemini）
├── translation_config.py # 高级配置（批处理、温度、术语表）
├── translation_postprocess.py # 翻译后处理（大写、术语一致性）
├── split_json.py         # JSON文件分割工具
├── example.json          # 示例JSON文件用于测试
├── test-small.json       # 小型测试文件
├── requirements.txt      # Python依赖包列表
├── serviceKey.json       # Google Cloud 凭证（可选，见第 4 节）
├── setup.sh              # 一键安装脚本（macOS/Linux）
├── setup.bat             # 一键安装脚本（Windows）
├── start.sh              # 应用启动脚本（macOS/Linux）
├── start.bat             # 应用启动脚本（Windows）
├── API_USAGE_TIPS.md     # API使用建议文档
├── BILLING_TROUBLESHOOTING.md # Google Cloud 计费问题排查
├── CREATE_NEW_PROJECT.md # 创建新项目指南
├── templates/            # HTML模板文件
│   ├── upload.html       # 主上传页面（现代化UI）
│   └── success.html      # 翻译完成页面
├── uploads/              # 上传文件临时存储
├── output/               # 翻译结果输出目录
└── venv/                 # Python虚拟环境（自动创建）
```

## ⚠️ 注意事项

### 安全提醒
- **保护密钥文件**：不要将 `serviceKey.json` 提交到Git仓库
- **虚拟环境**：建议使用虚拟环境避免依赖冲突
- **API配额**：注意Google Translation API的使用配额和计费

### 常见问题
1. **模块未找到错误**：确保已激活虚拟环境并安装所有依赖
2. **认证错误**：检查 `serviceKey.json` 文件是否存在且有效
3. **API错误**：确认Google Cloud项目已启用Translation API
4. **界面显示异常**：确保浏览器支持现代CSS特性，建议使用Chrome/Firefox/Safari
5. **文件上传失败**：检查文件格式是否为.js或.json，文件大小是否合理
6. **"User Rate Limit Exceeded"错误**：通常是计费账号问题，请查看 `BILLING_TROUBLESHOOTING.md`

### 故障排除
如果遇到问题，请按以下步骤检查：
1. 确认Python版本 >= 3.8（推荐 3.10+）
2. 确认虚拟环境已激活
3. 确认所有依赖包已安装
4. 确认至少一个翻译引擎凭证就位（`$OPENROUTER_API_KEY` 或 `serviceKey.json`）
5. 若使用 Google 引擎：确认 Cloud Translation API 已启用 + 计费正常

### 🆘 更多帮助
- **API使用建议**：查看 `API_USAGE_TIPS.md`
- **Google 计费问题**：查看 `BILLING_TROUBLESHOOTING.md`
- **OpenRouter 文档**：[openrouter.ai/docs](https://openrouter.ai/docs)
- **创建新项目**：查看 `CREATE_NEW_PROJECT.md`

## 🔧 开发相关

### 贡献指南
欢迎提交Pull Request和Issue来改进这个项目。

### 许可证
[MIT License](LICENSE.md)

### 致谢
- Google Cloud Translation API
- Flask 和 Flask-SocketIO 贡献者
- 所有项目贡献者和用户


