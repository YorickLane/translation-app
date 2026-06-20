"""D.7 回灌重译闭环 —— qa_retranslate + translate_json_file_llm sidecar（monkeypatch，不打真 API）。"""
import json

import translate_llm


def test_qa_retranslate_fixes_flagged(monkeypatch):
    """第一轮含英文残留 → 重译修好 → remaining 空。"""
    translated = {"k1": "確定", "k2": "Confirm"}   # k2 英文未翻
    source = {"k1": "确定", "k2": "确认"}
    monkeypatch.setattr(translate_llm, "translate_with_llm", lambda to_fix, lang, model: {k: "確認" for k in to_fix})
    out, remaining = translate_llm.qa_retranslate(translated, source, "zh-TW", "m", max_rounds=1)
    assert out["k2"] == "確認"
    assert remaining == []


def test_qa_retranslate_residual_goes_to_review(monkeypatch):
    """重译后仍英文 → 进 remaining（人工队列）。"""
    monkeypatch.setattr(translate_llm, "translate_with_llm", lambda to_fix, lang, model: {k: "Still English" for k in to_fix})
    out, remaining = translate_llm.qa_retranslate({"k": "Confirm"}, {"k": "确认"}, "zh-TW", "m", max_rounds=1)
    assert len(remaining) == 1
    assert remaining[0][0] == "k"
    assert remaining[0][2] == "英文未翻译"


def test_qa_retranslate_noop_when_clean(monkeypatch):
    """无 flagged → 不调用重译。"""
    called = []
    monkeypatch.setattr(translate_llm, "translate_with_llm", lambda *a: called.append(1) or {})
    out, remaining = translate_llm.qa_retranslate({"k": "確定"}, {"k": "确定"}, "zh-TW", "m")
    assert remaining == []
    assert called == []


def test_translate_json_file_writes_needs_review(monkeypatch, tmp_path):
    """strict 语言 + 顽固残留 → 写 needs_review sidecar。

    用 'abc'（非关键词小写拉丁）：过 batch 级 >20%关键词阈值（不触发重试 sleep），
    但被 item 级 contains_english 抓 → 进 QA 闭环 → sidecar。
    """
    src = tmp_path / "s.json"
    src.write_text('{"k": "确认"}', encoding="utf-8")
    monkeypatch.setattr(translate_llm, "translate_with_llm", lambda items, lang, model: {k: "abc" for k in items})
    out_name = translate_llm.translate_json_file_llm(str(src), "zh-TW", None, "m", str(tmp_path))
    review = tmp_path / out_name.replace(".json", ".needs_review.json")
    assert review.exists()
    data = json.loads(review.read_text(encoding="utf-8"))
    assert data[0]["key"] == "k"
    assert data[0]["reason"] == "英文未翻译"
