"""translation_postprocess 回归测试（pytest 版，自根目录 test_translation_postprocess.py 迁移）。

覆盖 cb780b2 根因修复:
  1. contains_english 不把"合法嵌入拉丁"（品牌/缩写/单位/i18n 占位符）误判为英文混入
  2. contains_english 仍抓得住"真正未翻译的英文"
  3. contains_simplified 检出 zh-TW 简体残留（豁免 才/台 这类合法繁体变体）
  4. strict_validation 检出问题时不写破坏性的 [需要重新翻译] 前缀
"""
import pytest

import translation_postprocess as pp


# ── contains_english：合法嵌入拉丁 → 不应判为英文混入 (False) ──
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
    "只允許上傳 png/jpg/jpeg 格式的圖片",      # 文件格式名（小写，白名单）
    "支援 gif/svg/webp/pdf 上傳",             # 更多文件格式
    # CJK 为主、嵌入品牌/术语/括注 → 非"未翻译"（real-data: e2e Oracle / seller-h5 AI 括注 / x4 allegro）
    "這是 Oracle 提供的企業級電子商務平台，客戶可基於它搭建自己的網路商店",
    "結合人工智慧(Artificial Intelligence, AI)和影像辨識技術的智慧商城",
    "Allegro的新客戶",
]

# contains_english：真正未翻译的英文 → 应判为 True
ENGLISH_POSITIVES = [
    "Confirm",
    "Edit",
    "Please login to continue",
    "loading, please wait",
]

# contains_simplified：zh-TW 简体残留 → True
SIMPLIFIED_POSITIVES = [
    "价格排序",
    "切换到买家端",
    "网络错误，请检查网络连接",
    "《隐私与用户协议》",
]

# 正确繁体（含变体豁免）→ False
SIMPLIFIED_NEGATIVES = [
    "A級賣家",
    "完成店舖設定後才可上架商品",   # 才（s2t 想转 纔，古字，豁免）
    "後台手動充值",                # 台（保留，不当简体）
    "商品資訊",
    "USDT提現",
]


@pytest.mark.parametrize("text", ENGLISH_NEGATIVES)
def test_contains_english_negatives(text):
    assert pp.contains_english(text) is False


@pytest.mark.parametrize("text", ENGLISH_POSITIVES)
def test_contains_english_positives(text):
    assert pp.contains_english(text) is True


@pytest.mark.parametrize("text", SIMPLIFIED_POSITIVES)
def test_contains_simplified_positives(text):
    assert pp.contains_simplified(text) is True


@pytest.mark.parametrize("text", SIMPLIFIED_NEGATIVES)
def test_contains_simplified_negatives(text):
    assert pp.contains_simplified(text) is False


def test_strict_validation_no_destructive_marker():
    """含合法繁体 + 一条真英文残留：检出但不写 [需要重新翻译]，合法条目不动。"""
    data = {
        "USDT提現": "USDT提現",
        "确定": "Confirm",
        "价格排序": "价格排序",
    }
    out = pp.strict_validation(dict(data), "zh-TW")
    for value in out.values():
        assert "[需要重新翻译]" not in value
    assert out["USDT提現"] == "USDT提現"
