"""translation_runner.translate_single_file 分发逻辑（monkeypatch 叶子函数，不打真 API）。"""
import pytest

import translation_runner as runner


def test_openrouter_json_dispatch(monkeypatch):
    called = {}

    def fake_json(path, lang, cb, model, out):
        called["args"] = (path, lang, model, out)
        return "a_zh-TW.json"

    monkeypatch.setattr(runner, "translate_json_file_llm", fake_json)
    name, full = runner.translate_single_file("a.json", "zh-TW", "openrouter", "m", "out")
    assert name == "a_zh-TW.json"
    assert full.endswith("a_zh-TW.json")
    assert called["args"] == ("a.json", "zh-TW", "m", "out")


def test_openrouter_js_dispatch(monkeypatch):
    monkeypatch.setattr(runner, "translate_js_file_llm", lambda *a: "a.js")
    name, _ = runner.translate_single_file("a.js", "es", "openrouter", "m", "out")
    assert name == "a.js"


def test_google_dispatch(monkeypatch):
    monkeypatch.setattr(runner, "translate_file", lambda *a: "g.json")
    name, _ = runner.translate_single_file("a.json", "es", "google", None, "out")
    assert name == "g.json"


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        runner.translate_single_file("a.txt", "es", "openrouter", "m", "out")
