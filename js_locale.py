"""JS 语言包 (`export default {...}`) 的解析与输出 —— Google 与 LLM 两引擎共用。

去掉两引擎里逐字重复的 JS 正则 + `export default` 组装；并把"key 同时剥单/双引号"
的修复统一到两边（旧 translate.py 只剥单引号 → 双引号 key 会产出 ""key"" 非法 JS，
见 commit 7772f65）。
"""
import re

# 源 key 三种写法: bare(全球到达时间) / 单引号('Settings.xxx') / 双引号("滑动验证")。
# 值: 反引号模板 / 双引号 / 单引号。re.DOTALL 让值跨行。
JS_KV_PATTERN = re.compile(
    r'(\'[^\']+\'|[^\s:]+):\s*(`.*?`|".*?"|\'.*?\')', re.DOTALL,
)


def parse_js_locale(content):
    """从 JS 文件内容提取 {key: value} dict（剥引号、跳过空值）。

    [^\\s:]+ 分支会把双引号一起吞进 key，必须同时剥单/双引号，否则双引号残留
    → 输出时再包一层 => ""key"" 非法 JS。
    """
    result = {}
    for k, v in JS_KV_PATTERN.findall(content):
        clean_k = k.strip().strip("\"'")
        clean_v = v.strip().strip("`\"'")
        if clean_v.strip():
            result[clean_k] = clean_v
    return result


def dump_js_locale(translated_data):
    """把 {key: value} 组装成 `export default {...}` JS 文本（双引号转义）。"""
    lines = ["export default {\n"]
    for k, v in translated_data.items():
        escaped = v.replace('"', '\\"')
        lines.append(f'  "{k}": "{escaped}",\n')
    lines.append("};\n")
    return "".join(lines)
