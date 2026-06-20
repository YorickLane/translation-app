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
    """严格验证（用于繁体中文等）。

    检测两类问题并写入日志，但【不再】往交付物里加 "[需要重新翻译]" 前缀——旧行为依赖
    会误判的 contains_english，把合法繁体污染成非法译文。改为非破坏性：检出的 key 经
    logger.warning 暴露，供上游 pipeline 决定是否回灌 LLM 重译（OpenCC 只当检测闸，
    不当翻译器）。返回的 data 内容不变。
    """
    is_zh_hant = target_lang in ('zh-TW', 'zh-Hant')
    flagged = []
    for key, value in data.items():
        if not isinstance(value, str):
            continue
        if contains_english(value):
            flagged.append((key, value, '英文未翻译'))
        elif is_zh_hant and contains_simplified(value):
            flagged.append((key, value, '简体残留'))

    for key, value, reason in flagged:
        logger.warning(f"[{target_lang}] {reason} ({key}): {value}")
    if flagged:
        logger.warning(
            f"[{target_lang}] 共 {len(flagged)} 条待重译（已记录，未改动交付物，"
            f"由上游决定是否回灌 LLM）"
        )

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


# 合法嵌入拉丁的白名单（含小写的品牌/单位）。全大写缩写无需列入——见下判定逻辑。
_LATIN_ALLOW = {'ios', 'iphone', 'ipad', 'android', 'safari', 'app', 'px'}


def contains_english(text):
    """检查中文译文里是否【真的混入了未翻译的英文】。

    只把"含小写字母、且不在白名单里的字母词"判为英文泄漏。合法嵌入的拉丁一律放行：
    i18n 占位符 {x}/${x}、全大写缩写 (USDT/PC/AI/LOGO/VIP)、紧邻数字的型号/单位
    (H5/2MB/75px/1920)、品牌 (iOS/Android)。

    旧实现（残留任意 [a-zA-Z] 即判混入）会把上述全部误杀，是 [需要重新翻译] 误标记的根因。
    """
    # 1) 去掉 i18n 占位符
    t = re.sub(r'\$?\{[^}]*\}', '', text)
    # 2) 去掉紧邻数字的字母（型号/单位/规格：H5 / 2MB / 75px / 1920x1080）
    t = re.sub(r'(?<=\d)[A-Za-z]+|[A-Za-z]+(?=\d)', '', t)
    # 3) 任一"含小写且不在白名单"的字母词 → 真英文未翻译
    for tok in re.findall(r'[A-Za-z]+', t):
        if any(c.islower() for c in tok) and tok.lower() not in _LATIN_ALLOW:
            return True
    return False


# OpenCC 简繁检测（确定性，零 LLM）。检测基准用 s2tw 而非 s2t：s2t 会把 才→纔 这类古字误判，
# s2tw 不会。台/臺 我们保留 台，s2tw 想转 臺，故豁免。缺库则优雅降级（不检测，不报错）。
try:
    from opencc import OpenCC as _OpenCC
    _S2TW = _OpenCC('s2tw')
except Exception:  # opencc 未安装
    _S2TW = None

# s2tw 想改、但实为合法繁体、无需视作简体残留的字
_TRAD_VARIANT_OK = {'台'}


def contains_simplified(text):
    """检查 zh-TW/zh-Hant 译文是否还残留简体字（确定性检测，非翻译）。

    用作 LLM 漏翻的 QA 闸：命中即"这条该是繁体却还有简体"。注意只用来【检测】，
    不要拿 OpenCC 输出直接当译文（字形映射给不出地道台湾用语，且有 才/纔 古字坑）。
    """
    if _S2TW is None:
        return False
    converted = _S2TW.convert(text)
    if converted == text:
        return False
    if len(converted) != len(text):   # s2tw 为 1:1 字映射；长度变了直接判残留
        return True
    return any(a != b and a not in _TRAD_VARIANT_OK for a, b in zip(text, converted))


_ENGLISH_KEYWORD_PATTERNS = [
    re.compile(rf'\b{re.escape(k)}\b', re.IGNORECASE)
    for k in QUALITY_CHECK_RULES['english_keywords']
]


def contains_english_keywords(text):
    """检查是否包含常见的英文关键词（词边界匹配，避免把罗曼语系同源词误判）。"""
    for pattern in _ENGLISH_KEYWORD_PATTERNS:
        if pattern.search(text):
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