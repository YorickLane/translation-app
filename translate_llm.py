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

from llm_client import translate_batch
from config import BATCH_SIZE, REQUEST_DELAY, MAX_RETRIES, DEFAULT_MODEL
# 英文关键词检测单一来源:直接复用 translation_postprocess 的 contains_english_keywords,
# 不在本模块另编关键词/正则。(SoT: translation_config.QUALITY_CHECK_RULES['english_keywords'];
#  translation_postprocess 只依赖 translation_config,方向无环)
from translation_postprocess import contains_english_keywords
from js_locale import parse_js_locale, dump_js_locale

try:
    from translation_config import (
        TEMPERATURE_BY_LANGUAGE,
        LANGUAGE_CODE_MAPPING,
        BATCH_CONFIG,
        VALIDATION_STRENGTH,
        TERM_GLOSSARY,
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


# 繁体中文（台湾）规则 —— zh-TW / zh-Hant 共用一份，避免两份漂移 (SoT)。
# 词汇现代化指南直接进 LLM prompt：phrase 级、上下文感知（OpenCC 字形映射做不到），
# 尤其 通過/透過 的 pass/via 分流只能靠 LLM 语义判断。glossary 与此处保持一致。
_TRADITIONAL_CHINESE_TW_RULE = """- This is Traditional Chinese for TAIWAN (台灣), use traditional characters (繁體字), NOT simplified
- NEVER return English; must translate to Traditional Chinese
- Use idiomatic TAIWAN vocabulary, NOT mainland Chinese terms:
  網路(not 網絡), 登入(not 登錄), 設定(not 設置), 載入(not 加載), 資訊(not 信息),
  訊息(not 消息), 資料(not 數據), 影片(not 視頻), 搜尋(not 搜索), 複製(not 复制),
  檔案(not 文件), 開啟(not 打開), 螢幕(not 屏幕), 帳號/帳戶(not 賬號/賬戶), 儲值(not 充值)
- Context-sensitive 通過 vs 透過: use 透過 for via/through (e.g. 透過郵箱找回),
  but 通過 for pass/approve (e.g. 審核通過). Never blindly convert one to the other.
- Context-sensitive 連線 vs 連接: use 連線 for network/online connection (e.g. 網路連線),
  but 連接 for physical join. (TW UI says 網路連線, not 網路連接.)
- Keep brands/units/i18n placeholders verbatim: USDT, LOGO, AI, {name}, ${price}, 2MB, 75px
- Examples: 确定→確定, 保存→儲存, 设置→設定, 网络→網路, 信息→資訊"""


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

    "zh-TW": _TRADITIONAL_CHINESE_TW_RULE,

    "zh-Hant": _TRADITIONAL_CHINESE_TW_RULE,
}

GENERIC_RULE = (
    "- Follow standard capitalization rules for this language\n"
    "- Be consistent across all strings"
)


# ---------- English 混入检测（非英语目标触发重试） ----------
#
# 这是"批级粗粒度重试闸":一整批里 >20% 的项含英文 UI 关键词 → 判本批英文过多、重调 LLM。
# 对【所有】非英语目标生效(含拉丁字母系 es/fr/de/it/pt…),故必须用【词边界关键词匹配】
# ——绝不能用 translation_postprocess.contains_english 的"可疑拉丁词占比法":那套假定目标
# 是非拉丁文(CJK/阿语),会把西/法语的合法译文 cancelar/confirmar 全判成英文 → 无限重试。
#
# 与之相对的是 translation_postprocess.contains_english(经 _detect_flagged/qa_retranslate 用):
# "逐项精细 QA 分类器",仅对 strict 的 CJK/阿语目标跑,决定哪几项进人工复审队列。两者【职责/
# 粒度/适用脚本都不同,刻意分开】。此处只共享底层的关键词检测(contains_english_keywords),
# 保证"是否含英文 UI 关键词"全项目唯一一份实现;勿把两个闸合并成同一算法。


def _contains_too_much_english(translations):
    """批级重试闸:>20% 的字符串项含英文 UI 关键词则判英文过多(触发整批重译)。

    关键词检测复用 translation_postprocess.contains_english_keywords(词边界匹配,
    避免罗曼语系同源词误判)——单一来源,不在本模块另实现。
    """
    values = [v for v in translations.values() if isinstance(v, str)]
    if not values:
        return False
    hits = sum(1 for v in values if contains_english_keywords(v))
    return hits / len(values) > 0.2


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


# ---------- D.7 QA 回灌重译闭环 ----------

