@echo off
chcp 65001 >nul
echo 🚀 启动翻译应用...

REM 检查虚拟环境
if not exist "venv" (
    echo ❌ 未找到虚拟环境，请先运行 setup.bat 进行安装
    pause
    exit /b 1
)

REM 激活虚拟环境
echo 🔄 激活虚拟环境...
call venv\Scripts\activate.bat

REM 检查serviceKey.json
if not exist "serviceKey.json" (
    echo ⚠️  未找到serviceKey.json文件
    echo 请按照README.md中的说明配置Google Cloud凭证
    pause
    exit /b 1
)

REM 启动应用
echo 🌐 启动Flask应用...
echo 应用将在 http://127.0.0.1:5000 启动
echo 按 Ctrl+C 停止应用
echo.

python app.py
pause 