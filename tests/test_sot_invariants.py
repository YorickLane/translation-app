"""单源真相不变量 —— 守护重构后关键 SoT 不退化（work_philosophy §7）。

这些不变量回答"这个变了，几处要同步？"：答案必须是 1 处。若有人重新引入本地副本，
对应不变量会立刻变红。
"""
import config
import llm_models
import translation_config as cfg
import translation_postprocess as pp
import translate_llm


def test_default_model_exists_in_catalog():
    """config.DEFAULT_MODEL 必须是 AVAILABLE_MODELS 里真实存在的 slug。"""
    assert llm_models.get_model_info(config.DEFAULT_MODEL) is not None


def test_catalog_default_has_pricing():
    """目录默认模型须带定价（cost_estimator 直接读这里，定价单源）。"""
    default_id = llm_models.get_default_model_id()
    info = llm_models.get_model_info(default_id)
    assert info is not None
    assert info["input_price_per_m"] > 0
    assert info["output_price_per_m"] > 0


def test_english_keywords_single_source():
    """英文关键词检测单一来源（防本地副本回归）。

    编译源在 translation_postprocess（模式数 == SoT 列表长度）；translate_llm 不再
    自持一份模式,而是直接复用 pp.contains_english_keywords 这个【同一函数对象】——
    若有人重新在 translate_llm 里本地编译关键词/正则,下面的 `is` 断言会立刻变红。
    """
    n = len(cfg.QUALITY_CHECK_RULES["english_keywords"])
    assert len(pp._ENGLISH_KEYWORD_PATTERNS) == n
    # translate_llm 用的就是 pp 的那个函数,不是副本
    assert translate_llm.contains_english_keywords is pp.contains_english_keywords
    # 且 translate_llm 不再持有本地关键词模式副本
    assert not hasattr(translate_llm, "_ENGLISH_KEYWORD_PATTERNS")
    assert not hasattr(translate_llm, "_ENGLISH_PATTERN")
