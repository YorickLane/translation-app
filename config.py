import os

# Flask secret key for session management
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")
