#!/usr/bin/env python3
"""
使用Claude API进行翻译
作为Google Translation API的替代方案
"""

import os
import json
import time
import logging
import re
from anthropic import Anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL, BATCH_SIZE, REQUEST_DELAY, MAX_RETRIES
try:
    from translation_config import (
        TEMPERATURE_BY_LANGUAGE, 
        LANGUAGE_CODE_MAPPING,
        BATCH_CONFIG
    )
    from translation_postprocess import post_process_translation, validate_translation_quality
    USE_ADVANCED_CONFIG = True
except ImportError:
    USE_ADVANCED_CONFIG = False
    logger.warning("高级配置未找到，使用默认设置")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def clean_json_response(response_text):
    """清理和修复 Claude 返回的 JSON 响应

    处理常见的 JSON 格式问题：
    - 移除 markdown 代码块标记
    - 移除单行和多行注释
    - 清理多余的空白字符
    - 尝试修复常见的格式错误
    """
    import re

    # 保存原始响应用于日志
    original_text = response_text

    # 1. 移除 markdown 代码块
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # 移除第一行（```json 或 ```）和最后一行（```）
        if len(lines) > 2:
            response_text = "\n".join(lines[1:-1])

    # 2. 移除单行注释 // ...
    response_text = re.sub(r'//.*?$', '', response_text, flags=re.MULTILINE)

    # 3. 移除多行注释 /* ... */
    response_text = re.sub(r'/\*.*?\*/', '', response_text, flags=re.DOTALL)

    # 4. 清理多余的空白字符（保留字符串内的空白）
    # 这个比较复杂，暂时只清理行尾空白
    response_text = re.sub(r'[ \t]+$', '', response_text, flags=re.MULTILINE)

    # 5. 移除 BOM (Byte Order Mark)
    response_text = response_text.lstrip('\ufeff')

    # 6. 确保文本前后没有多余空白
    response_text = response_text.strip()

    return response_text


def _contains_too_much_english(translations):
    """检测翻译结果中是否包含过多英文"""
    import re
    
    english_pattern = re.compile(r'[A-Za-z]{3,}')  # 至少3个连续英文字母
    total_values = 0
    english_values = 0
    
    for key, value in translations.items():
        if isinstance(value, str):
            total_values += 1
            # 检查是否包含明显的英文单词
            if english_pattern.search(value):
                # 检查一些常见的英文UI词汇
                common_english_words = [
                    'Please', 'Enter', 'Select', 'Password', 'Login',
                    'Settings', 'Edit', 'Delete', 'Clear', 'Copy',
                    'Download', 'Upload', 'Cancel', 'Confirm', 'Save',
                    'verification', 'progress', 'merchant', 'payment'
                ]
                
                for word in common_english_words:
                    if word.lower() in value.lower():
                        english_values += 1
                        break
    
    # 如果超过20%的值包含英文，认为有问题
    if total_values > 0:
        english_ratio = english_values / total_values
        return english_ratio > 0.2
    
    return False


