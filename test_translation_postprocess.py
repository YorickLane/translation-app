#!/usr/bin/env python3
"""
translation_postprocess 回归测试（纯 stdlib，无需 pytest）。
运行: ./venv/bin/python test_translation_postprocess.py

覆盖根因修复：
  1. contains_english 不再把"合法嵌入拉丁"（品牌/缩写/单位/i18n 占位符）误判为英文混入
  2. contains_english 仍能抓住"真正未翻译的英文"
  3. contains_simplified 检出 zh-TW 里的简体残留（豁免 才/台 这类合法繁体变体）
  4. strict_validation 检测到问题时不再写入破坏性的 [需要重新翻译] 前缀
"""
import translation_postprocess as pp

_passed = 0
_failed = 0


def check(name, got, want):
    global _passed, _failed
    if got == want:
        _passed += 1
    else:
        _failed += 1
        print(f"  ✗ {name}: got {got!r}, want {want!r}")


# ── 1. contains_english：合法嵌入拉丁 → 不应判为英文混入 (False) ──────────────
ENGLISH_NEGATIVES = [
    "确定要购买{name}吗？费用：${price}",   # i18n 占位符
    "利润率必须在{start}%-{end}%之间",        # 占位符
    "USDT提現",                              # 加密缩写
    "店鋪LOGO",                              # 品牌缩写
    "智慧商城AI介紹",                         # 缩写
    "圖片大小不能超過2MB",                    # 单位（数字邻接）
    "A級賣家",                               # 等级码
    "升級 B-LEVEL",                          # 等级码
    "PC橫幅（1920*320）",                     # 规格
    "請上傳店鋪LOGO(75*75px)",                # 像素单位
    "iOS下載",                               # 品牌（含小写，白名单）
    "Android下載",                           # 品牌（含小写，白名单）
]

# contains_english：真正未翻译的英文 → 应判为 True
ENGLISH_POSITIVES = [
    "Confirm",
    "Edit",
    "Please login to continue",
    "loading, please wait",
]


# ── 2. contains_simplified：zh-TW 简体残留检测 ───────────────────────────────
SIMPLIFIED_POSITIVES = [          # 含简体残留 → True
    "价格排序",
    "切换到买家端",
    "网络错误，请检查网络连接",
    "《隐私与用户协议》",
]
SIMPLIFIED_NEGATIVES = [          # 正确繁体（含变体豁免）→ False
    "A級賣家",
    "完成店舖設定後才可上架商品",   # 才（s2t 想转 纔，古字，豁免）
    "後台手動充值",                # 台（保留，不当简体）
    "商品資訊",
    "USDT提現",
]


def run():
    print("== contains_english 负例（应 False）==")
    for s in ENGLISH_NEGATIVES:
        check(f"english({s})", pp.contains_english(s), False)

    print("== contains_english 正例（应 True）==")
    for s in ENGLISH_POSITIVES:
        check(f"english({s})", pp.contains_english(s), True)

    print("== contains_simplified 正例（应 True）==")
    for s in SIMPLIFIED_POSITIVES:
        check(f"simplified({s})", pp.contains_simplified(s), True)

    print("== contains_simplified 负例（应 False）==")
    for s in SIMPLIFIED_NEGATIVES:
        check(f"simplified({s})", pp.contains_simplified(s), False)

    print("== strict_validation 不写破坏性前缀 ==")
    # 含合法繁体 + 一条真英文残留
    data = {
        "USDT提現": "USDT提現",
        "确定": "Confirm",
        "价格排序": "价格排序",
    }
    out = pp.strict_validation(dict(data), "zh-TW")
    for k, v in out.items():
        check(f"no-marker[{k}]", "[需要重新翻译]" not in v, True)
    # 合法繁体条目不应被改动
    check("USDT提現 unchanged", out["USDT提現"], "USDT提現")

    print(f"\n结果: {_passed} passed, {_failed} failed")
    return _failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
