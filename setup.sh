#!/bin/bash

# 翻译应用一键安装脚本
# 注：本项目 venv 为手动维护（手动 ./setup.sh / ./start.sh），非常驻服务，不受
#     claude-soul runtime-versions 探针追踪；Python 目标见 .python-version（3.14.x）。
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

# 创建/校验虚拟环境
# 只查 [ -d venv ] 不够 — relocation 或 Python 升级会留下“目录在但坏掉”的 venv：
#   · activate 硬编码绝对路径（mv .venv→venv 后指向幽灵目录 → command not found）
#   · console-script（pip/flask）的 shebang 指向旧解释器 → bad interpreter
# 故实测解释器可用性，坏了就重建（venv 已 gitignored，可从 requirements.txt 完全重建）。
echo "📦 检查Python虚拟环境..."
if [ -x venv/bin/python ] && venv/bin/python -c '' 2>/dev/null; then
    echo "ℹ️  虚拟环境已存在且可用（$(venv/bin/python --version 2>&1)）"
else
    if [ -d venv ]; then
        echo "⚠️  检测到损坏的 venv（解释器不可用/路径失效），重建中..."
        rm -rf venv
    fi
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功（$(venv/bin/python --version 2>&1)）"
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 升级 pip + 装依赖 — 一律走 `python -m pip`，不依赖脆弱的 pip console-script shebang
# （relocation/Python 升级后 console-script 会 bad interpreter；`-m` 形态永远 mv-safe）
echo "⬆️  升级pip..."
python -m pip install --upgrade pip

# 安装依赖
echo "📥 安装项目依赖..."
python -m pip install -r requirements.txt

# 安装开发/测试依赖（pytest；requirements-dev.txt 内含 -r requirements.txt）
echo "🧪 安装测试依赖..."
python -m pip install -r requirements-dev.txt

# 跑测试套件做安装自检（纯离线，不需要任何 API key / 凭证）
echo ""
echo "🧪 运行测试套件 (pytest)..."
if python -m pytest -q; then
    echo "✅ 测试全绿"
else
    echo "⚠️  测试未全绿（详见上方输出）"
fi

# 检查Google Cloud凭证（可选 — 语言列表 + 回退引擎）
# 查找顺序: GOOGLE_APPLICATION_CREDENTIALS env → gcloud ADC → 项目根 fallback 文件
echo ""
echo "🔑 检查Google Cloud凭证（可选）..."
CRED_FILE=""
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    CRED_FILE="$GOOGLE_APPLICATION_CREDENTIALS (env)"
elif [ -f "google-credentials.json" ]; then
    CRED_FILE="google-credentials.json"
elif [ -f "serviceKey.json" ]; then
    CRED_FILE="serviceKey.json (legacy)"
elif [ -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
    CRED_FILE="gcloud ADC"
fi

if [ -z "$CRED_FILE" ]; then
    echo "ℹ️  未找到 Google 凭证（可选 — LLM 引擎不需要）"
    echo "   如需 Google Translate 作为回退或获取完整语言列表，参见 README.md:"
    echo "     - 放 google-credentials.json 到项目根，或"
    echo "     - export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json，或"
    echo "     - gcloud auth application-default login"
else
    echo "✅ 找到凭证：$CRED_FILE，验证..."
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
echo "3. 在浏览器中访问: http://127.0.0.1:5050"
echo ""
echo "如果遇到问题，请查看README.md中的故障排除部分"
