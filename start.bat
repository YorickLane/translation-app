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

REM 凭证检查（OpenRouter 或 Google 至少一个，和 start.sh 行为一致）
set "has_or=0"
set "has_google=0"
if defined OPENROUTER_API_KEY set "has_or=1"
if defined GOOGLE_APPLICATION_CREDENTIALS if exist "%GOOGLE_APPLICATION_CREDENTIALS%" set "has_google=1"
if not "%has_google%"=="1" if exist "google-credentials.json" set "has_google=1"
if not "%has_google%"=="1" if exist "serviceKey.json" set "has_google=1"
if not "%has_google%"=="1" if exist "%APPDATA%\gcloud\application_default_credentials.json" set "has_google=1"

if "%has_or%"=="0" if "%has_google%"=="0" (
    echo ❌ 未检测到任何翻译引擎凭证，至少需要一个:
    echo    • OpenRouter: set OPENROUTER_API_KEY=sk-or-v1-...
    echo    • Google Translate:
    echo       - 项目根放 google-credentials.json
    echo       - 或 set GOOGLE_APPLICATION_CREDENTIALS=path\to\key.json
    echo       - 或 gcloud auth application-default login
    echo    详见 README.md
    pause
    exit /b 1
)

if "%has_or%"=="1" echo ✅ OpenRouter LLM 引擎可用（主引擎）
if "%has_google%"=="1" (
    echo ✅ Google Translate 可用（完整语言列表 + 回退引擎）
) else (
    echo ⚠️  无 Google 凭证 — 语言列表降级到 20 种 fallback，Google 引擎不可用
)

REM 启动应用
echo 🌐 启动Flask应用...
echo 应用将在 http://127.0.0.1:5050 启动
echo 按 Ctrl+C 停止应用
echo.

python app.py
pause 