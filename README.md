# 翻译工具 (Translation Utility)

## 概述
这是一个基于Flask的翻译应用，专门用于自动翻译JavaScript和JSON文件中的语言字符串。它使用Google Cloud Translation API进行翻译，支持带引号和不带引号的JavaScript对象键名。

## 功能特性
- 翻译JavaScript和JSON文件，支持特殊字符键名
- 通过Socket通信实时显示翻译进度
- 输出单个ZIP文件包含所有翻译文档
- 缓存支持的语言列表以减少API调用

## 系统要求
- Python 3.8+ (推荐 Python 3.10+)
- Google Cloud Translation API 凭证
- 稳定的网络连接

## 🚀 快速开始

### 方法一：一键安装（推荐）

**macOS/Linux:**
```bash
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

### 方法二：手动安装

#### 1. 环境准备
确保您的系统已安装Python 3.8+：
```bash
python --version
```

#### 2. 创建虚拟环境（推荐）
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

#### 3. 安装依赖包
```bash
pip install -r requirements.txt
```

#### 4. 配置Google Cloud凭证
1. 在Google Cloud Console创建项目
2. 启用Translation API
3. 创建服务账号并下载JSON凭证文件
4. 将凭证文件重命名为 `serviceKey.json` 并放在项目根目录

#### 5. 测试配置
```bash
python test_credentials.py
```
如果看到"✅ 凭证验证成功！"说明配置正确。

#### 6. 启动应用
```bash
# 方法一：使用启动脚本（推荐）
./start.sh          # macOS/Linux
start.bat           # Windows

# 方法二：手动启动
source venv/bin/activate  # 激活虚拟环境
python app.py            # 启动应用
```
应用将在 `http://127.0.0.1:5000/` 启动

## 📖 使用方法

### 1. 访问应用
在浏览器中打开 `http://127.0.0.1:5000/`

### 2. 上传文件
- 点击"选择文件"按钮
- 选择要翻译的 `.js` 或 `.json` 文件
- 文件应包含需要翻译的语言字符串

### 3. 选择目标语言
- 从支持的语言列表中选择一个或多个目标语言
- 应用支持Google Translate API支持的所有语言（193种）

### 4. 开始翻译
- 点击"翻译"按钮
- 应用会显示实时翻译进度
- 翻译完成后会生成包含所有翻译文件的ZIP压缩包

### 5. 下载结果
- 翻译完成后，点击下载链接获取ZIP文件
- ZIP文件包含所有目标语言的翻译版本

## 📁 项目结构
```
translation-app/
├── app.py                 # Flask主应用文件
├── translate.py           # 翻译逻辑实现
├── config.py             # 配置文件
├── test_credentials.py   # 凭证测试脚本
├── requirements.txt      # Python依赖包列表
├── serviceKey.json       # Google Cloud凭证文件（需要自行创建）
├── setup.sh              # 一键安装脚本（macOS/Linux）
├── setup.bat             # 一键安装脚本（Windows）
├── start.sh              # 应用启动脚本（macOS/Linux）
├── start.bat             # 应用启动脚本（Windows）
├── templates/            # HTML模板文件
│   ├── upload.html
│   └── success.html
├── uploads/              # 上传文件临时存储
├── output/               # 翻译结果输出目录
└── venv/                 # Python虚拟环境（自动创建）
```

## ⚠️ 注意事项

### 安全提醒
- **保护密钥文件**：不要将 `serviceKey.json` 提交到Git仓库
- **虚拟环境**：建议使用虚拟环境避免依赖冲突
- **API配额**：注意Google Translation API的使用配额和计费

### 常见问题
1. **模块未找到错误**：确保已激活虚拟环境并安装所有依赖
2. **认证错误**：检查 `serviceKey.json` 文件是否存在且有效
3. **API错误**：确认Google Cloud项目已启用Translation API

### 故障排除
如果遇到问题，请按以下步骤检查：
1. 确认Python版本 >= 3.8
2. 确认虚拟环境已激活
3. 确认所有依赖包已安装
4. 确认 `serviceKey.json` 文件存在
5. 确认Google Cloud项目配置正确

## 🔧 开发相关

### 贡献指南
欢迎提交Pull Request和Issue来改进这个项目。

### 许可证
[MIT License](LICENSE.md)

### 致谢
- Google Cloud Translation API
- Flask 和 Flask-SocketIO 贡献者
- 所有项目贡献者和用户


