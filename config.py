"""
翻译应用基础配置

Secrets 策略: 遵循 ~/claude-soul/protocols/secrets-management.md ——
  - OPENROUTER_API_KEY 从 shell env 读取（来源: ~/.config/secrets.env）
  - 本项目不使用 .env 文件，不调用 python-dotenv，不通过 Keychain
  - 从 terminal 启动应用以继承 shell env
"""

import os
import logging
import secrets

# Flask debug 开关 —— 由 env 控制，默认 False（生产安全）；开发者 export FLASK_DEBUG=1 开启
DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}

# Flask session secret —— 删除可猜的硬编码默认；env 未设时用随机值保证 session 加密仍可用
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("SECRET_KEY"):
    logging.warning("SECRET_KEY 未设，已生成临时随机值，重启后 session 失效")

# 翻译引擎: 'openrouter' (LLM 多 provider) 或 'google' (Google Translate)
TRANSLATION_ENGINE = os.environ.get("TRANSLATION_ENGINE", "openrouter")

# Google Cloud Translate 凭证（仅 google 引擎需要）
# 查找优先级 (google-cloud library 原生链):
#   1. GOOGLE_APPLICATION_CREDENTIALS env var (可从 ~/.config/secrets.env 设置)
#   2. gcloud ADC (`gcloud auth application-default login` 后
#      ~/.config/gcloud/application_default_credentials.json)
#   3. GCE / Cloud Run metadata server (云环境自动)
#   4. 项目根 fallback convention:
#      - google-credentials.json (2026-04-23 后推荐)
#      - serviceKey.json (legacy, 向后兼容保留)
GOOGLE_CREDENTIALS_FILENAMES = ("google-credentials.json", "serviceKey.json")

# OpenRouter API Key —— 走 shell env，来源 ~/.config/secrets.env
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# 默认 LLM 模型（见 llm_models.AVAILABLE_MODELS）
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "anthropic/claude-sonnet-5")

# 上传大小上限 —— 已接线为 Flask MAX_CONTENT_LENGTH（app.py）；>此值的上传返回 413。
# 50MB 容得下大 ZIP 多语言包（实测最大单包 ru.json ~79KB，远低于此）。
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
# 允许上传的扩展名（单源真相；app.py 从这里 import，勿在 app.py 另立副本）
ALLOWED_EXTENSIONS = {"json", "js", "zip"}

# 批处理默认值（可被 translation_config.BATCH_CONFIG 覆盖）
BATCH_SIZE = 3
REQUEST_DELAY = 1.0
MAX_RETRIES = 3

try:
    from translation_config import BATCH_CONFIG
    BATCH_SIZE = BATCH_CONFIG.get('size', BATCH_SIZE)
    REQUEST_DELAY = BATCH_CONFIG.get('request_delay', REQUEST_DELAY)
    MAX_RETRIES = BATCH_CONFIG.get('max_retries', MAX_RETRIES)
except ImportError:
    pass
