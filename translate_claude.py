#!/usr/bin/env python3
"""
使用Claude API进行翻译
作为Google Translation API的替代方案
"""

import os
import json
import time
import logging
from anthropic import Anthropic

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Claude API配置
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
BATCH_SIZE = 10  # 每批翻译的项目数
REQUEST_DELAY = 0.5  # 请求间隔

# 语言映射
LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
}


def translate_with_claude(texts, target_language="en"):
    """使用Claude API翻译文本"""
    if not CLAUDE_API_KEY:
        raise ValueError("请设置CLAUDE_API_KEY环境变量")

    client = Anthropic(api_key=CLAUDE_API_KEY)

    # 准备翻译提示
    target_lang_name = LANGUAGE_NAMES.get(target_language, target_language)

    # 构建JSON格式的输入
    json_input = json.dumps(texts, ensure_ascii=False, indent=2)

    prompt = f"""Please translate the following JSON content to {target_lang_name}. 
Keep the JSON structure exactly the same, only translate the values (not the keys).
Maintain any special formatting, placeholders (like {{0}}), or HTML tags.

Input JSON:
{json_input}

Output the translated JSON only, without any explanation."""

    try:
        # 调用Claude API
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # 使用更便宜的Haiku模型
            max_tokens=4096,
            temperature=0.3,  # 降低温度以获得更一致的翻译
            messages=[{"role": "user", "content": prompt}],
        )

        # 解析响应
        translated_json = response.content[0].text.strip()

        # 尝试解析JSON
        try:
            translated_data = json.loads(translated_json)
            return translated_data
        except json.JSONDecodeError:
            # 如果解析失败，尝试清理响应
            # 移除可能的markdown代码块标记
            if translated_json.startswith("```"):
                lines = translated_json.split("\n")
                translated_json = "\n".join(lines[1:-1])
                translated_data = json.loads(translated_json)
                return translated_data
            raise

    except Exception as e:
        logger.error(f"Claude API错误: {e}")
        raise


def translate_json_file_claude(source_file_path, target_language="en"):
    """使用Claude翻译JSON文件"""
    logger.info(f"开始使用Claude翻译JSON文件到 {target_language}")

    with open(source_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_items = len(data)
    logger.info(f"文件包含 {total_items} 个项目")

    # 分批处理
    items = list(data.items())
    translated_data = {}

    for i in range(0, total_items, BATCH_SIZE):
        batch_items = dict(items[i : i + BATCH_SIZE])
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"翻译批次 {batch_num}/{total_batches}")

        try:
            # 翻译这一批
            translated_batch = translate_with_claude(batch_items, target_language)
            translated_data.update(translated_batch)

            # 请求间隔
            if i + BATCH_SIZE < total_items:
                time.sleep(REQUEST_DELAY)

        except Exception as e:
            logger.error(f"批次 {batch_num} 翻译失败: {e}")
            # 保留原文
            translated_data.update(batch_items)

    # 保存结果
    output_file_name = f"{target_language}.json"
    output_path = os.path.join("output", output_file_name)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    logger.info(f"翻译完成: {output_file_name}")
    return output_file_name


def test_claude_api():
    """测试Claude API是否正常工作"""
    try:
        test_data = {"hello": "Hello", "world": "World"}
        result = translate_with_claude(test_data, "zh")
        print("✅ Claude API测试成功！")
        print(f"测试结果: {result}")
        return True
    except Exception as e:
        print(f"❌ Claude API测试失败: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_claude_api()
    else:
        print("使用方法:")
        print("  测试API: python translate_claude.py --test")
        print("  翻译文件: 在app.py中集成使用")
