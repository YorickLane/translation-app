"""
LLM 翻译引擎 —— 基于 OpenRouter 结构化输出

相比旧版 translate_claude.py 的变化:
- 删除 clean_json_response() 及所有 regex JSON 清理（json_schema 保证有效 JSON）
- 删除 fragile markdown code block / 注释剥离逻辑
- 引入 llm_client 作为 provider-agnostic 客户端层
- 增加 ar (阿拉伯语) 的 capitalization 规则 (N/A)
- 保留所有原有的批处理、重试、进度回调、失败收集逻辑
"""

import os
import json
import time
import logging
import re

from llm_client import translate_batch
from config import BATCH_SIZE, REQUEST_DELAY, MAX_RETRIES, DEFAULT_MODEL

try:
    from translation_config import (
        TEMPERATURE_BY_LANGUAGE,
        LANGUAGE_CODE_MAPPING,
        BATCH_CONFIG,
    )
    from translation_postprocess import post_process_translation
    USE_ADVANCED_CONFIG = True
except ImportError:
    USE_ADVANCED_CONFIG = False

logger = logging.getLogger(__name__)


LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "zh-Hant": "Chinese (Traditional)",
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


CAPITALIZATION_RULES = {
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

    "ar": """- Arabic has no uppercase/lowercase concept
- Preserve the natural Arabic script (RTL, right-to-left)
- Use standard Modern Standard Arabic for UI elements
- Examples: "تأكيد" (confirm), "إلغاء" (cancel), "الإعدادات" (settings)""",

    "zh-TW": """- This is Traditional Chinese, use traditional characters (繁體字), NOT simplified
- NEVER return English; must translate to Traditional Chinese
- Examples: "确定" → "確定", "保存" → "儲存", "设置" → "設定" """,

    "zh-Hant": """- This is Traditional Chinese, use traditional characters (繁體字), NOT simplified
- NEVER return English; must translate to Traditional Chinese
- Examples: "确定" → "確定", "保存" → "儲存", "设置" → "設定" """,
}

GENERIC_RULE = (
    "- Follow standard capitalization rules for this language\n"
    "- Be consistent across all strings"
)


# ---------- English 混入检测（非英语目标触发重试） ----------

_ENGLISH_KEYWORDS = {
    'Please', 'Enter', 'Select', 'Password', 'Login',
    'Settings', 'Edit', 'Delete', 'Clear', 'Copy',
    'Download', 'Upload', 'Cancel', 'Confirm', 'Save',
    'verification', 'progress', 'merchant', 'payment',
}
_ENGLISH_PATTERN = re.compile(r'[A-Za-z]{3,}')
# 词边界匹配，避免把罗曼语系同源词（cancelar/confirmar/editar/copiar 等）误判为英文混入
_ENGLISH_KEYWORD_PATTERNS = [
    re.compile(rf'\b{re.escape(w)}\b', re.IGNORECASE) for w in _ENGLISH_KEYWORDS
]


def _contains_too_much_english(translations):
    """检测翻译结果中是否 >20% 的项目混入明显英文 UI 词。"""
    total = 0
    english_hit = 0
    for value in translations.values():
        if not isinstance(value, str):
            continue
        total += 1
        if _ENGLISH_PATTERN.search(value):
            for pattern in _ENGLISH_KEYWORD_PATTERNS:
                if pattern.search(value):
                    english_hit += 1
                    break
    return total > 0 and english_hit / total > 0.2


# ---------- 核心翻译函数（单批次） ----------

def translate_with_llm(texts, target_language, model):
    """翻译 {key: value} 字典，返回同 key 字典。

    只发送 values 给 LLM，翻译后和原 keys zip 回来 —— key 不会被错译。
    """
    # 语言代码映射（zh-TW → zh-Hant 等）
    api_lang = target_language
    if USE_ADVANCED_CONFIG and target_language in LANGUAGE_CODE_MAPPING:
        api_lang = LANGUAGE_CODE_MAPPING[target_language]

    target_lang_name = LANGUAGE_NAMES.get(api_lang, api_lang)
    original_keys = list(texts.keys())
    values_only = list(texts.values())

    # 温度：语言特定优先
    temperature = 0.1
    if USE_ADVANCED_CONFIG and target_language in TEMPERATURE_BY_LANGUAGE:
        temperature = TEMPERATURE_BY_LANGUAGE[target_language]

    cap_rule = CAPITALIZATION_RULES.get(target_language, GENERIC_RULE)

    translated_values = translate_batch(
        values=values_only,
        target_lang_name=target_lang_name,
        target_lang_code=target_language,
        model=model,
        temperature=temperature,
        capitalization_rule=cap_rule,
    )

    translated = dict(zip(original_keys, translated_values))

    if USE_ADVANCED_CONFIG:
        translated = post_process_translation(translated, target_language)

    return translated


