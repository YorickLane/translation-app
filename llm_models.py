"""
LLM 模型目录 —— OpenRouter 上的三档推荐模型

设计原则:
- 3 档覆盖 90% 场景（质量 / 备选 / 经济），不铺 20 个选项避免选择困难
- 硬编码，不做 runtime API 发现（简单 + 可靠 + 不浪费 API 调用）
- 定价与 OpenRouter live 数据对齐（2026-04-22 校准）
- 新增模型 = 改这个文件 + cost_estimator.py 的 MODEL_PRICING
"""

from typing import Literal, TypedDict


class ModelInfo(TypedDict):
    id: str
    name: str
    description: str
    tier: Literal["quality", "alternative", "economy"]
    input_price_per_m: float   # USD per 1M input tokens
    output_price_per_m: float  # USD per 1M output tokens
    context_length: int
    default: bool


# 模型目录（2026-04-22 校准自 https://openrouter.ai/api/v1/models）
#
# ⚠️ Opus 4.7+ breaking change: 设 temperature/top_p/top_k 为非默认值会 400 error
#    (源: platform.claude.com/docs/en/about-claude/models/whats-new, 2026-04-22)
#    如果未来加 `anthropic/claude-opus-4.7` 或 `anthropic/claude-opus-5*` 进这个 list，
#    必须先在 llm_client.py 的 translate_batch() 里按 slug 条件化 strip 掉 temperature。
#    当前 3 档（Sonnet 4.6 / GPT-5.4 / Gemini Flash Lite）都支持 temperature，无需处理。
AVAILABLE_MODELS: list[ModelInfo] = [
    {
        "id": "anthropic/claude-sonnet-4.6",
        "name": "Claude Sonnet 4.6 ⭐",
        "description": "质量档 — 翻译质量标杆，多语言稳定，推荐生产默认",
        "tier": "quality",
        "input_price_per_m": 3.00,
        "output_price_per_m": 15.00,
        "context_length": 1_000_000,
        "default": True,
    },
    {
        "id": "openai/gpt-5.4",
        "name": "GPT-5.4 ✨",
        "description": "备选档 — 同价位替代方案，推理强；Sonnet 故障时可切换",
        "tier": "alternative",
        "input_price_per_m": 2.50,
        "output_price_per_m": 15.00,
        "context_length": 1_050_000,
        "default": False,
    },
    {
        "id": "google/gemini-3.1-flash-lite-preview",
        "name": "Gemini 3.1 Flash Lite 💰",
        "description": "经济档 — 比 Sonnet 便宜 12x，多语言能力扎实，大批量翻译首选",
        "tier": "economy",
        "input_price_per_m": 0.25,
        "output_price_per_m": 1.50,
        "context_length": 1_048_576,
        "default": False,
    },
]


def get_models() -> list[ModelInfo]:
    """返回所有可用模型。"""
    return AVAILABLE_MODELS


def get_default_model_id() -> str:
    """返回 default 标记的模型 ID。"""
    for m in AVAILABLE_MODELS:
        if m["default"]:
            return m["id"]
    return AVAILABLE_MODELS[0]["id"]


def get_model_info(model_id: str) -> ModelInfo | None:
    """按 ID 查找模型元信息，找不到返回 None。"""
    for m in AVAILABLE_MODELS:
        if m["id"] == model_id:
            return m
    return None


if __name__ == "__main__":
    print(f"可用 AI 模型（共 {len(AVAILABLE_MODELS)} 个）:\n")
    for m in AVAILABLE_MODELS:
        mark = " [默认]" if m["default"] else ""
        print(f"  {m['name']}{mark}")
        print(f"    ID: {m['id']}")
        print(f"    定位: {m['description']}")
        print(f"    价格: ${m['input_price_per_m']}/M in, ${m['output_price_per_m']}/M out")
        print(f"    上下文: {m['context_length']:,} tokens\n")