def translate_with_claude(texts, target_language="en", model=None):
    """使用Claude API翻译文本"""
    if not CLAUDE_API_KEY:
        raise ValueError("请设置CLAUDE_API_KEY环境变量")

    client = Anthropic(api_key=CLAUDE_API_KEY)
    
    # 使用传入的模型或默认模型
    selected_model = model or CLAUDE_MODEL
    
    # 处理语言代码映射
    if USE_ADVANCED_CONFIG and target_language in LANGUAGE_CODE_MAPPING:
        api_language_code = LANGUAGE_CODE_MAPPING[target_language]
        logger.info(f"语言代码映射: {target_language} -> {api_language_code}")
    else:
        api_language_code = target_language

    # 准备翻译提示
    target_lang_name = LANGUAGE_NAMES.get(api_language_code, api_language_code)

    # 构建JSON格式的输入
    json_input = json.dumps(texts, ensure_ascii=False, indent=2)

    # 语言特定的大写规则
    capitalization_rules = {
        "en": """- Use title case for UI elements and buttons (e.g., "Confirm", "Cancel", "Save")
- Use sentence case for longer phrases and messages
- Capitalize proper nouns and the first word of sentences""",
        
        "de": """- Capitalize all nouns (Substantive)
- Do NOT capitalize verbs, adjectives, or other parts of speech unless they start a sentence
- Examples: "speichern" (save), "Einstellungen" (settings), "Datei bearbeiten" (edit file)""",
        
        "es": """- Use lowercase for UI elements unless they start a sentence
- Examples: "confirmar", "cancelar", "guardar", "editar"
- Only capitalize proper nouns and sentence beginnings""",
        
        "fr": """- Use lowercase for UI elements unless they start a sentence
- Examples: "confirmer", "annuler", "enregistrer", "modifier"
- Only capitalize proper nouns and sentence beginnings""",
        
        "it": """- Use lowercase for UI elements unless they start a sentence
- Examples: "conferma", "annulla", "salva", "modifica"
- Only capitalize proper nouns and sentence beginnings""",
        
        "pt": """- Use lowercase for UI elements unless they start a sentence
- Examples: "confirmar", "cancelar", "salvar", "editar"
- Only capitalize proper nouns and sentence beginnings""",
        
        "zh-TW": """- 这是繁体中文，请确保使用繁体字而不是简体字
- 不要返回英文翻译，必须翻译成繁体中文
- 例如："确定" → "確定"，"取消" → "取消"，"保存" → "儲存" """,
        
        "zh-Hant": """- 这是繁体中文，请确保使用繁体字而不是简体字
- 不要返回英文翻译，必须翻译成繁体中文
- 例如："确定" → "確定"，"取消" → "取消"，"保存" → "儲存" """
    }
    
    # 获取特定语言的规则，如果没有则使用通用规则
    specific_rules = capitalization_rules.get(target_language, 
        "- Follow the standard capitalization rules for this language\n- Be consistent throughout the translation")

    prompt = f"""Please translate the following JSON content to {target_lang_name}.

CRITICAL REQUIREMENTS:
1. Keep the JSON structure exactly the same, only translate the values (not the keys)
2. NEVER return English translations for non-English target languages
3. You MUST translate to {target_lang_name} ({target_language})
4. Maintain any special formatting, placeholders (like {{{{0}}}}), or HTML tags

CAPITALIZATION RULES for {target_lang_name}:
{specific_rules}

JSON OUTPUT REQUIREMENTS:
- Output ONLY valid JSON, no additional text or explanation
- Do NOT add comments (// or /* */)
- Do NOT wrap in markdown code blocks (```json)
- Ensure all strings are properly escaped
- Use double quotes for all strings (not single quotes)
- Do NOT add trailing commas

Input JSON:
{json_input}

Output the translated JSON only. Remember: translate to {target_lang_name}, NOT English!"""

    try:
        # 调用Claude API
        logger.info(f"[Claude API] 发送请求到模型: {selected_model}")
        # 获取温度设置
        temperature = 0.1  # 默认值
        if USE_ADVANCED_CONFIG and target_language in TEMPERATURE_BY_LANGUAGE:
            temperature = TEMPERATURE_BY_LANGUAGE[target_language]
            logger.info(f"使用特定温度设置: {temperature} (语言: {target_language})")
        
        response = client.messages.create(
            model=selected_model,  # 使用选定的模型
            max_tokens=8192,  # 增加到8192以避免长翻译被截断
            temperature=temperature,  # 使用语言特定的温度
            messages=[{"role": "user", "content": prompt}],
        )
        logger.info(f"[Claude API] 成功收到响应，模型: {selected_model}")

        # 解析响应
        raw_response = response.content[0].text.strip()

        # 尝试解析JSON
        try:
            translated_data = json.loads(raw_response)

            # 应用后处理
            if USE_ADVANCED_CONFIG:
                translated_data = post_process_translation(translated_data, target_language)

            return translated_data

        except json.JSONDecodeError as e:
            # JSON 解析失败，尝试清理响应
            logger.warning(f"初始 JSON 解析失败，尝试清理响应...")
            logger.debug(f"原始响应前200字符: {raw_response[:200]}")

            try:
                cleaned_response = clean_json_response(raw_response)
                translated_data = json.loads(cleaned_response)

                logger.info("清理后的响应解析成功")

                # 应用后处理
                if USE_ADVANCED_CONFIG:
                    translated_data = post_process_translation(translated_data, target_language)

                return translated_data

            except json.JSONDecodeError as clean_error:
                # 清理后仍然失败，记录详细错误
                logger.error(f"清理后仍无法解析 JSON: {clean_error}")
                logger.error(f"清理后的响应前500字符: {cleaned_response[:500]}")
                logger.error(f"JSON 错误位置: 行 {clean_error.lineno}, 列 {clean_error.colno}")
                raise Exception(f"JSON 解析失败: {clean_error}")

    except Exception as e:
        logger.error(f"Claude API错误: {e}")
        raise


