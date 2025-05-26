#!/usr/bin/env python3
"""
测试Google Cloud Translation API凭证
运行此脚本验证serviceKey.json是否正确配置
"""

import os
from google.cloud import translate_v2 as translate
from google.auth.exceptions import DefaultCredentialsError


def test_credentials():
    try:
        # 设置凭证文件路径
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./serviceKey.json"

        # 创建翻译客户端
        translate_client = translate.Client()

        # 测试获取支持的语言
        languages = translate_client.get_languages()

        print("✅ 凭证验证成功！")
        print(f"支持的语言数量: {len(languages)}")
        print("前5种语言:")
        for lang in languages[:5]:
            print(f"  - {lang['name']} ({lang['language']})")

        # 测试简单翻译
        result = translate_client.translate("Hello, World!", target_language="zh")
        print(f"\n测试翻译: 'Hello, World!' -> '{result['translatedText']}'")

    except DefaultCredentialsError:
        print("❌ 凭证文件未找到或无效")
        print("请确保serviceKey.json文件存在于项目根目录")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        print("请检查:")
        print("1. serviceKey.json文件是否存在")
        print("2. Google Cloud项目是否启用了Translation API")
        print("3. 服务账号是否有适当权限")


if __name__ == "__main__":
    test_credentials()
