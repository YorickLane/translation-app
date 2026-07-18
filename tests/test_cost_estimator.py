"""cost_estimator 输出长度倍数守护 —— 中文变体须走比 DEFAULT 更紧凑的倍数。

背景：估算按 lang[:2].lower() 查 OUTPUT_LENGTH_MULTIPLIER。曾漏 'zh' 条目，
导致 zh / zh-TW / zh-CN 全落 DEFAULT_MULTIPLIER(0.85)，高估中文输出长度与费用。
中文（尤其 UI 字符串）相对英文源更紧凑，倍数应显著低于 DEFAULT。
"""
from cost_estimator import OUTPUT_LENGTH_MULTIPLIER, DEFAULT_MULTIPLIER


def _lookup(lang):
    """复刻 estimate_cost 里的查表逻辑：lang[:2].lower() → 倍数（缺失落 DEFAULT）。"""
    return OUTPUT_LENGTH_MULTIPLIER.get(lang[:2].lower(), DEFAULT_MULTIPLIER)


def test_zh_tw_multiplier_below_default():
    """zh-TW（及 zh / zh-CN）经 lang[:2] 命中 'zh'，倍数须 < DEFAULT_MULTIPLIER。"""
    assert _lookup("zh-TW") < DEFAULT_MULTIPLIER
    # 同一个 'zh' 键覆盖全部中文变体
    assert _lookup("zh-CN") == _lookup("zh-TW") == OUTPUT_LENGTH_MULTIPLIER["zh"]
