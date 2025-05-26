import os

# Flask secret key for session management
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")

# 翻译引擎配置
# 可选值: 'google' 或 'claude'
TRANSLATION_ENGINE = os.environ.get("TRANSLATION_ENGINE", "google")

# Google Cloud配置
GOOGLE_APPLICATION_CREDENTIALS = "./serviceKey.json"

# Claude API配置
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

# 翻译配置
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {"json", "js"}

# 批处理配置
BATCH_SIZE = 10  # 每批处理的项目数
REQUEST_DELAY = 0.5  # 请求间隔（秒）