def _detect_flagged(translated_data, target_language):
    """用确定性检测器找需重译的 key。返回 [(key, reason)]。"""
    from translation_postprocess import contains_english, contains_simplified
    is_zh_hant = target_language in ('zh-TW', 'zh-Hant')
    flagged = []
    for key, value in translated_data.items():
        if not isinstance(value, str):
            continue
        if target_language != 'en' and contains_english(value):
            flagged.append((key, '英文未翻译'))
        elif is_zh_hant and contains_simplified(value):
            flagged.append((key, '简体残留'))
    return flagged


def qa_retranslate(translated_data, source_data, target_language, model,
                   max_rounds=1, progress_callback=None):
    """QA 回灌重译闭环：检测 flagged → 用原文重译 → 复检；剩余的返回供人工队列。

    复用 translation_postprocess 的确定性检测器(contains_english / contains_simplified)。
    只对 strict 语言(zh-TW/zh-Hant/ar)有意义。受 max_rounds 限制防 token 失控。

    Returns: (translated_data, remaining_flagged)；remaining_flagged: [(key, value, reason)]
    """
    flagged = _detect_flagged(translated_data, target_language)
    rounds = 0
    while flagged and rounds < max_rounds:
        rounds += 1
        to_fix = {k: source_data[k] for k, _ in flagged if k in source_data}
        if not to_fix:
            break
        if progress_callback:
            progress_callback(100, f"QA 回灌重译 {len(to_fix)} 项（第 {rounds}/{max_rounds} 轮）")
        try:
            retranslated = translate_with_llm(to_fix, target_language, model)
            translated_data.update(retranslated)
        except Exception as e:
            logger.error(f"QA 回灌重译失败: {e}")
            break
        flagged = _detect_flagged(translated_data, target_language)
    remaining = [(k, translated_data.get(k), reason) for k, reason in flagged]
    return translated_data, remaining


# ---------- 嵌套结构展平 / 重建（纯函数） ----------

def _flatten(data, _path=()):
    """递归展平 dict/list，收集【非空字符串】叶子为 [(path_tuple, str)]。

    - dict: 按插入序遍历，path 追加 str key
    - list: 按下标遍历，path 追加 int index
    - str 叶子且 strip 后非空 → 收集待翻译；空串/纯空白不送翻译（与 Google 引擎一致）
    - int/float/bool/None 及其它标量 → 不收集（重建时原样保留）
    顶层同时支持 dict 与 list。

    只返回待翻译叶子；重建靠 _rebuild 走原始 data，故此处无需记录非字符串叶子。
    """
    leaves = []
    if isinstance(data, dict):
        for key, value in data.items():
            leaves.extend(_flatten(value, _path + (key,)))
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            leaves.extend(_flatten(value, _path + (idx,)))
    elif isinstance(data, str):
        if data.strip():
            leaves.append((_path, data))
    # 其它标量（int/float/bool/None）不收集，重建时由 _rebuild 原样返回
    return leaves


