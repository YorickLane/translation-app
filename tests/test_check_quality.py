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


def test_word_boundary_no_romance_cognate_false_positive():
    """词边界：罗曼同源词不再被 substring 误报（real-data: es entero≠Enter / Cancelado≠Cancel）。"""
    assert cq.contains_english_keywords("número entero en centavos", "es")[0] is False
    assert cq.contains_english_keywords("Cancelado", "es")[0] is False


def test_word_boundary_still_flags_whole_word_leak():
    """真整词英文泄漏仍 flag。"""
    assert cq.contains_english_keywords("Login expired, please try again", "ru")[0] is True