# ---------- 动态批次分割 ----------

def _create_dynamic_batches(items, use_dynamic=True):
    """智能批次：按字符数动态分，兼容固定大小 fallback。"""
    if not use_dynamic or not USE_ADVANCED_CONFIG:
        return [dict(items[i:i + BATCH_SIZE]) for i in range(0, len(items), BATCH_SIZE)]

    max_chars = BATCH_CONFIG.get('max_chars_per_batch', 3000)
    min_size = BATCH_CONFIG.get('min_batch_size', 2)
    max_size = BATCH_CONFIG.get('max_batch_size', 25)

    batches = []
    current = {}
    current_chars = 0

    for key, value in items:
        item_chars = len(str(key)) + len(str(value))
        should_split = (
            len(current) >= max_size
            or (current_chars + item_chars > max_chars and len(current) >= min_size)
        )
        if should_split and current:
            batches.append(current)
            current = {}
            current_chars = 0
        current[key] = value
        current_chars += item_chars

    if current:
        batches.append(current)
    return batches


def _get_retry_delay(attempt):
    """指数退避或配置的渐进延迟。"""
    if USE_ADVANCED_CONFIG and 'retry_delays' in BATCH_CONFIG:
        delays = BATCH_CONFIG['retry_delays']
        return delays[min(attempt - 1, len(delays) - 1)]
    return REQUEST_DELAY * 2


# ---------- JSON 文件翻译 ----------

