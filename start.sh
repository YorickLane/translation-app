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

# 检查serviceKey.json
if [ ! -f "serviceKey.json" ]; then
    echo "⚠️  未找到serviceKey.json文件"
    echo "请按照README.md中的说明配置Google Cloud凭证"
    exit 1
fi

# 启动应用
echo "🌐 启动Flask应用..."
echo "应用将在 http://127.0.0.1:5000 启动"
echo "按 Ctrl+C 停止应用"
echo ""

python app.py 