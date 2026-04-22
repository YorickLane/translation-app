"""
翻译费用估算 —— 字符数估算（不再依赖 Anthropic count_tokens API）

变更:
- 删除 Anthropic beta count_tokens API 依赖（OpenRouter 不代理）
- 扩展到多 provider 定价（源于 llm_models.AVAILABLE_MODELS）
- UI 应明确标注"估算值"，典型误差 20-30%
"""

import json
import logging

from llm_models import get_model_info, get_default_model_id
from config import BATCH_SIZE

logger = logging.getLogger(__name__)

USD_TO_CNY = 7.3

# 中文源文本 → 目标语的长度相对系数（tokens 数量变化）
OUTPUT_LENGTH_MULTIPLIER = {
    'en': 0.5,  'ja': 0.7,  'ko': 0.8,
    'es': 0.9,  'fr': 0.9,  'de': 1.0,
    'ru': 0.9,  'ar': 0.8,  'pt': 0.9,
    'it': 0.9,  'vi': 1.1,  'th': 0.7,
    'tr': 0.9,  'pl': 0.95, 'nl': 0.9,
    'sv': 0.85, 'no': 0.85, 'da': 0.85,
    'fi': 0.9,  'el': 0.9,  'he': 0.7,
    'hi': 0.8,  'id': 0.9,  'ms': 0.9,
}
DEFAULT_MULTIPLIER = 0.85

# JSON 内容 tokens 估算常数：1 token ≈ 3 characters
CHARS_PER_TOKEN = 3
# 每批次的 prompt 模板开销（schema 说明 + capitalization rule）
PROMPT_OVERHEAD_TOKENS = 600


def estimate_cost(file_path, target_languages, model_id=None):
    """估算翻译费用。

    Args:
        file_path: JSON 语言包路径
        target_languages: 目标语言代码列表
        model_id: OpenRouter 模型 slug（默认用 AVAILABLE_MODELS 的 default）

    Returns:
        dict with model info, token estimates, cost breakdown
        or {'error': ...} on failure
    """
    model_id = model_id or get_default_model_id()
    model_info = get_model_info(model_id)
    if not model_info:
        return {"error": f"未知模型: {model_id}"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"读取文件失败: {e}"}

    total_items = len(data)
    num_batches = max(1, (total_items + BATCH_SIZE - 1) // BATCH_SIZE)
    num_languages = len(target_languages)

    # JSON 序列化后字符数（LLM 实际看到的输入大小）
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_chars = len(json_str)
    json_tokens = json_chars // CHARS_PER_TOKEN
    avg_batch_tokens = max(1, json_tokens // num_batches)

    input_tokens_per_batch = avg_batch_tokens + PROMPT_OVERHEAD_TOKENS

    # 每种语言的输出 tokens（基于长度乘数）
    output_tokens_per_lang = []
    for lang in target_languages:
        lang_code = lang[:2].lower()
        mult = OUTPUT_LENGTH_MULTIPLIER.get(lang_code, DEFAULT_MULTIPLIER)
        lang_output = int(avg_batch_tokens * mult * num_batches)
        output_tokens_per_lang.append(lang_output)

    total_input_tokens = input_tokens_per_batch * num_batches * num_languages
    total_output_tokens = sum(output_tokens_per_lang)

    input_cost = (total_input_tokens / 1_000_000) * model_info['input_price_per_m']
    output_cost = (total_output_tokens / 1_000_000) * model_info['output_price_per_m']
    total_cost = input_cost + output_cost

    return {
        "model": model_info['id'],
        "model_name": model_info['name'],
        "file_size": json_chars,
        "num_keys": total_items,
        "num_languages": num_languages,
        "num_batches": num_batches,
        "batch_size": BATCH_SIZE,
        "estimated_input_tokens": total_input_tokens,
        "estimated_output_tokens": total_output_tokens,
        "estimated_total_tokens": total_input_tokens + total_output_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "total_cost_cny": round(total_cost * USD_TO_CNY, 4),
        "pricing": {
            "input_per_million": model_info['input_price_per_m'],
            "output_per_million": model_info['output_price_per_m'],
        },
        "estimation_note": "字符数估算，典型误差 20-30%",
    }


def format_cost_summary(info):
    """可读的费用摘要。"""
    if "error" in info:
        return f"❌ 错误: {info['error']}"

    return f"""
📊 费用估算（字符数估算，典型误差 20-30%）
━━━━━━━━━━━━━━━━━━━━━━
📁 文件信息:
   键值对: {info['num_keys']}
   文件大小: {info['file_size']:,} 字节
   目标语言: {info['num_languages']}
   批次数: {info['num_batches']} × 每批 {info['batch_size']} 项

🤖 模型: {info['model_name']}
   ${info['pricing']['input_per_million']}/M 输入 | ${info['pricing']['output_per_million']}/M 输出

📈 Token 预估:
   输入: {info['estimated_input_tokens']:,}
   输出: {info['estimated_output_tokens']:,}
   合计: {info['estimated_total_tokens']:,}

💰 费用:
   输入: ${info['input_cost_usd']:.4f}
   输出: ${info['output_cost_usd']:.4f}
   合计: ${info['total_cost_usd']:.4f} (≈ ¥{info['total_cost_cny']:.4f})
━━━━━━━━━━━━━━━━━━━━━━
"""


if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else "uploads/test.json"
    langs = sys.argv[2].split(",") if len(sys.argv) > 2 else ["es", "fr", "de", "ar", "it", "pt"]
    model = sys.argv[3] if len(sys.argv) > 3 else None
    print(format_cost_summary(estimate_cost(test_file, langs, model)))
