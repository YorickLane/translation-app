#!/bin/bash

# 翻译应用一键安装脚本
echo "🚀 开始安装翻译应用..."

# 检查Python版本
echo "📋 检查Python版本..."
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python版本检查通过: $python_version"
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

# 检查serviceKey.json
echo "🔑 检查Google Cloud凭证..."
if [ ! -f "serviceKey.json" ]; then
    echo "⚠️  未找到serviceKey.json文件"
    echo "请按照README.md中的说明配置Google Cloud凭证"
else
    echo "✅ 找到serviceKey.json文件"
    
    # 测试凭证
    echo "🧪 测试Google Cloud凭证..."
    python test_credentials.py
fi

echo ""
echo "🎉 安装完成！"
echo ""
echo "📖 使用说明："
echo "1. 激活虚拟环境: source venv/bin/activate"
echo "2. 启动应用: python app.py"
echo "3. 在浏览器中访问: http://127.0.0.1:5000"
echo ""
echo "如果遇到问题，请查看README.md中的故障排除部分" 