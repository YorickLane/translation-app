"""js_locale 解析/输出 + 两引擎 JS 路径共用验证。"""
import js_locale


JS_SAMPLE = '''export default {
  greeting: "你好",
  'app.title': "标题",
  "验证": "Verify",
  empty: "",
  tpl: `模板`
}
'''


def test_parse_strips_all_key_quote_styles():
    d = js_locale.parse_js_locale(JS_SAMPLE)
    assert d["greeting"] == "你好"
    assert d["app.title"] == "标题"
    assert d["验证"] == "Verify"          # 双引号 key 剥净（7772f65 修复）
    assert d["tpl"] == "模板"             # 反引号值
    assert "empty" not in d               # 空值跳过


def test_dump_escapes_double_quotes():
    out = js_locale.dump_js_locale({"a": "x", "b": 'has "q"'})
    assert out.startswith("export default {\n")
    assert '  "a": "x",\n' in out
    assert '  "b": "has \\"q\\"",\n' in out
    assert out.endswith("};\n")


def test_roundtrip_double_quoted_key_is_valid():
    """双引号 key 经 parse→dump 不再产生 ""key"" 非法 JS。"""
    d = js_locale.parse_js_locale('export default {\n  "滑动验证": "x"\n}')
    out = js_locale.dump_js_locale(d)
    assert '""' not in out
    assert '  "滑动验证": "x",\n' in out


def test_translate_locale_file_uses_shared_js_path(monkeypatch, tmp_path):
    """translate.translate_locale_file 走共用 js_locale，双引号 key 不再 ""key""。"""
    import translate
    monkeypatch.setattr(translate, "translate_text", lambda text, lang: text)  # identity，不打 Google
    src = tmp_path / "s.js"
    src.write_text(
        'export default {\n  "滑动验证": "拖动",\n  greeting: "你好"\n}',
        encoding="utf-8",
    )
    out_name = translate.translate_locale_file(str(src), "en", None, str(tmp_path))
    out = (tmp_path / out_name).read_text(encoding="utf-8")
    assert '  "滑动验证": "拖动",\n' in out   # 不是 ""滑动验证""
    assert '""' not in out
