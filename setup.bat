@echo off
chcp 65001 >nul
echo 🚀 开始安装翻译应用...

REM 检查Python版本
echo 📋 检查Python版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.8+（推荐 3.10+）
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

REM 检查Google Cloud凭证（可选 — 语言列表 + 回退引擎）
echo.
echo 🔑 检查Google Cloud凭证（可选）...
if not exist "serviceKey.json" (
    echo ℹ️  未找到 serviceKey.json（可选 — LLM 引擎不需要）
    echo    如需 Google Translate 作为回退或获取完整语言列表，请参见 README.md
) else (
    echo ✅ 找到 serviceKey.json，验证凭证...
    python -c "from google.cloud import translate_v2 as translate; c=translate.Client(); langs=c.get_languages(); print(f'✅ Google 凭证有效，拉到 {len(langs)} 种语言')"
)

REM 检查 OpenRouter API key
echo.
echo 🔑 检查 OpenRouter API Key...
if defined OPENROUTER_API_KEY (
    echo ✅ OPENROUTER_API_KEY 已设置
) else (
    echo ⚠️  OPENROUTER_API_KEY 未设置（LLM 引擎不可用）
    echo    推荐在环境变量设置 OPENROUTER_API_KEY=sk-or-v1-...
    echo    或在 PowerShell profile 中 source ~/.config/secrets.env（bash 格式）
)

echo.
echo 🎉 安装完成！
echo.
echo 📖 使用说明：
echo 1. 激活虚拟环境: venv\Scripts\activate.bat
echo 2. 启动应用: python app.py（或 start.bat）
echo 3. 在浏览器中访问: http://127.0.0.1:5050
echo.
echo 如果遇到问题，请查看README.md中的故障排除部分
pause
