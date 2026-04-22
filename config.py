"""
翻译应用基础配置

Secrets 策略: 遵循 ~/claude-soul/protocols/secrets-management.md ——
  - OPENROUTER_API_KEY 从 shell env 读取（来源: ~/.config/secrets.env）
  - 本项目不使用 .env 文件，不调用 python-dotenv，不通过 Keychain
  - 从 terminal 启动应用以继承 shell env
"""

import os

# Flask session secret
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

# 翻译引擎: 'openrouter' (LLM 多 provider) 或 'google' (Google Translate)
TRANSLATION_ENGINE = os.environ.get("TRANSLATION_ENGINE", "openrouter")

# Google Cloud Translate 凭证（仅 google 引擎需要）
GOOGLE_APPLICATION_CREDENTIALS = "./serviceKey.json"

# OpenRouter API Key —— 走 shell env，来源 ~/.config/secrets.env
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# 默认 LLM 模型（见 llm_models.AVAILABLE_MODELS）
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "anthropic/claude-sonnet-4.6")

# 文件限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"json", "js"}

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
