#!/usr/bin/env python3
"""
zh-TW 词汇现代化测试（纯 stdlib）。
运行: ./venv/bin/python test_tw_vocabulary.py

验证"全局重跑做词汇现代化"两层杠杆：
  1. LLM prompt 指南（CAPITALIZATION_RULES）携带台湾用语 + 通过/透過 上下文分流
     —— 主杠杆，phrase 级、上下文感知（OpenCC 做不到）
  2. TERM_GLOSSARY 确定性兜底 —— 单词 key 精确强制台湾标准词
"""
import translation_postprocess as pp
import translation_config as cfg
import translate_llm

_passed = 0
_failed = 0


def check(name, got, want):
    global _passed, _failed
    if got == want:
        _passed += 1
    else:
        _failed += 1
        print(f"  ✗ {name}: got {got!r}, want {want!r}")


# 无歧义的台湾标准词（prompt 与 glossary 必须一致，避免互相打架）
MODERN_TERMS = {
    '网络': '網路',
    '信息': '資訊',
    '消息': '訊息',
    '数据': '資料',
    '视频': '影片',
    '登录': '登入',
    '加载': '載入',
}


def run():
    print("== TERM_GLOSSARY 含台湾标准词 ==")
    for src, expected in MODERN_TERMS.items():
        check(f"glossary[{src}]", cfg.TERM_GLOSSARY['zh-TW'].get(src), expected)

    print("== ensure_term_consistency 把大陆词强制成台湾词 ==")
    # 模拟 LLM 产出大陆用语，glossary 应纠正
    llm_out = {'网络': '網絡', '信息': '信息', '视频': '視頻'}
    fixed = pp.ensure_term_consistency(dict(llm_out), 'zh-TW')
    check("enforce 网络→網路", fixed['网络'], '網路')
    check("enforce 信息→資訊", fixed['信息'], '資訊')
    check("enforce 视频→影片", fixed['视频'], '影片')

    print("== LLM prompt 指南携带台湾用语 + 通过分流 ==")
    for lang in ('zh-TW', 'zh-Hant'):
        rule = translate_llm.CAPITALIZATION_RULES[lang]
        for term in ['網路', '資訊', '訊息', '透過', '通過']:
            check(f"prompt[{lang}] 含 {term}", term in rule, True)

    print(f"\n结果: {_passed} passed, {_failed} failed")
    return _failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
