# 使用Claude API进行翻译

## 🚀 快速设置

### 1. 获取Claude API密钥
1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 注册或登录账号
3. 在API Keys页面创建新的API密钥
4. 复制密钥

### 2. 配置环境变量

#### macOS/Linux:
```bash
export CLAUDE_API_KEY="sk-ant-api..."
export TRANSLATION_ENGINE="claude"
```

#### Windows:
```cmd
set CLAUDE_API_KEY=sk-ant-api...
set TRANSLATION_ENGINE=claude
```

### 3. 测试Claude API
```bash
python translate_claude.py --test
```

### 4. 启动应用
```bash
./start.sh  # macOS/Linux
# 或
start.bat   # Windows
```

## 💰 成本对比

### Google Translation API
- 前500,000字符/月：免费
- 之后：$20/百万字符

### Claude API (Haiku模型)
- 输入：$0.25/百万token
- 输出：$1.25/百万token
- 大约：$1-2/百万字符

## 🎯 优势

### Claude API的优点
- ✅ 没有速率限制问题
- ✅ 更好的上下文理解
- ✅ 保持格式和占位符
- ✅ 支持复杂的翻译需求

### Google API的优点
- ✅ 支持更多语言（193种）
- ✅ 更快的响应速度
- ✅ 专门针对翻译优化

## 🔧 切换翻译引擎

### 使用Google（默认）
```bash
export TRANSLATION_ENGINE="google"
```

### 使用Claude
```bash
export TRANSLATION_ENGINE="claude"
```

## 📝 注意事项

1. Claude API需要付费账号
2. 建议先用小文件测试
3. Claude支持的语言较少（约20种主流语言）
4. 翻译质量通常很好，特别是对于技术文档 