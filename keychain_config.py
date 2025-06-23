"""
macOS Keychain 集成
用于安全地从 Keychain 获取 API 密钥
"""

import subprocess
import os

def get_keychain_password(account, service="translation-app"):
    """从 macOS Keychain 获取密码"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def load_keychain_secrets():
    """加载所有 Keychain 中的密钥到环境变量"""
    # 获取 Claude API Key
    claude_key = get_keychain_password("CLAUDE_API_KEY")
    if claude_key:
        os.environ["CLAUDE_API_KEY"] = claude_key
        print("✅ 已从 Keychain 加载 Claude API Key")
    
    # 可以添加更多密钥
    # google_key = get_keychain_password("GOOGLE_API_KEY")
    # if google_key:
    #     os.environ["GOOGLE_API_KEY"] = google_key

# 在导入时自动加载
if __name__ != "__main__":
    load_keychain_secrets()