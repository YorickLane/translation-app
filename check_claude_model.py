#!/usr/bin/env python3
"""
检查当前配置的 Claude 模型
"""

import os
from config import CLAUDE_MODEL, CLAUDE_API_KEY, CLAUDE_MODELS
from anthropic import Anthropic

def check_claude_model():
    """检查并显示当前 Claude 模型配置"""
    print("=" * 50)
    print("🤖 Claude API 配置检查")
    print("=" * 50)
    
    # 检查 API Key
    if CLAUDE_API_KEY:
        # 隐藏部分 API Key
        masked_key = CLAUDE_API_KEY[:15] + "..." + CLAUDE_API_KEY[-4:]
        print(f"✅ API Key: {masked_key}")
    else:
        print("❌ API Key: 未配置")
        return
    
    # 显示配置的模型
    print(f"📊 配置的模型: {CLAUDE_MODEL}")
    
    # 尝试调用 API 获取实际使用的模型信息
    try:
        client = Anthropic(api_key=CLAUDE_API_KEY)
        
        # 发送一个简单的请求
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Hello' in one word only."}]
        )
        
        # 显示响应信息
        print(f"✅ API 连接成功")
        print(f"📝 模型响应: {response.content[0].text.strip()}")
        
        # 如果有模型信息在响应中
        if hasattr(response, 'model'):
            print(f"🎯 实际使用的模型: {response.model}")
        
        print("\n💡 提示: 使用 'claude-3-5-sonnet-latest' 会自动使用最新版本的 Sonnet 模型")
        
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
    
    # 显示可用的模型
    print("\n📋 可用的 Claude 模型:")
    for model in CLAUDE_MODELS:
        print(f"   • {model['name']} ({model['id']})")
        print(f"     {model['description']}")
    
    print("=" * 50)

if __name__ == "__main__":
    check_claude_model()