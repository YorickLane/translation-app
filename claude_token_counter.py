#!/usr/bin/env python3
"""
Claude API Token 计算和费用预估
"""

import json
import logging
from anthropic import Anthropic
from config import CLAUDE_API_KEY

logger = logging.getLogger(__name__)

# Claude 模型定价 (2025年价格，单位：美元/百万 tokens)
CLAUDE_PRICING = {
    # Sonnet 4
    "claude-sonnet-4-20250514": {
        "input": 3.00,    # $3 per million input tokens
        "output": 15.00,  # $15 per million output tokens
        "name": "Claude Sonnet 4"
    },
    # Opus 4
    "claude-opus-4-20250514": {
        "input": 15.00,   # $15 per million input tokens
        "output": 75.00,  # $75 per million output tokens
        "name": "Claude Opus 4"
    },
    # Claude 3.5 models
    "claude-3-5-sonnet-latest": {
        "input": 3.00,
        "output": 15.00,
        "name": "Claude 3.5 Sonnet (Latest)"
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "name": "Claude 3.5 Sonnet"
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,    # $0.80 per million input tokens
        "output": 4.00,   # $4 per million output tokens
        "name": "Claude 3.5 Haiku"
    },
    # Claude 3 models
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
        "name": "Claude 3 Opus"
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,    # $0.25 per million input tokens
        "output": 1.25,   # $1.25 per million output tokens
        "name": "Claude 3 Haiku"
    }
}


def count_tokens_for_translation(file_path, target_languages, model="claude-3-5-sonnet-latest"):
    """
    计算翻译任务的 token 数量和预估费用
    
    Args:
        file_path: JSON 文件路径
        target_languages: 目标语言列表
        model: Claude 模型 ID
    
    Returns:
        dict: 包含 token 计数和费用预估的字典
    """
    if not CLAUDE_API_KEY:
        return {
            "error": "未配置 CLAUDE_API_KEY",
            "estimated": True,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0
        }
    
    try:
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 估算方法：
        # 1. 输入 tokens = 原文本 + prompt 模板
        # 2. 输出 tokens ≈ 输入 tokens * 1.2 (翻译通常会稍微增加长度)
        
        # 计算原始文本的字符数
        total_chars = 0
        for key, value in data.items():
            total_chars += len(key) + len(str(value))
        
        # 估算 tokens (1 token ≈ 4 characters)
        base_tokens = total_chars // 4
        
        # 每个翻译任务的 prompt 模板大约 200 tokens
        prompt_tokens_per_language = 200
        
        # 计算总的输入和输出 tokens
        num_languages = len(target_languages)
        total_input_tokens = (base_tokens + prompt_tokens_per_language) * num_languages
        total_output_tokens = int(base_tokens * 1.2 * num_languages)  # 翻译后文本通常稍长
        
        # 获取定价信息
        pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-3-5-sonnet-latest"])
        
        # 计算费用 (转换为百万 tokens)
        input_cost = (total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (total_output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "model": model,
            "model_name": pricing["name"],
            "file_size": len(json.dumps(data, ensure_ascii=False)),
            "num_keys": len(data),
            "num_languages": num_languages,
            "estimated_input_tokens": total_input_tokens,
            "estimated_output_tokens": total_output_tokens,
            "estimated_total_tokens": total_input_tokens + total_output_tokens,
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
            "total_cost_usd": round(total_cost, 4),
            "total_cost_cny": round(total_cost * 7.3, 4),  # 假设汇率 1 USD = 7.3 CNY
            "pricing": {
                "input_per_million": pricing["input"],
                "output_per_million": pricing["output"]
            }
        }
        
    except Exception as e:
        logger.error(f"计算 token 时出错: {e}")
        return {
            "error": str(e),
            "estimated": True,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0
        }


def count_tokens_with_api(file_path, target_language, model="claude-3-5-sonnet-latest"):
    """
    使用 Claude API 精确计算 token 数量
    注意：这会消耗 API 调用次数，但不会产生 token 费用
    """
    if not CLAUDE_API_KEY:
        return None
    
    try:
        client = Anthropic(api_key=CLAUDE_API_KEY)
        
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 构建翻译 prompt
        json_input = json.dumps(data, ensure_ascii=False, indent=2)
        prompt = f"""Please translate the following JSON content to {target_language}. 
Keep the JSON structure exactly the same, only translate the values (not the keys).
Maintain any special formatting, placeholders (like {{0}}), or HTML tags.

Input JSON:
{json_input}

Output the translated JSON only, without any explanation."""
        
        # 使用 count_tokens API
        response = client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "input_tokens": response.input_tokens,
            "model": model
        }
        
    except Exception as e:
        logger.error(f"API token 计算失败: {e}")
        return None


def format_cost_summary(token_info):
    """格式化费用摘要"""
    if "error" in token_info:
        return f"❌ 错误: {token_info['error']}"
    
    summary = f"""
📊 Token 计算和费用预估
━━━━━━━━━━━━━━━━━━━━━━
📁 文件信息:
   • 键值对数量: {token_info['num_keys']}
   • 文件大小: {token_info['file_size']:,} 字节
   • 目标语言数: {token_info['num_languages']}

🤖 模型: {token_info['model_name']}
   • 输入价格: ${token_info['pricing']['input_per_million']}/百万 tokens
   • 输出价格: ${token_info['pricing']['output_per_million']}/百万 tokens

📈 Token 预估:
   • 输入 Tokens: {token_info['estimated_input_tokens']:,}
   • 输出 Tokens: {token_info['estimated_output_tokens']:,}
   • 总计 Tokens: {token_info['estimated_total_tokens']:,}

💰 费用预估:
   • 输入费用: ${token_info['input_cost_usd']:.4f}
   • 输出费用: ${token_info['output_cost_usd']:.4f}
   • 总计 (USD): ${token_info['total_cost_usd']:.4f}
   • 总计 (CNY): ¥{token_info['total_cost_cny']:.4f}
━━━━━━━━━━━━━━━━━━━━━━
"""
    return summary


if __name__ == "__main__":
    # 测试 token 计算
    test_file = "uploads/zh-cn.json"
    test_languages = ["en", "ja", "ko", "es", "fr"]
    test_model = "claude-3-5-sonnet-latest"
    
    result = count_tokens_for_translation(test_file, test_languages, test_model)
    print(format_cost_summary(result))