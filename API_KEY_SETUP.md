# API Key 安全配置指南

本指南介绍如何在 macOS 上安全地管理 API 密钥。

## 🔐 推荐方案（按安全级别排序）

### 方案 1：macOS Keychain（最安全）✅

使用 macOS 原生的 Keychain 存储敏感信息：

```bash
# 使用提供的脚本
./setup_keychain.sh

# 选择 1 存储 API Key
# 选择 4 设置环境变量
```

**优点：**
- 密钥加密存储
- 系统级安全保护
- 不会意外提交到 Git

### 方案 2：环境变量（推荐日常使用）

在 `~/.zshrc` 中设置：

```bash
# 编辑配置文件
nano ~/.zshrc

# 添加以下内容
export CLAUDE_API_KEY="your-api-key-here"

# 重新加载
source ~/.zshrc
```

**优点：**
- 设置简单
- 全局可用
- 不在项目代码中

### 方案 3：.env 文件（开发环境）

1. 复制示例文件：
```bash
cp .env.example .env
```

2. 编辑 .env 文件：
```bash
CLAUDE_API_KEY=your-api-key-here
```

**优点：**
- 项目级配置
- 便于开发测试
- 已在 .gitignore 中

## 🛡️ 安全最佳实践

### 1. **永远不要做的事：**
- ❌ 不要将 API Key 硬编码在代码中
- ❌ 不要提交 .env 文件到 Git
- ❌ 不要在公开的地方分享 API Key

### 2. **应该做的事：**
- ✅ 使用环境变量或 Keychain
- ✅ 定期轮换 API Key
- ✅ 为不同环境使用不同的 Key
- ✅ 检查 .gitignore 包含敏感文件

### 3. **Git 安全检查：**

```bash
# 检查是否有敏感信息
git grep -i "sk-ant-api"
git grep -i "api.*key.*="

# 如果发现敏感信息，从历史中删除
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/file" \
  --prune-empty --tag-name-filter cat -- --all
```

## 🚀 快速开始

### 对于您的环境（macOS + iTerm2 + zsh）：

1. **首次设置：**
```bash
# 方法 1：使用 Keychain（最安全）
./setup_keychain.sh

# 方法 2：使用环境变量
echo 'export CLAUDE_API_KEY="your-key"' >> ~/.zshrc
source ~/.zshrc
```

2. **验证设置：**
```bash
# 检查环境变量
echo $CLAUDE_API_KEY

# 测试 API
python3 check_claude_model.py
```

3. **在代码中使用：**
```python
# config.py 会自动处理：
# 1. 先检查 Keychain（macOS）
# 2. 然后检查 .env 文件
# 3. 最后检查环境变量
```

## 🔄 密钥轮换

定期更新 API Key：

1. 在 Anthropic Console 生成新 Key
2. 更新存储位置（Keychain/环境变量/.env）
3. 测试新 Key
4. 删除旧 Key

## 📱 iTerm2 特定配置

在 iTerm2 中自动加载环境变量：

1. 打开 iTerm2 → Preferences → Profiles
2. 选择你的 Profile → General → Command
3. 设置为：`/bin/zsh -l`（登录 shell）

这样每次打开新终端都会加载 ~/.zshrc 中的环境变量。

## 🆘 故障排除

如果 API Key 不工作：

```bash
# 1. 检查是否已设置
env | grep CLAUDE

# 2. 重新加载配置
source ~/.zshrc

# 3. 检查 Keychain（如果使用）
security find-generic-password -a "CLAUDE_API_KEY" -s "translation-app"

# 4. 测试 API
python3 -c "from config import CLAUDE_API_KEY; print('Key exists:', bool(CLAUDE_API_KEY))"
```

---

记住：安全存储 API Key 是保护您的账户和避免意外费用的第一步！