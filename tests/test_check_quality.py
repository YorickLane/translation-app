"""check_translation_quality 英文检测 —— 词表接 QUALITY_CHECK_RULES SoT。"""
import check_translation_quality as cq
from translation_config import QUALITY_CHECK_RULES


def test_uses_sot_keyword_list_no_password_false_positive():
    """Password 已从 SoT 移除(0073e88 借词误报)，check 工具也不应再 flag。"""
    assert "Password" not in QUALITY_CHECK_RULES["english_keywords"]
    hit, _ = cq.contains_english_keywords("Password", "ru")  # ru 无豁免
    assert hit is False


def test_still_flags_real_sot_keyword():
    """SoT 内的真英文词仍能 flag。"""
    hit, kw = cq.contains_english_keywords("Confirm", "ru")
    assert hit is True
    assert kw == "Confirm"
