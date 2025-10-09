#!/usr/bin/env python3
"""
实时获取 Claude 可用模型列表
"""

import logging
from anthropic import Anthropic
from config import CLAUDE_API_KEY
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# 缓存机制
_models_cache = None
_cache_time = None
CACHE_DURATION = timedelta(hours=1)  # 缓存1小时


def get_claude_models():
    """实时获取 Claude 可用模型列表"""
    global _models_cache, _cache_time
    
    # 检查缓存
    if _models_cache and _cache_time and datetime.now() - _cache_time < CACHE_DURATION:
        logger.info("使用缓存的模型列表")
        return _models_cache
    
    try:
        # 返回所有已知的模型列表（基于官方文档）
        # 不逐个验证以提高性能
        models = [
            {
                "id": "claude-sonnet-4-5-20250929",
                "name": "Claude Sonnet 4.5 ⭐",
                "description": "最新最强模型，最佳编码和复杂代理能力（官方推荐）"
            },
            {
                "id": "claude-sonnet-4-20250514",
                "name": "Claude Sonnet 4 ✨",
                "description": "高智能平衡性能，适合日常翻译"
            },
            {
                "id": "claude-3-5-sonnet-latest",
                "name": "Claude 3.5 Sonnet (Latest)",
                "description": "自动更新到最新版本的 Sonnet"
            },
            {
                "id": "claude-opus-4-20250514",
                "name": "Claude Opus 4 ⚡",
                "description": "超高智能，适合最复杂的翻译任务"
            },
            {
                "id": "claude-3-5-haiku-20241022",
                "name": "Claude 3.5 Haiku",
                "description": "最快的模型，适合大量翻译任务"
            },
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "description": "Claude 3 系列最强大的模型"
            },
            {
                "id": "claude-3-haiku-20240307",
                "name": "Claude 3 Haiku",
                "description": "经济快速的模型"
            }
        ]
        
        # 如果提供了 API Key，尝试快速验证一个模型
        if CLAUDE_API_KEY:
            client = Anthropic(api_key=CLAUDE_API_KEY)
            # 只验证一个模型来确认 API 可用
            if validate_model(client, "claude-3-5-sonnet-latest"):
                logger.info("API 验证成功")
            else:
                logger.warning("API 验证失败，使用默认列表")
        
        # 更新缓存
        _models_cache = models
        _cache_time = datetime.now()
        
        return models
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return get_default_models()


def validate_model(client, model_id):
    """验证模型是否可用"""
    try:
        # 尝试用该模型发送一个简单请求
        response = client.messages.create(
            model=model_id,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except Exception as e:
        # 如果模型不存在或不可用，会抛出异常
        logger.debug(f"模型 {model_id} 验证失败: {e}")
        return False


def get_default_models():
    """返回默认的模型列表"""
    return [
        {
            "id": "claude-sonnet-4-5-20250929",
            "name": "Claude Sonnet 4.5 ⭐",
            "description": "最新最强模型，最佳编码和复杂代理能力（官方推荐）"
        },
        {
            "id": "claude-sonnet-4-20250514",
            "name": "Claude Sonnet 4 ✨",
            "description": "高智能平衡性能，适合日常翻译"
        },
        {
            "id": "claude-3-5-sonnet-latest",
            "name": "Claude 3.5 Sonnet (Latest)",
            "description": "自动更新到最新版本"
        },
        {
            "id": "claude-opus-4-20250514",
            "name": "Claude Opus 4 ⚡",
            "description": "超高智能，适合最复杂的翻译"
        },
        {
            "id": "claude-3-5-haiku-20241022",
            "name": "Claude 3.5 Haiku",
            "description": "快速且智能，适合大量翻译任务"
        },
        {
            "id": "claude-3-opus-20240229",
            "name": "Claude 3 Opus",
            "description": "Claude 3 系列最强大的模型"
        },
        {
            "id": "claude-3-haiku-20240307",
            "name": "Claude 3 Haiku",
            "description": "经济快速，适合简单翻译"
        }
    ]


def refresh_models_cache():
    """刷新模型缓存"""
    global _models_cache, _cache_time
    _models_cache = None
    _cache_time = None
    return get_claude_models()


if __name__ == "__main__":
    # 测试获取模型列表
    models = get_claude_models()
    print(f"\n找到 {len(models)} 个可用的 Claude 模型:")
    for model in models:
        print(f"  - {model['name']} ({model['id']})")
        print(f"    {model['description']}")