"""
LLM 翻译客户端 —— OpenRouter + OpenAI SDK + structured output (json_schema)

核心设计:
- 单一 OpenAI client，base_url 指向 OpenRouter
- 使用 response_format=json_schema 强制返回 {"translations": [...]} 格式
- 这取代了原 Claude 直连里脆弱的 regex JSON 清理 (clean_json_response)
- API key 来源: shell env OPENROUTER_API_KEY (SoT: ~/.config/secrets.env)
"""

import json
import logging
from typing import Optional
from openai import OpenAI, APIError
from config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# OpenRouter 推荐但非强制的 headers（用于 leaderboard / usage attribution）
_ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://github.com/YorickLane/translation-app",
    "X-OpenRouter-Title": "Translation App",
}

# 懒加载 client 单例
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """返回 OpenAI client（指向 OpenRouter）。Fail fast if key missing."""
    global _client
    if _client is not None:
        return _client

    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY 未在 shell 环境变量中。\n"
            "修复步骤:\n"
            "1. 确认 ~/.config/secrets.env 含 `export OPENROUTER_API_KEY=sk-or-v1-...`\n"
            "2. 确认 ~/.zshrc 末尾 source 该文件\n"
            "3. 从 terminal (非 Dock/Spotlight) 启动当前进程以继承 env\n"
            "详见 ~/claude-soul/protocols/secrets-management.md"
        )

    _client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
    return _client


# JSON Schema: 强制 LLM 返回 {"translations": ["...", "..."]}
_TRANSLATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "translations",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["translations"],
            "additionalProperties": False,
        },
    },
}


def translate_batch(
    values: list[str],
    target_lang_name: str,
    target_lang_code: str,
    model: str,
    temperature: float = 0.1,
    capitalization_rule: str = "",
    max_tokens: int = 8192,
) -> list[str]:
    """翻译一批字符串到目标语言，返回同序数组。

    Args:
        values: 待翻译的字符串列表
        target_lang_name: 语言全名 (e.g. "Spanish", "Arabic")
        target_lang_code: 语言代码，仅用于 prompt 内提示 (e.g. "es", "ar")
        model: OpenRouter model slug (e.g. "anthropic/claude-sonnet-4.6")
        temperature: 采样温度
        capitalization_rule: 语言特定大写规则说明（直接注入 prompt）
        max_tokens: 输出上限

    Returns:
        翻译后的字符串列表，长度与 values 一致

    Raises:
        ValueError: 返回数量不匹配 / API key 缺失
        APIError: 上游 provider 错误（rate limit / 模型不支持 structured output 等）
    """
    if not values:
        return []

    prompt = _build_prompt(values, target_lang_name, target_lang_code, capitalization_rule)

    logger.info(f"[OpenRouter] 调用 {model} 翻译 {len(values)} 项 → {target_lang_name}")

    response = _get_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        response_format=_TRANSLATION_SCHEMA,
        extra_headers=_ATTRIBUTION_HEADERS,
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError(f"{model} 返回空响应")

    # structured output 保证是 valid JSON object 符合 schema，无需 regex 清理
    parsed = json.loads(raw)
    translations = parsed["translations"]

    if len(translations) != len(values):
        raise ValueError(
            f"翻译数量不匹配: 输入 {len(values)} 项，返回 {len(translations)} 项"
        )

    logger.info(f"[OpenRouter] {model} 成功返回 {len(translations)} 项翻译")
    return translations


def _build_prompt(
    values: list[str],
    target_lang_name: str,
    target_lang_code: str,
    capitalization_rule: str,
) -> str:
    """构建翻译 prompt。

    相比旧版 Claude prompt，删除了所有 JSON 格式化说明（"output only JSON, no markdown"
    之类）—— structured output 强制 schema，无需再告诉模型输出什么结构。
    """
    json_input = json.dumps(values, ensure_ascii=False, indent=2)

    cap_section = ""
    if capitalization_rule:
        cap_section = f"\nCAPITALIZATION RULES for {target_lang_name}:\n{capitalization_rule}\n"

    return f"""Translate each string in the following array to {target_lang_name}.

REQUIREMENTS:
1. Translate each string to {target_lang_name} ({target_lang_code}) — NEVER return English for non-English target
2. Return exactly {len(values)} translations in the same order as input
3. Preserve placeholders (like {{{{0}}}}, %s, {{name}}), HTML tags, and special formatting
4. Keep the meaning and tone appropriate for UI / application strings
{cap_section}
Input strings ({len(values)} items):
{json_input}

Return the translations as the `translations` field of a JSON object."""


def test_connectivity(model: str = "anthropic/claude-sonnet-4.6") -> bool:
    """冒烟测试：验证 OR API key + 网络 + 模型可达。"""
    try:
        result = translate_batch(
            values=["Hello", "Cancel"],
            target_lang_name="Spanish",
            target_lang_code="es",
            model=model,
            temperature=0.1,
        )
        print(f"✅ OpenRouter 连通正常 (模型: {model})")
        print(f"   测试输出: {result}")
        return True
    except Exception as e:
        print(f"❌ OpenRouter 连通失败: {e}")
        return False


if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "anthropic/claude-sonnet-4.6"
    test_connectivity(model)
