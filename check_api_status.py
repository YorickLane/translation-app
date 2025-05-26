#!/usr/bin/env python3
"""
Google Translation API 状态检查工具
用于检查API是否从速率限制中恢复
"""

import os
import time
from google.cloud import translate_v2 as translate
from google.api_core.exceptions import TooManyRequests, GoogleAPIError

# 设置凭证
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./serviceKey.json"


def check_api_status():
    """检查API状态"""
    try:
        client = translate.Client()

        # 测试简单翻译
        test_text = "Hello"
        result = client.translate(test_text, target_language="zh")

        print("✅ API状态正常！")
        print(f"测试翻译: '{test_text}' -> '{result['translatedText']}'")
        return True

    except TooManyRequests:
        print("❌ 仍然遇到速率限制，请继续等待...")
        return False

    except GoogleAPIError as e:
        print(f"❌ API错误: {e}")
        return False

    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False


def monitor_api_recovery(check_interval=300):  # 5分钟检查一次
    """监控API恢复状态"""
    print("🔍 开始监控API状态...")
    print(f"每{check_interval//60}分钟检查一次")
    print("按 Ctrl+C 停止监控\n")

    attempt = 1

    try:
        while True:
            print(f"第{attempt}次检查 ({time.strftime('%H:%M:%S')})")

            if check_api_status():
                print("\n🎉 API已恢复正常！您现在可以开始翻译了。")
                print("\n建议操作:")
                print("1. 先用 test-small.json 测试")
                print("2. 然后逐个翻译分割后的文件")
                print("3. 每个文件间隔5-10分钟")
                break
            else:
                print(f"等待{check_interval//60}分钟后再次检查...\n")
                time.sleep(check_interval)

            attempt += 1

    except KeyboardInterrupt:
        print("\n👋 监控已停止")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # 只检查一次
        check_api_status()
    else:
        # 持续监控
        monitor_api_recovery()