def translate_json_file_claude(source_file_path, target_language="en", progress_callback=None, model=None, output_dir="output"):
    """使用Claude翻译JSON文件

    Args:
        source_file_path: 源文件路径
        target_language: 目标语言代码
        progress_callback: 进度回调函数
        model: Claude 模型 ID
        output_dir: 输出目录（默认为 "output"）
    """
    # 使用传入的模型或默认模型
    selected_model = model or CLAUDE_MODEL
    logger.info(f"开始使用Claude翻译JSON文件到 {target_language}，使用模型: {selected_model}")
    print(f"[Claude API] 正在使用模型: {selected_model}")

    # 提取源文件基础名称（不含扩展名）
    source_base_name = os.path.splitext(os.path.basename(source_file_path))[0]

    with open(source_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_items = len(data)
    logger.info(f"文件包含 {total_items} 个项目")

    # 分批处理
    items = list(data.items())
    translated_data = {}
    failed_batches = []  # 记录失败的批次

    for i in range(0, total_items, BATCH_SIZE):
        batch_items = dict(items[i : i + BATCH_SIZE])
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"翻译批次 {batch_num}/{total_batches}")
        
        # 发送进度更新
        if progress_callback:
            progress = (i / total_items) * 100
            progress_callback(progress, f"翻译批次 {batch_num}/{total_batches}")

        try:
            # 翻译这一批，传递选定的模型
            translated_batch = translate_with_claude(batch_items, target_language, selected_model)
            translated_data.update(translated_batch)

            # 请求间隔
            if i + BATCH_SIZE < total_items:
                time.sleep(REQUEST_DELAY)

        except Exception as e:
            logger.error(f"批次 {batch_num} 翻译失败: {e}")
            # 重试机制
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                retry_count += 1
                logger.info(f"重试批次 {batch_num} (尝试 {retry_count}/{max_retries})")
                
                try:
                    time.sleep(REQUEST_DELAY * 2)  # 延长等待时间
                    translated_batch = translate_with_claude(batch_items, target_language, selected_model)
                    
                    # 验证翻译结果
                    if target_language != "en" and _contains_too_much_english(translated_batch):
                        logger.warning(f"批次 {batch_num} 包含过多英文，重试...")
                        continue
                    
                    translated_data.update(translated_batch)
                    break
                except Exception as retry_e:
                    logger.error(f"重试失败: {retry_e}")
                    if retry_count == max_retries:
                        # 最终失败，保留原文
                        logger.error(f"批次 {batch_num} 多次重试失败，保留原文")
                        failed_batches.append({
                            'batch_num': batch_num,
                            'error': str(e),
                            'item_count': len(batch_items)
                        })
                        translated_data.update(batch_items)

                        # 通知前端
                        if progress_callback:
                            progress_callback(
                                (i / total_items) * 100,
                                f"⚠️ 批次 {batch_num}/{total_batches} 翻译失败，已保留原文"
                            )

    # 保存结果（输出文件名包含源文件名，避免多文件翻译时的命名冲突）
    output_file_name = f"{source_base_name}_{target_language}.json"
    output_path = os.path.join(output_dir, output_file_name)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    logger.info(f"翻译完成: {output_file_name}")
    print(f"[Claude API] 翻译完成，使用的模型: {selected_model}")

    # 汇总失败信息
    if failed_batches:
        total_failed_items = sum(batch['item_count'] for batch in failed_batches)
        failure_summary = f"⚠️ {len(failed_batches)} 个批次失败（共 {total_failed_items} 项保留原文）"
        logger.warning(failure_summary)
        logger.warning(f"失败批次详情: {[b['batch_num'] for b in failed_batches]}")

        # 发送完成消息，包含失败信息
        if progress_callback:
            progress_callback(
                100,
                f"翻译完成 (模型: {selected_model}) - {failure_summary}"
            )
    else:
        # 发送完成消息，无失败
        if progress_callback:
            progress_callback(100, f"✅ 翻译完成 (模型: {selected_model})")

    return output_file_name


