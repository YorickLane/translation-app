#!/usr/bin/env python3
"""无头批量翻译 CLI —— 复用 translation_runner，便于自动化 / CI / 无浏览器批量。

示例:
  ./venv/bin/python cli.py uploads/zh-CN.json --langs zh-TW,es,fr
  ./venv/bin/python cli.py strings.js --langs ja --model openai/gpt-5.4 --out out/
  ./venv/bin/python cli.py --list-models
"""
import argparse
import os
import sys

import config
from llm_models import get_models
from translation_runner import translate_single_file


def _stdout_progress(pct, message):
    print(f"  [{pct:5.1f}%] {message}")


def build_parser():
    p = argparse.ArgumentParser(
        description="批量翻译 .json/.js 语言包到多语言（无头，不启 Web）"
    )
    p.add_argument("source", nargs="?", help="源 .json/.js 文件路径")
    p.add_argument("--langs", help="逗号分隔的目标语言代码，如 zh-TW,es,fr")
    p.add_argument(
        "--model", default=config.DEFAULT_MODEL,
        help=f"OpenRouter 模型 slug（默认 {config.DEFAULT_MODEL}）",
    )
    p.add_argument(
        "--engine", default="openrouter", choices=["openrouter", "google"],
        help="翻译引擎（默认 openrouter）",
    )
    p.add_argument("--out", default="output", help="输出目录（默认 output/）")
    p.add_argument(
        "--list-models", action="store_true", help="列出可用模型并退出",
    )
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        for m in get_models():
            mark = " [默认]" if m["default"] else ""
            print(f"{m['id']}{mark} — {m['description']}")
        return 0

    if not args.source or not args.langs:
        parser.error("需要 source 与 --langs（或用 --list-models）")

    if not os.path.isfile(args.source):
        print(f"❌ 文件不存在: {args.source}", file=sys.stderr)
        return 1

    langs = [s.strip() for s in args.langs.split(",") if s.strip()]
    if not langs:
        print("❌ --langs 为空", file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)

    failures = 0
    for lang in langs:
        print(f"→ {args.source} → {lang} ({args.engine}/{args.model})")
        try:
            _name, path = translate_single_file(
                args.source, lang, args.engine, args.model, args.out, _stdout_progress
            )
            print(f"  ✅ {path}")
        except Exception as e:
            failures += 1
            print(f"  ❌ {lang} 失败: {e}", file=sys.stderr)

    print(f"\n完成: {len(langs) - failures}/{len(langs)} 成功 → {args.out}/")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
