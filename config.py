import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 尝试从 macOS Keychain 加载密钥（如果在 macOS 上）
try:
    import platform
    if platform.system() == "Darwin":  # macOS
        from keychain_config import load_keychain_secrets
        # Keychain 会自动加载密钥
except ImportError:
    pass

# Flask secret key for session management
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")

# 翻译引擎配置
# 可选值: 'google' 或 'claude'
TRANSLATION_ENGINE = os.environ.get("TRANSLATION_ENGINE", "google")

# Google Cloud配置
GOOGLE_APPLICATION_CREDENTIALS = "./serviceKey.json"

# Claude API配置
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-latest")  # Default model

# 可用的 Claude 模型列表
CLAUDE_MODELS = [
    {
        "id": "claude-3-5-sonnet-20241022",
        "name": "Claude 3.5 Sonnet",
        "description": "最新最强大的 Sonnet，推荐用于翻译"
    },
    {
        "id": "claude-3-5-haiku-20241022",
        "name": "Claude 3.5 Haiku",
        "description": "快速且智能，适合大量翻译任务"
    },
    {
        "id": "claude-3-opus-20240229",
        "name": "Claude 3 Opus",
        "description": "功能强大，适合复杂翻译"
    },
    {
        "id": "claude-3-haiku-20240307",
        "name": "Claude 3 Haiku",
        "description": "经济快速，适合简单翻译"
    },
    {
        "id": "claude-3-5-sonnet-latest",
        "name": "Claude 3.5 Sonnet (Latest)",
        "description": "始终使用最新版本的 Sonnet"
    }
]

# 翻译配置
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {"json", "js"}

# 批处理配置
BATCH_SIZE = 10  # 每批处理的项目数
REQUEST_DELAY = 0.5  # 请求间隔（秒）
