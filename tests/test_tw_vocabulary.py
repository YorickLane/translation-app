"""zh-TW 词汇现代化测试（pytest 版，自根目录 test_tw_vocabulary.py 迁移）。

验证"全局重跑做词汇现代化"两层杠杆:
  1. LLM prompt 指南（CAPITALIZATION_RULES）携带台湾用语 + 通過/透過 上下文分流
     —— 主杠杆，phrase 级、上下文感知（OpenCC 做不到）
  2. TERM_GLOSSARY 确定性兜底 —— 单词 key 精确强制台湾标准词
"""
import pytest

import translation_postprocess as pp
import translation_config as cfg
import translate_llm


# 无歧义的台湾标准词（prompt 与 glossary 必须一致，避免互相打架）
MODERN_TERMS = {
    "网络": "網路",
    "信息": "資訊",
    "消息": "訊息",
    "数据": "資料",
    "视频": "影片",
    "登录": "登入",
    "加载": "載入",
    "充值": "儲值",   # 台湾 top-up 标准词（充值=大陆），web 验证 2026-06-21
}


@pytest.mark.parametrize("src,expected", list(MODERN_TERMS.items()))
def test_glossary_has_taiwan_terms(src, expected):
    assert cfg.TERM_GLOSSARY["zh-TW"].get(src) == expected


def test_ensure_term_consistency_enforces_taiwan_terms():
    """模拟 LLM 产出大陆用语，glossary 应纠正为台湾词。"""
    llm_out = {"网络": "網絡", "信息": "信息", "视频": "視頻"}
    fixed = pp.ensure_term_consistency(dict(llm_out), "zh-TW")
    assert fixed["网络"] == "網路"
    assert fixed["信息"] == "資訊"
    assert fixed["视频"] == "影片"


@pytest.mark.parametrize("lang", ["zh-TW", "zh-Hant"])
@pytest.mark.parametrize("term", ["網路", "資訊", "訊息", "透過", "通過", "儲值", "連線"])
def test_prompt_carries_taiwan_vocab(lang, term):
    rule = translate_llm.CAPITALIZATION_RULES[lang]
    assert term in rule


def test_ensure_term_consistency_whole_key_only():
    """D.10 契约: 整 key 精确匹配才生效；句子 key(含术语子串)不被改。"""
    # 精确 key → 强制
    assert pp.ensure_term_consistency({"网络": "網絡"}, "zh-TW")["网络"] == "網路"
    # 句子 key 含"网络"但非精确 key → 不动（不做子串替换）
    out = pp.ensure_term_consistency({"请检查网络连接": "請檢查網絡連線"}, "zh-TW")
    assert out["请检查网络连接"] == "請檢查網絡連線"
