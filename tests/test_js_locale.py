"""js_locale 解析/输出 + 两引擎 JS 路径共用验证。"""
import json
import re
import shutil
import subprocess

import pytest

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


# ---------------------------------------------------------------------------
# dump 转义完整性 + dump→parse 往返（修复：旧版只转义双引号，值含反斜杠/换行/
# </script> 时产出非法 JS 或 XSS 面。key/value 改用 json.dumps 生成）。
# ---------------------------------------------------------------------------

# 各种"值来自 LLM 不可控"的危险字符：反斜杠 / 换行 / 双引号 / 单引号 /
# </script> / unicode(中文+emoji) / 占位符 {{0}} %s。key 也放危险字符。
_ROUNDTRIP_CASES = {
    "path.windows": r"C:\Users\名字\桌面",          # 反斜杠（旧版尾部 \" 吞引号）
    "path.trailing_backslash": "结尾反斜杠\\",       # 值以反斜杠结尾（最毒的吞引号场景）
    "msg.multiline": "第一行\n第二行\t缩进",          # 真实换行/制表（旧版裸换行语法错）
    "quote.double": '他说"你好"世界',                # 内嵌双引号
    "quote.single": "It's a test",                   # 内嵌单引号
    "xss.script": "</script><script>alert(1)</script>",  # 内联 XSS 面
    "unicode.mix": "你好 🌍 Café résumé",            # 中文 + emoji + 重音
    "placeholder.brace": "剩余 {{0}} 项，共 {{1}}",   # {{n}} 占位符
    "placeholder.printf": "进度 %s%% 完成",           # %s / %% 占位符
    'key.with"quote': "含双引号的 key",              # key 里带双引号
    "control.tab_return": "a\tb\rc",                 # 控制字符
}


@pytest.mark.parametrize("key,value", list(_ROUNDTRIP_CASES.items()))
def test_dump_parse_roundtrip_single(key, value):
    """单条 dump→parse 严格相等（逐条定位失败用）。"""
    out = js_locale.dump_js_locale({key: value})
    parsed = js_locale.parse_js_locale(out)
    assert parsed == {key: value}


def test_dump_parse_roundtrip_all():
    """一次性 dump 全部危险条目，parse 回来键值全等。"""
    out = js_locale.dump_js_locale(_ROUNDTRIP_CASES)
    parsed = js_locale.parse_js_locale(out)
    assert parsed == _ROUNDTRIP_CASES


def test_dump_backslash_does_not_eat_closing_quote():
    """回归：值以反斜杠结尾时，旧版 v.replace('\"',...) 产出 ...\\\" 吞掉闭合引号。

    json.dumps 会把反斜杠转成 \\\\，闭合引号不再被吞 —— 输出可被 JSON 解析。
    """
    out = js_locale.dump_js_locale({"k": "abc\\"})
    # 结尾反斜杠已翻倍转义，字面量正常闭合
    assert r'"k": "abc\\"' in out
    # 整体结构可被 JSON 解析（去 export 包裹 + 尾逗号后）
    _assert_valid_js_syntax(out)


def test_dump_neutralizes_script_close_tag():
    """</script> 被转成 <\\/script>：输出里不含裸 </script>，但 parse 还原回 </script>。"""
    value = "</script>"
    out = js_locale.dump_js_locale({"k": value})
    assert "</script>" not in out          # 裸闭合标签已中和
    assert "<\\/script>" in out            # 换成 JS 等价的 <\/script>
    assert js_locale.parse_js_locale(out) == {"k": value}  # 往返仍相等


def test_dump_output_is_valid_js_syntax():
    """dump 产物是合法 JS：优先 node --check，无 node 时退回 JSON 校验。"""
    out = js_locale.dump_js_locale(_ROUNDTRIP_CASES)
    _assert_valid_js_syntax(out)


def test_dump_structure_unchanged():
    """结构（export 包裹 / 两空格缩进 / 尾逗号 / 键序）与旧版一致。"""
    out = js_locale.dump_js_locale({"a": "1", "b": "2"})
    assert out == 'export default {\n  "a": "1",\n  "b": "2",\n};\n'


# --- 语法校验辅助：node --check 为主，JSON 解析为兜底 -------------------------

def _assert_valid_js_syntax(dump_text):
    node = shutil.which("node")
    if node:                               # 真 JS 引擎校验 ES module 语法（含尾逗号合法）
        import tempfile
        import os
        fd, path = tempfile.mkstemp(suffix=".mjs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(dump_text)
            proc = subprocess.run(
                [node, "--check", path], capture_output=True, text=True,
            )
            assert proc.returncode == 0, f"node --check 失败: {proc.stderr}"
        finally:
            os.unlink(path)
        return
    # 兜底：剥掉 export 包裹 + 结构尾逗号后当 JSON 解析（json.loads 会认 \/ → /）
    body = dump_text[len("export default "):].rstrip()
    assert body.endswith(";")
    body = body[:-1].rstrip()
    body = re.sub(r",(\s*})\s*$", r"\1", body)   # 只去结构末尾那个尾逗号
    json.loads(body)                             # 非法则抛异常，测试失败


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
