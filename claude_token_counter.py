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
        
        # 导入批处理配置
        from config import BATCH_SIZE
        
        # 计算批次数量
        total_items = len(data)
        num_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE
        
        # 更准确的 token 估算：
        # 1. JSON 序列化后的实际大小（包含缩进、引号等）
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        json_chars = len(json_str)
        
        # 2. 更准确的字符到 token 转换率
        # 对于 JSON 内容，1 token ≈ 3 characters（考虑到特殊字符和格式）
        json_tokens_per_batch = json_chars // 3
        
        # 3. Prompt 模板的实际大小（每批）
        # 包含指令、示例、格式说明等
        prompt_template_tokens = 800  # 实际 prompt 更长
        
        # 4. 每批的输入 tokens
        # 注意：每批都包含部分 JSON 数据，不是整个文件
        avg_tokens_per_batch = json_tokens_per_batch // num_batches
        input_tokens_per_batch = avg_tokens_per_batch + prompt_template_tokens
        
        # 5. 输出 tokens 估算（根据目标语言调整）
        # 中文到不同语言的典型长度变化
        output_multipliers = {
            'en': 0.5,      # 英文通常比中文短
            'ja': 0.7,      # 日文略短
            'ko': 0.8,      # 韩文略短
            'es': 0.9,      # 西班牙语接近
            'fr': 0.9,      # 法语接近
            'de': 1.0,      # 德语略长
            'ru': 0.9,      # 俄语接近
            'ar': 0.8,      # 阿拉伯语略短
            'pt': 0.9,      # 葡萄牙语接近
            'it': 0.9,      # 意大利语接近
            'vi': 1.1,      # 越南语略长
            'th': 0.7,      # 泰语略短
            'tr': 0.9,      # 土耳其语接近
            'pl': 0.95,     # 波兰语略长
            'nl': 0.9,      # 荷兰语接近
            'sv': 0.85,     # 瑞典语略短
            'no': 0.85,     # 挪威语略短
            'da': 0.85,     # 丹麦语略短
            'fi': 0.9,      # 芬兰语接近
            'el': 0.9,      # 希腊语接近
            'he': 0.7,      # 希伯来语较短
            'hi': 0.8,      # 印地语略短
            'id': 0.9,      # 印尼语接近
            'ms': 0.9,      # 马来语接近
        }
        
        # 计算语言数量
        num_languages = len(target_languages)
        
        # 计算每种语言的输出 tokens
        output_tokens_per_language = []
        for lang in target_languages:
            # 使用语言代码的前两个字符匹配
            lang_code = lang[:2].lower()
            multiplier = output_multipliers.get(lang_code, 0.85)  # 默认 0.85
            lang_output_tokens = int(avg_tokens_per_batch * multiplier * num_batches)
            output_tokens_per_language.append(lang_output_tokens)
        
        # 总输出 tokens
        output_tokens_per_batch = sum(output_tokens_per_language) // (num_batches * num_languages) if num_languages > 0 else int(avg_tokens_per_batch * 0.85)
        
        # 6. 计算所有语言的总 tokens
        total_input_tokens = input_tokens_per_batch * num_batches * num_languages
        total_output_tokens = sum(output_tokens_per_language) if output_tokens_per_language else 0
        
        # 获取定价信息
        pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-3-5-sonnet-latest"])
        
        # 计算费用 (转换为百万 tokens)
        input_cost = (total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (total_output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "model": model,
            "model_name": pricing["name"],
            "file_size": len(json_str),
            "num_keys": len(data),
            "num_languages": num_languages,
            "num_batches": num_batches,
            "batch_size": BATCH_SIZE,
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
            },
            "estimation_note": "预估可能有 20-30% 的误差，实际费用取决于内容复杂度"
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


def count_tokens_with_api(file_path, target_languages, model="claude-3-5-sonnet-latest"):
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
        
        # 导入批处理配置
        from config import BATCH_SIZE
        
        # 计算批次数量
        total_items = len(data)
        num_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE
        
        # 取一个批次的数据作为样本
        sample_size = min(BATCH_SIZE, total_items)
        sample_data = dict(list(data.items())[:sample_size])
        
        total_input_tokens = 0
        
        # 对每种语言计算一次
        for target_language in target_languages[:1]:  # 只测试一种语言，然后乘以语言数
            # 构建翻译 prompt
            json_input = json.dumps(sample_data, ensure_ascii=False, indent=2)
            prompt = f"""Please translate the following JSON content to {target_language}. 
Keep the JSON structure exactly the same, only translate the values (not the keys).
Maintain any special formatting, placeholders (like {{0}}), or HTML tags.

Input JSON:
{json_input}

Output the translated JSON only, without any explanation."""
            
            # 使用 count_tokens API
            try:
                response = client.beta.messages.count_tokens(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
            except AttributeError:
                # 如果 beta 接口不可用，尝试直接调用
                response = client.messages.count_tokens(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
            
            # 一个批次的 tokens
            batch_tokens = response.input_tokens
            
            # 计算所有批次的总 tokens
            total_input_tokens = batch_tokens * num_batches * len(target_languages)
        
        # 估算输出 tokens（根据目标语言调整）
        # 中文到不同语言的典型长度变化
        output_multipliers = {
            'en': 0.5,      # 英文通常比中文短
            'ja': 0.7,      # 日文略短
            'ko': 0.8,      # 韩文略短
            'es': 0.9,      # 西班牙语接近
            'fr': 0.9,      # 法语接近
            'de': 1.0,      # 德语略长
            'ru': 0.9,      # 俄语接近
            'ar': 0.8,      # 阿拉伯语略短
            'pt': 0.9,      # 葡萄牙语接近
            'it': 0.9,      # 意大利语接近
        }
        
        # 计算平均输出倍数
        total_multiplier = 0
        for lang in target_languages:
            # 使用语言代码的前两个字符匹配
            lang_code = lang[:2].lower()
            multiplier = output_multipliers.get(lang_code, 0.85)  # 默认 0.85
            total_multiplier += multiplier
        
        avg_multiplier = total_multiplier / len(target_languages) if target_languages else 0.85
        estimated_output_tokens = int(total_input_tokens * avg_multiplier)
        
        # 获取定价信息
        pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-3-5-sonnet-latest"])
        
        # 计算费用
        input_cost = (total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "method": "api_count",
            "model": model,
            "model_name": pricing["name"],
            "file_size": len(json.dumps(data, ensure_ascii=False)),
            "num_keys": len(data),
            "num_languages": len(target_languages),
            "num_batches": num_batches,
            "batch_size": BATCH_SIZE,
            "sample_batch_tokens": batch_tokens,
            "estimated_input_tokens": total_input_tokens,  # 添加这个字段
            "total_input_tokens": total_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": total_input_tokens + estimated_output_tokens,  # 添加这个字段
            "total_tokens": total_input_tokens + estimated_output_tokens,
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
            "total_cost_usd": round(total_cost, 4),
            "total_cost_cny": round(total_cost * 7.3, 4),
            "pricing": {
                "input_per_million": pricing["input"],
                "output_per_million": pricing["output"]
            },
            "accuracy_note": "使用 API 精确计算输入 tokens，输出基于经验估算"
        }
        
    except Exception as e:
        logger.error(f"API token 计算失败: {e}")
        logger.error(f"错误类型: {type(e).__name__}")
        logger.error(f"错误详情: {str(e)}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        return None


def format_cost_summary(token_info):
    """格式化费用摘要"""
    if "error" in token_info:
        return f"❌ 错误: {token_info['error']}"
    
    # 判断是否使用了 API 计算
    if token_info.get('method') == 'api_count':
        method_text = "🎯 计算方式: API 精确计算（输入）+ 经验估算（输出）"
        input_label = "精确输入 Tokens"
        output_label = "估算输出 Tokens"
    else:
        method_text = "📐 计算方式: 基于平均值估算"
        input_label = "输入 Tokens 预估"
        output_label = "输出 Tokens 预估"
    
    summary = f"""
📊 Token 计算和费用预估
━━━━━━━━━━━━━━━━━━━━━━
{method_text}

📁 文件信息:
   • 键值对数量: {token_info.get('num_keys', 'N/A')}
   • 文件大小: {token_info.get('file_size', 0):,} 字节
   • 目标语言数: {token_info['num_languages']}
   • 批次数量: {token_info.get('num_batches', 'N/A')} (每批 {token_info.get('batch_size', token_info.get('BATCH_SIZE', 10))} 项)

🤖 模型: {token_info['model_name']}
   • 输入价格: ${token_info.get('pricing', {}).get('input_per_million', 'N/A')}/百万 tokens
   • 输出价格: ${token_info.get('pricing', {}).get('output_per_million', 'N/A')}/百万 tokens

📈 Token 计算:
   • {input_label}: {token_info.get('total_input_tokens', token_info.get('estimated_input_tokens', 0)):,}
   • {output_label}: {token_info.get('estimated_output_tokens', 0):,}
   • 总计 Tokens: {token_info.get('total_tokens', token_info.get('estimated_total_tokens', 0)):,}

💰 费用预估:
   • 输入费用: ${token_info['input_cost_usd']:.4f}
   • 输出费用: ${token_info['output_cost_usd']:.4f}
   • 总计 (USD): ${token_info['total_cost_usd']:.4f}
   • 总计 (CNY): ¥{token_info['total_cost_cny']:.4f}

⚠️  {token_info.get('accuracy_note', token_info.get('estimation_note', ''))}
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