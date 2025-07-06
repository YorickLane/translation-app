#!/usr/bin/env python3
"""
翻译后处理模块
用于验证和修正翻译结果
"""

import re
import logging
from translation_config import (
    VALIDATION_STRENGTH,
    QUALITY_CHECK_RULES,
    POST_PROCESSING_RULES,
    TERM_GLOSSARY
)

logger = logging.getLogger(__name__)


def post_process_translation(translated_data, target_lang, source_lang='zh-CN'):
    """
    对翻译结果进行后处理
    
    Args:
        translated_data: 翻译后的数据字典
        target_lang: 目标语言代码
        source_lang: 源语言代码
        
    Returns:
        处理后的数据字典
    """
    validation_level = VALIDATION_STRENGTH.get(target_lang, 'light')
    
    if validation_level == 'strict':
        translated_data = strict_validation(translated_data, target_lang)
    elif validation_level == 'moderate':
        translated_data = moderate_validation(translated_data, target_lang)
    
    # 应用后处理规则
    translated_data = apply_post_processing_rules(translated_data, target_lang)
    
    # 检查术语一致性
    translated_data = ensure_term_consistency(translated_data, target_lang, source_lang)
    
    return translated_data


def strict_validation(data, target_lang):
    """严格验证（用于繁体中文等）"""
    if target_lang in ['zh-TW', 'zh-Hant']:
        # 检查是否有英文混入
        for key, value in data.items():
            if isinstance(value, str) and contains_english(value):
                logger.warning(f"发现英文混入 ({key}): {value}")
                # 标记需要重新翻译
                data[key] = f"[需要重新翻译] {value}"
    
    return data


def moderate_validation(data, target_lang):
    """中度验证（用于罗曼语系）"""
    max_ratio = QUALITY_CHECK_RULES['max_english_ratio'].get(target_lang, 0.1)
    english_count = 0
    total_count = len(data)
    
    for key, value in data.items():
        if isinstance(value, str) and contains_english_keywords(value):
            english_count += 1
            logger.warning(f"可能的英文混入 ({key}): {value}")
    
    if total_count > 0 and english_count / total_count > max_ratio:
        logger.error(f"{target_lang} 翻译中英文比例过高: {english_count}/{total_count}")
    
    return data


def apply_post_processing_rules(data, target_lang):
    """应用后处理规则"""
    # 罗曼语系小写处理
    if target_lang in POST_PROCESSING_RULES['lowercase_languages']:
        for key, value in data.items():
            if isinstance(value, str):
                # 处理单个词的UI元素
                words = value.split()
                if len(words) == 1 and not should_preserve_case(words[0]):
                    data[key] = value.lower()
    
    return data


def ensure_term_consistency(data, target_lang, source_lang='zh-CN'):
    """确保术语翻译一致性"""
    if target_lang not in TERM_GLOSSARY:
        return data
    
    glossary = TERM_GLOSSARY[target_lang]
    
    for key, value in data.items():
        # 检查是否有术语表中的词汇
        if key in glossary and isinstance(value, str):
            expected = glossary[key]
            if value.lower() != expected.lower():
                logger.info(f"术语修正 ({key}): {value} → {expected}")
                data[key] = expected
    
    return data


def contains_english(text):
    """检查文本是否包含英文字符（用于中文）"""
    # 排除常见的品牌名和技术术语
    exceptions = ['APP', 'iOS', 'Android', 'ID', 'VIP', 'API', 'URL', 'T+1']
    
    # 移除例外词汇
    temp_text = text
    for exception in exceptions:
        temp_text = temp_text.replace(exception, '')
    
    # 检查是否有英文字母
    return bool(re.search(r'[a-zA-Z]', temp_text))


def contains_english_keywords(text):
    """检查是否包含常见的英文关键词"""
    keywords = QUALITY_CHECK_RULES['english_keywords']
    text_lower = text.lower()
    
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True
    
    return False


def should_preserve_case(word):
    """判断词汇是否应该保留大写"""
    return word.upper() in POST_PROCESSING_RULES['preserve_uppercase']


def validate_translation_quality(original_data, translated_data, target_lang):
    """
    验证翻译质量
    
    Returns:
        tuple: (is_valid, issues)
    """
    issues = []
    
    # 检查键是否完整
    missing_keys = set(original_data.keys()) - set(translated_data.keys())
    if missing_keys:
        issues.append(f"缺失的键: {missing_keys}")
    
    # 检查值是否都已翻译
    untranslated = []
    for key in original_data:
        if key in translated_data:
            if translated_data[key] == original_data[key]:
                untranslated.append(key)
    
    if untranslated:
        issues.append(f"未翻译的条目: {len(untranslated)}")
    
    # 检查英文混入
    if target_lang != 'en':
        english_entries = []
        for key, value in translated_data.items():
            if isinstance(value, str) and contains_english_keywords(value):
                english_entries.append(key)
        
        if english_entries:
            issues.append(f"包含英文的条目: {len(english_entries)}")
    
    is_valid = len(issues) == 0
    return is_valid, issues


if __name__ == "__main__":
    # 测试后处理功能
    test_data = {
        "确定": "Confirm",
        "取消": "Cancel",
        "编辑": "Edit"
    }
    
    print("测试罗曼语系小写处理:")
    result = post_process_translation(test_data.copy(), 'es')
    print(f"西班牙语: {result}")
    
    print("\n测试繁体中文验证:")
    test_zh_tw = {
        "确定": "Confirm",
        "取消": "取消",
        "编辑": "Edit"
    }
    result = post_process_translation(test_zh_tw.copy(), 'zh-TW')
    print(f"繁体中文: {result}")