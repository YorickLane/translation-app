@echo off
chcp 65001 >nul
echo 🚀 开始安装翻译应用...

REM 检查Python版本
echo 📋 检查Python版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 创建虚拟环境
echo 📦 创建Python虚拟环境...
if not exist "venv" (
    python -m venv venv
    echo ✅ 虚拟环境创建成功
) else (
    echo ℹ️  虚拟环境已存在
)

REM 激活虚拟环境
echo 🔄 激活虚拟环境...
call venv\Scripts\activate.bat

REM 升级pip
echo ⬆️  升级pip...
python -m pip install --upgrade pip

REM 安装依赖
echo 📥 安装项目依赖...
pip install -r requirements.txt

REM 检查serviceKey.json
echo 🔑 检查Google Cloud凭证...
if not exist "serviceKey.json" (
    echo ⚠️  未找到serviceKey.json文件
    echo 请按照README.md中的说明配置Google Cloud凭证
) else (
    echo ✅ 找到serviceKey.json文件
    
    REM 测试凭证
    echo 🧪 测试Google Cloud凭证...
    python test_credentials.py
)

echo.
echo 🎉 安装完成！
echo.
echo 📖 使用说明：
echo 1. 激活虚拟环境: venv\Scripts\activate.bat
echo 2. 启动应用: python app.py
echo 3. 在浏览器中访问: http://127.0.0.1:5000
echo.
echo 如果遇到问题，请查看README.md中的故障排除部分
pause 