def translate_js_file_claude(source_file_path, target_language="en", progress_callback=None, model=None, output_dir="output"):
    """使用 Claude 翻译 JavaScript 语言文件

    Args:
        source_file_path: 源文件路径
        target_language: 目标语言代码
        progress_callback: 进度回调函数
        model: Claude 模型 ID
        output_dir: 输出目录（默认为 "output"）
    """
    # 使用传入的模型或默认模型
    selected_model = model or CLAUDE_MODEL
    logger.info(f"开始使用 Claude 翻译 JS 文件到 {target_language}，使用模型: {selected_model}")
    print(f"[Claude API] 正在使用模型: {selected_model}")

    # 提取源文件基础名称（不含扩展名）
    source_base_name = os.path.splitext(os.path.basename(source_file_path))[0]

    # 读取 JS 文件内容
    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    logger.info(f"文件内容预览: {content[:200]}...")

    # 解析 JS 文件中的键值对
    key_value_pairs = re.findall(
        r'(\'[^\']+\'|[^\s:]+):\s*(`.*?`|".*?"|\'.*?\')', content, re.DOTALL
    )

    if not key_value_pairs:
        raise ValueError("无法从 JS 文件中提取键值对，请检查文件格式")

    logger.info(f"找到 {len(key_value_pairs)} 个键值对")

    # 构建用于翻译的字典
    translation_dict = {}
    for key, value in key_value_pairs:
        clean_key = key.strip("'")
        clean_value = value.strip().strip("`\"'")
        if clean_value.strip():  # 只处理非空值
            translation_dict[clean_key] = clean_value

    total_items = len(translation_dict)
    logger.info(f"准备翻译 {total_items} 个项目")

    # 分批翻译（使用与 JSON 相同的批处理逻辑）
    items = list(translation_dict.items())
    translated_data = {}
    failed_batches = []

    for i in range(0, total_items, BATCH_SIZE):
        batch_items = dict(items[i : i + BATCH_SIZE])
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"翻译批次 {batch_num}/{total_batches}")

        # 发送进度更新
        if progress_callback:
            progress = (i / total_items) * 100
            progress_callback(progress, f"正在翻译 JS 文件: 批次 {batch_num}/{total_batches}")

        # 使用 Claude API 翻译批次
        max_retries = MAX_RETRIES
        retry_count = 0

        while retry_count <= max_retries:
            try:
                translated_batch = translate_with_claude(
                    batch_items, target_language, selected_model
                )
                translated_data.update(translated_batch)
                break

            except Exception as e:
                logger.error(f"批次 {batch_num} 翻译失败: {e}")

                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"重试批次 {batch_num} (尝试 {retry_count}/{max_retries})")
                    time.sleep(REQUEST_DELAY * 2)
                else:
                    # 最终失败，保留原文
                    logger.error(f"批次 {batch_num} 多次重试失败，保留原文")
                    failed_batches.append({
                        'batch_num': batch_num,
                        'error': str(e),
                        'item_count': len(batch_items)
                    })
                    translated_data.update(batch_items)

                    # 通知前端
                    if progress_callback:
                        progress_callback(
                            (i / total_items) * 100,
                            f"⚠️ 批次 {batch_num}/{total_batches} 翻译失败，已保留原文"
                        )

        # 批次间延迟
        if i + BATCH_SIZE < total_items:
            time.sleep(REQUEST_DELAY)

    # 构建输出的 JS 文件内容
    translated_content = ["export default {\n"]
    for key, value in translated_data.items():
        # 转义引号
        escaped_value = value.replace('"', '\\"')
        translated_content.append(f'  "{key}": "{escaped_value}",\n')
    translated_content.append("};\n")

    # 保存结果（输出文件名包含源文件名，避免多文件翻译时的命名冲突）
    output_file_name = f"{source_base_name}_{target_language}.js"
    output_path = os.path.join(output_dir, output_file_name)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(translated_content))

    logger.info(f"JS 翻译完成: {output_file_name}")
    print(f"[Claude API] JS 翻译完成，使用的模型: {selected_model}")

    # 汇总失败信息
    if failed_batches:
        total_failed_items = sum(batch['item_count'] for batch in failed_batches)
        failure_summary = f"⚠️ {len(failed_batches)} 个批次失败（共 {total_failed_items} 项保留原文）"
        logger.warning(failure_summary)
        logger.warning(f"失败批次详情: {[b['batch_num'] for b in failed_batches]}")

        if progress_callback:
            progress_callback(100, f"翻译完成 (模型: {selected_model}) - {failure_summary}")
    else:
        if progress_callback:
            progress_callback(100, f"✅ 翻译完成 (模型: {selected_model})")

    return output_file_name


def test_claude_api():
    """测试Claude API是否正常工作"""
    try:
        # 显示当前使用的模型
        print(f"📊 当前使用的 Claude 模型: {CLAUDE_MODEL}")
        
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
