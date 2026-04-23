#!/bin/bash

# 翻译应用一键安装脚本
echo "🚀 开始安装翻译应用..."

# 检查Python版本
echo "📋 检查Python版本..."
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python版本检查通过: $python_version"
    # FutureWarning 提醒（google-* 库已标 3.9 EOL）
    if [ "$(printf '%s\n' "3.10" "$python_version" | sort -V | head -n1)" != "3.10" ]; then
        echo "ℹ️  建议升级到 Python 3.10+（google-api-core 已标记 3.9 EOL）"
    fi
else
    echo "❌ Python版本过低，需要3.8+，当前版本: $python_version"
    exit 1
fi

# 创建虚拟环境
echo "📦 创建Python虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功"
else
    echo "ℹ️  虚拟环境已存在"
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "⬆️  升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📥 安装项目依赖..."
pip install -r requirements.txt

# 检查Google Cloud凭证（可选 — 语言列表 + 回退引擎）
echo ""
echo "🔑 检查Google Cloud凭证（可选）..."
if [ ! -f "serviceKey.json" ]; then
    echo "ℹ️  未找到 serviceKey.json（可选 — LLM 引擎不需要）"
    echo "   如需 Google Translate 作为回退或获取完整语言列表，请参见 README.md"
else
    echo "✅ 找到 serviceKey.json，验证凭证..."
    python -c "from google.cloud import translate_v2 as translate; c=translate.Client(); langs=c.get_languages(); print(f'✅ Google 凭证有效，拉到 {len(langs)} 种语言')" || echo "⚠️  Google 凭证验证失败（详见上方错误）"
fi

# 检查 OpenRouter API key
echo ""
echo "🔑 检查 OpenRouter API Key..."
if [ -n "$OPENROUTER_API_KEY" ]; then
    echo "✅ OPENROUTER_API_KEY 已设置（${#OPENROUTER_API_KEY} 字符）"
else
    echo "⚠️  OPENROUTER_API_KEY 未设置（LLM 引擎不可用）"
    echo "   推荐配置方式（secrets SoT 模式）:"
    echo "     echo 'export OPENROUTER_API_KEY=sk-or-v1-...' >> ~/.config/secrets.env"
    echo "     然后确保 ~/.zshrc 末尾有: [ -f ~/.config/secrets.env ] && source ~/.config/secrets.env"
    echo "     重新 source ~/.zshrc 或开新 terminal"
fi

echo ""
echo "🎉 安装完成！"
echo ""
echo "📖 使用说明："
echo "1. 激活虚拟环境: source venv/bin/activate"
echo "2. 启动应用: python app.py（或 ./start.sh）"
echo "3. 在浏览器中访问: http://127.0.0.1:5000"
echo ""
echo "如果遇到问题，请查看README.md中的故障排除部分"
