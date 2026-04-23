#!/bin/bash

echo "🚀 启动翻译应用..."

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 未找到虚拟环境，请先运行 ./setup.sh 进行安装"
    exit 1
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 凭证检查（OpenRouter 或 Google 至少一个）
has_or=0
has_google=0
[ -n "$OPENROUTER_API_KEY" ] && has_or=1
[ -f "serviceKey.json" ] && has_google=1

if [ $has_or -eq 0 ] && [ $has_google -eq 0 ]; then
    echo "❌ 未检测到任何翻译引擎凭证，至少需要一个："
    echo "   • OpenRouter（推荐）: 在 ~/.config/secrets.env 设置 OPENROUTER_API_KEY"
    echo "   • Google Translate: 项目根放置 serviceKey.json"
    echo "   详见 README.md"
    exit 1
fi

[ $has_or -eq 1 ] && echo "✅ OpenRouter LLM 引擎可用（主引擎）"
if [ $has_google -eq 1 ]; then
    echo "✅ Google Translate 可用（完整语言列表 + 回退引擎）"
else
    echo "⚠️  serviceKey.json 不存在 — 语言列表降级到 20 种 fallback，Google 引擎不可用"
fi

# 启动应用
echo ""
echo "🌐 启动Flask应用..."
echo "应用将在 http://127.0.0.1:5000 启动"
echo "按 Ctrl+C 停止应用"
echo ""

python app.py
