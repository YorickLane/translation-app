"""JS 语言包 (`export default {...}`) 的解析与输出 —— Google 与 LLM 两引擎共用。

去掉两引擎里逐字重复的 JS 正则 + `export default` 组装；并把"key 同时剥单/双引号"
的修复统一到两边（旧 translate.py 只剥单引号 → 双引号 key 会产出 ""key"" 非法 JS，
见 commit 7772f65）。

输出转义（dump_js_locale）：key/value 字面量一律用 json.dumps(ensure_ascii=False)
生成 —— JSON 字符串字面量本身就是合法的 JS 字符串字面量，自动处理反斜杠 / 换行 /
引号 / 控制字符。旧版"只把 " 换成 \\""在以下场景产出非法 JS：值含反斜杠（尾部
的 \\" 把闭合引号吞掉）、值含真实换行（字符串字面量裸换行语法错）；另 </script>
在内联 <script> 场景是 XSS 面。翻译值来自 LLM 完全不可控，必须按最坏情况转义。

parse 端（parse_js_locale）与之严格往返：双引号字面量就是合法 JSON，直接 json.loads
还原全部转义；正则改为转义感知，避免旧版 ".*?" 在 \\" 处提前截断字面量。
"""
import json
import re

# 源 key 三种写法: bare(全球到达时间) / 单引号('Settings.xxx') / 双引号("滑动验证")。
# 值: 反引号模板 / 双引号 / 单引号。三种引号字面量都用转义感知 (?:\\.|[^q\\])*，
# 让 \" \' \` 不会把字面量提前截断；re.DOTALL 让值/模板可跨行。
_DQ = r'"(?:\\.|[^"\\])*"'          # 双引号字面量（= 合法 JSON）
_SQ = r"'(?:\\.|[^'\\])*'"          # 单引号字面量
_BT = r"`(?:\\.|[^`\\])*`"          # 反引号模板字面量
_BARE = r"[^\s:'\"`,{}]+"           # 裸 key（无引号标识符 / CJK）

JS_KV_PATTERN = re.compile(
    rf"({_DQ}|{_SQ}|{_BARE})\s*:\s*({_DQ}|{_SQ}|{_BT})", re.DOTALL,
)

# 单引号/反引号字面量（源文件人工写法）用的简单转义表；双引号走 json.loads 不用它。
_JS_SIMPLE_ESCAPE = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v",
    "0": "\0", "\\": "\\", "'": "'", '"': '"', "`": "`", "/": "/",
}


def _is_hex(s, start, length):
    """s[start:start+length] 是否恰为 length 位十六进制。"""
    frag = s[start:start + length]
    return len(frag) == length and all(c in "0123456789abcdefABCDEF" for c in frag)


def _unescape_js(inner):
    """还原单引号/反引号字面量里的 JS 转义（源文件可能带 \\' \\n \\uXXXX 等）。

    未识别的转义（如手写路径里的 \\U）保留反斜杠原样，贴近 JS 引擎的宽松行为，
    也避免吞掉本该保留的反斜杠。双引号字面量不走这里 —— 它是合法 JSON，交给 json.loads。
    """
    if "\\" not in inner:            # 快路径：无转义原样返回，对既有简单值零行为变化
        return inner
    out = []
    i, n = 0, len(inner)
    while i < n:
        c = inner[i]
        if c == "\\" and i + 1 < n:
            nxt = inner[i + 1]
            if nxt == "u" and _is_hex(inner, i + 2, 4):
                out.append(chr(int(inner[i + 2:i + 6], 16)))
                i += 6
                continue
            if nxt == "x" and _is_hex(inner, i + 2, 2):
                out.append(chr(int(inner[i + 2:i + 4], 16)))
                i += 4
                continue
            mapped = _JS_SIMPLE_ESCAPE.get(nxt)
            if mapped is not None:
                out.append(mapped)
            else:                    # 未识别转义：保留反斜杠 + 原字符
                out.append("\\")
                out.append(nxt)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _decode_literal(lit):
    """把捕获到的 JS 字符串字面量（含外层引号）解码成 Python 字符串。"""
    if not lit:
        return lit
    q = lit[0]
    if q == '"':                     # 双引号 = 合法 JSON，转义全交给 json（\/ \n \" \uXXXX）
        try:
            return json.loads(lit)
        except json.JSONDecodeError:
            # 源文件里手写的非法 JSON 转义（如 "C:\Users"）—— 退回宽松解码，勿丢内容
            return _unescape_js(lit[1:-1])
    if q in "'`":                    # 单引号 / 反引号：源文件写法，手工还原转义
        return _unescape_js(lit[1:-1])
    return lit                       # 裸字面量：原样


def parse_js_locale(content):
    """从 JS 文件内容提取 {key: value} dict（解引号、还原转义、跳过空值）。

    转义感知正则 + json.loads / _unescape_js 解码，保证与 dump_js_locale 的
    json.dumps 输出严格往返（反斜杠 / 换行 / 引号 / 单引号 / unicode / </script> /
    占位符 等）。双引号 key 也会剥净，避免输出时再包一层 => ""key"" 非法 JS。
    """
    result = {}
    for k, v in JS_KV_PATTERN.findall(content):
        clean_k = _decode_literal(k.strip())
        clean_v = _decode_literal(v.strip())
        if clean_v.strip():          # 空值 / 纯空白值跳过（与旧行为一致）
            result[clean_k] = clean_v
    return result


def dump_js_locale(translated_data):
    """把 {key: value} 组装成 `export default {...}` JS 文本。

    key/value 字面量一律 json.dumps(ensure_ascii=False) —— JSON 字符串字面量即合法
    JS 字符串字面量，自动处理反斜杠 / 换行 / 引号 / 控制字符；再把 `</` → `<\\/`
    （JS 里等价，parse 侧 json.loads 会把 \\/ 原样还原成 /，不破坏往返）以中和
    `</script>` 内联 XSS 面。整体结构（export 包裹 / 两空格缩进 / 尾逗号 / 键序）
    与旧版保持一致。
    """
    lines = ["export default {\n"]
    for k, v in translated_data.items():
        key_lit = json.dumps(k, ensure_ascii=False).replace("</", "<\\/")
        val_lit = json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
        lines.append(f"  {key_lit}: {val_lit},\n")
    lines.append("};\n")
    return "".join(lines)