def translate_json_file_llm(
    source_file_path, target_language,
    progress_callback=None, model=None, output_dir="output",
):
    """翻译 JSON 语言包文件。"""
    selected_model = model or DEFAULT_MODEL
    logger.info(f"翻译 JSON → {target_language} 使用 {selected_model}")

    source_base = os.path.splitext(os.path.basename(source_file_path))[0]

    with open(source_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = list(data.items())
    total_items = len(items)
    use_dynamic = USE_ADVANCED_CONFIG and BATCH_CONFIG.get('dynamic_batching', False)
    batches = _create_dynamic_batches(items, use_dynamic)
    total_batches = len(batches)

    translated_data = {}
    failed_batches = []
    processed = 0
    max_retries = BATCH_CONFIG.get('max_retries', MAX_RETRIES) if USE_ADVANCED_CONFIG else MAX_RETRIES

    for batch_num, batch_items in enumerate(batches, 1):
        batch_size = len(batch_items)
        if progress_callback:
            progress_callback((processed / total_items) * 100,
                              f"批次 {batch_num}/{total_batches} ({batch_size} 项)")

        attempt = 0
        success = False
        while attempt <= max_retries and not success:
            try:
                translated = translate_with_llm(batch_items, target_language, selected_model)

                # 非英语目标：检测英文混入
                if target_language != "en" and _contains_too_much_english(translated):
                    attempt += 1
                    logger.warning(f"批次 {batch_num} 英文混入过多，重试 {attempt}/{max_retries}")
                    if attempt > max_retries:
                        # 保留最后一次结果（部分翻译总比无翻译好）
                        translated_data.update(translated)
                        processed += batch_size
                        break
                    time.sleep(_get_retry_delay(attempt))
                    continue

                translated_data.update(translated)
                processed += batch_size
                success = True

            except Exception as e:
                attempt += 1
                logger.error(f"批次 {batch_num} 失败 ({attempt}/{max_retries}): {e}")
                if attempt > max_retries:
                    failed_batches.append({
                        'batch_num': batch_num, 'error': str(e), 'item_count': batch_size,
                    })
                    translated_data.update(batch_items)  # 保留原文
                    processed += batch_size
                    if progress_callback:
                        progress_callback((processed / total_items) * 100,
                                          f"⚠️ 批次 {batch_num} 失败，保留原文")
                    break
                time.sleep(_get_retry_delay(attempt))

        # 批次间延迟
        if batch_num < total_batches:
            delay = BATCH_CONFIG.get('request_delay', REQUEST_DELAY) if USE_ADVANCED_CONFIG else REQUEST_DELAY
            time.sleep(delay)

    # 保存
    output_file = f"{source_base}_{target_language}.json"
    output_path = os.path.join(output_dir, output_file)
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    _report_completion(progress_callback, selected_model, failed_batches)
    return output_file


# ---------- JS 文件翻译 ----------

_JS_KV_PATTERN = re.compile(
    r'(\'[^\']+\'|[^\s:]+):\s*(`.*?`|".*?"|\'.*?\')', re.DOTALL,
)


def translate_js_file_llm(
    source_file_path, target_language,
    progress_callback=None, model=None, output_dir="output",
):
    """翻译 `export default {...}` 形式的 JS 语言包。"""
    selected_model = model or DEFAULT_MODEL
    logger.info(f"翻译 JS → {target_language} 使用 {selected_model}")

    source_base = os.path.splitext(os.path.basename(source_file_path))[0]

    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pairs = _JS_KV_PATTERN.findall(content)
    if not pairs:
        raise ValueError("无法从 JS 文件提取键值对，请检查格式")

    translation_dict = {}
    for k, v in pairs:
        clean_k = k.strip("'")
        clean_v = v.strip().strip("`\"'")
        if clean_v.strip():
            translation_dict[clean_k] = clean_v

    items = list(translation_dict.items())
    total_items = len(translation_dict)
    total_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE

    translated_data = {}
    failed_batches = []

    for i in range(0, total_items, BATCH_SIZE):
        batch_items = dict(items[i:i + BATCH_SIZE])
        batch_num = i // BATCH_SIZE + 1

        if progress_callback:
            progress_callback((i / total_items) * 100, f"JS 批次 {batch_num}/{total_batches}")

        attempt = 0
        while attempt <= MAX_RETRIES:
            try:
                translated = translate_with_llm(batch_items, target_language, selected_model)
                translated_data.update(translated)
                break
            except Exception as e:
                attempt += 1
                logger.error(f"JS 批次 {batch_num} 失败 ({attempt}/{MAX_RETRIES}): {e}")
                if attempt > MAX_RETRIES:
                    failed_batches.append({
                        'batch_num': batch_num, 'error': str(e), 'item_count': len(batch_items),
                    })
                    translated_data.update(batch_items)
                    break
                time.sleep(REQUEST_DELAY * 2)

        if i + BATCH_SIZE < total_items:
            time.sleep(REQUEST_DELAY)

    # 组装 JS 输出
    lines = ["export default {\n"]
    for k, v in translated_data.items():
        escaped = v.replace('"', '\\"')
        lines.append(f'  "{k}": "{escaped}",\n')
    lines.append("};\n")

    output_file = f"{source_base}_{target_language}.js"
    output_path = os.path.join(output_dir, output_file)
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))

    _report_completion(progress_callback, selected_model, failed_batches)
    return output_file


def _report_completion(progress_callback, model, failed_batches):
    if not progress_callback:
        return
    if failed_batches:
        total_failed = sum(b['item_count'] for b in failed_batches)
        progress_callback(
            100,
            f"翻译完成 ({model}) — ⚠️ {len(failed_batches)} 批失败, {total_failed} 项保留原文",
        )
    else:
        progress_callback(100, f"✅ 翻译完成 ({model})")


def test_llm_translation():
    """CLI 自测：Spanish + Arabic 快速验证。"""
    print(f"📊 默认模型: {DEFAULT_MODEL}\n")
    test_data = {"hello": "Hello", "confirm": "Confirm", "cancel": "Cancel"}
    for lang in ["es", "ar"]:
        print(f"=== Testing {lang} ===")
        result = translate_with_llm(test_data, lang, DEFAULT_MODEL)
        for k, v in result.items():
            print(f"  {k}: {v}")
        print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_llm_translation()
    else:
        print("用法: python translate_llm.py --test")