def _rebuild(data, translations_by_path, _path=()):
    """按原结构重建：翻译过的路径取译文，其余（非字符串/空串/未翻译）原样保留。

    完整保留 dict 键序与 list 顺序（dict 推导式保序，Py3.7+）。
    translations_by_path: {path_tuple: translated_str}。
    """
    if isinstance(data, dict):
        return {
            key: _rebuild(value, translations_by_path, _path + (key,))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [
            _rebuild(value, translations_by_path, _path + (idx,))
            for idx, value in enumerate(data)
        ]
    if isinstance(data, str):
        return translations_by_path.get(_path, data)
    return data  # int/float/bool/None 等原样


def _path_to_str(path):
    """路径元组 → 可读字符串；dict key 用点号连接，list 下标用 [i]。

    ('a','b') → 'a.b'；('items',0,'label') → 'items[0].label'；(0,) → '[0]'
    """
    out = ""
    for seg in path:
        if isinstance(seg, int):
            out += f"[{seg}]"
        else:
            out += seg if out == "" else f".{seg}"
    return out


def _apply_glossary(translations_by_path, target_language):
    """术语表兜底：【整 key 精确匹配】，用路径最后一段（叶子 key）匹配 TERM_GLOSSARY。

    语义等同 translation_postprocess.ensure_term_consistency（whole-key exact match），
    但这里 translations_by_path 的 key 是路径元组，post_process 内的 glossary 对元组 key
    不会命中，故在此显式补上：只有叶子 key 精确等于 glossary 的 key 才强制（真实语言包
    key 多为整句，几乎不触发；这只是确定性兜底）。就地修改 translations_by_path。
    """
    if not (USE_ADVANCED_CONFIG and target_language in TERM_GLOSSARY):
        return
    glossary = TERM_GLOSSARY[target_language]
    for path, value in list(translations_by_path.items()):
        leaf = path[-1] if path else None
        if isinstance(leaf, str) and leaf in glossary and isinstance(value, str):
            expected = glossary[leaf]
            if value.lower() != expected.lower():
                logger.info(f"术语修正 ({_path_to_str(path)}): {value} → {expected}")
                translations_by_path[path] = expected


# ---------- JSON 文件翻译 ----------

def translate_json_file_llm(
    source_file_path, target_language,
    progress_callback=None, model=None, output_dir="output",
):
    """翻译 JSON 语言包文件（支持任意嵌套 dict/list，顶层可为 dict 或 list）。"""
    selected_model = model or DEFAULT_MODEL
    logger.info(f"翻译 JSON → {target_language} 使用 {selected_model}")

    source_base = os.path.splitext(os.path.basename(source_file_path))[0]

    with open(source_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 递归展平：只取非空字符串叶子送翻译；嵌套结构 / 非字符串叶子在重建时原样保留。
    # 内部一律以 path 元组为 key（唯一，避免不同路径同叶子 key 撞车）。
    leaves = _flatten(data)
    source_by_path = dict(leaves)          # path → 原文，供 QA 回灌取原文
    total_items = len(leaves)
    use_dynamic = USE_ADVANCED_CONFIG and BATCH_CONFIG.get('dynamic_batching', False)
    batches = _create_dynamic_batches(leaves, use_dynamic)
    total_batches = len(batches)

    translations_by_path = {}
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
                        translations_by_path.update(translated)
                        processed += batch_size
                        break
                    time.sleep(_get_retry_delay(attempt))
                    continue

                translations_by_path.update(translated)
                processed += batch_size
                success = True

            except Exception as e:
                attempt += 1
                logger.error(f"批次 {batch_num} 失败 ({attempt}/{max_retries}): {e}")
                if attempt > max_retries:
                    failed_batches.append({
                        'batch_num': batch_num, 'error': str(e), 'item_count': batch_size,
                    })
                    translations_by_path.update(batch_items)  # 保留原文（path → 原文）
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

    # 术语表兜底（整 key 精确匹配，用叶子 key）——post_process 对 path 元组 key 不命中，
    # 这里显式补；放在 QA 之前，保持原"glossary 先于 QA"的顺序。
    _apply_glossary(translations_by_path, target_language)

    # D.7 QA 回灌重译闭环（仅 strict 语言；可经 BATCH_CONFIG['qa_retranslate'] 关闭）
    # translated / source 均以 path 为 key，qa_retranslate 逻辑无需改动。
    needs_review = []
    if (USE_ADVANCED_CONFIG and BATCH_CONFIG.get('qa_retranslate', True)
            and VALIDATION_STRENGTH.get(target_language) == 'strict'):
        max_rounds = BATCH_CONFIG.get('qa_max_rounds', 1)
        translations_by_path, needs_review = qa_retranslate(
            translations_by_path, source_by_path, target_language, selected_model,
            max_rounds=max_rounds, progress_callback=progress_callback,
        )

    # 按原结构重建（保留键序、嵌套 dict/list、非字符串叶子、空串、未翻译原文）
    translated_data = _rebuild(data, translations_by_path)

    # 保存
    output_file = f"{source_base}_{target_language}.json"
    output_path = os.path.join(output_dir, output_file)
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    # D.7 人工复审队列：QA 回灌后仍未过的写 sidecar（非阻塞，交付物不受影响）
    # key 用点号路径字符串（数组下标 [i]），便于人工定位嵌套位置。
    if needs_review:
        review_path = os.path.join(
            output_dir, f"{source_base}_{target_language}.needs_review.json"
        )
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(
                [{"key": _path_to_str(p), "value": v, "reason": r} for p, v, r in needs_review],
                f, ensure_ascii=False, indent=2,
            )
        logger.warning(f"[{target_language}] {len(needs_review)} 项 QA 未过，写入 {review_path}")

    _report_completion(progress_callback, selected_model, failed_batches)
    return output_file


# ---------- JS 文件翻译 ----------


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

    translation_dict = parse_js_locale(content)
    if not translation_dict:
        raise ValueError("无法从 JS 文件提取键值对，请检查格式")

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
    output_file = f"{source_base}_{target_language}.js"
    output_path = os.path.join(output_dir, output_file)
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dump_js_locale(translated_data))

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
