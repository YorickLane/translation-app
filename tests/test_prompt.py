"""_build_prompt 契约测试。

含"UI 标签按字面翻译、禁扩写"指令——防 D.7 实测发现的标签过度扩写
（源 "VIP档案模式介绍" 被 LLM 扩成整句营销文案）。
"""
import llm_client


def test_prompt_forbids_label_expansion():
    p = llm_client._build_prompt(["VIP介绍"], "Spanish", "es", "")
    assert "Do NOT expand" in p


def test_prompt_still_has_core_requirements():
    """回归守护：核心要求仍在。"""
    p = llm_client._build_prompt(["x", "y"], "French", "fr", "")
    assert "exactly 2 translations" in p
    assert "Preserve placeholders" in p


def test_capitalization_section_injected_when_provided():
    p = llm_client._build_prompt(["x"], "German", "de", "RULE-MARKER-XYZ")
    assert "RULE-MARKER-XYZ" in p
