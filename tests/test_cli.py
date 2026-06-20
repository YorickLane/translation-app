"""cli.py 无头入口 —— 参数解析 + 编排（monkeypatch 翻译，不打真 API）。"""
import pytest

import cli


def test_parser_basic():
    args = cli.build_parser().parse_args(["src.json", "--langs", "zh-TW,es", "--model", "m"])
    assert args.source == "src.json"
    assert args.langs == "zh-TW,es"
    assert args.model == "m"
    assert args.engine == "openrouter"


def test_list_models(capsys):
    rc = cli.main(["--list-models"])
    assert rc == 0
    assert "anthropic/claude-sonnet-4.6" in capsys.readouterr().out


def test_missing_source_errors():
    with pytest.raises(SystemExit):
        cli.main(["--langs", "es"])  # 缺 source


def test_orchestrates_per_lang(monkeypatch, tmp_path):
    src = tmp_path / "s.json"
    src.write_text('{"k": "v"}', encoding="utf-8")
    calls = []

    def fake(path, lang, engine, model, out, cb):
        calls.append(lang)
        return (f"s_{lang}.json", f"{out}/s_{lang}.json")

    monkeypatch.setattr(cli, "translate_single_file", fake)
    rc = cli.main([str(src), "--langs", "zh-TW,es,fr", "--out", str(tmp_path / "o")])
    assert rc == 0
    assert calls == ["zh-TW", "es", "fr"]
