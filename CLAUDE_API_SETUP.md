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
python check_claude_model.py  # 检查可用模型
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

### Claude API 定价（2025年）
- **Claude 3.5 Haiku**（推荐）:
  - 输入：$0.80/百万token
  - 输出：$4.00/百万token
- **Claude 3.5 Sonnet**:
  - 输入：$3.00/百万token
  - 输出：$15.00/百万token
- **Claude Sonnet 4**:
  - 输入：$3.00/百万token
  - 输出：$15.00/百万token
- **Claude Opus 4**:
  - 输入：$15.00/百万token
  - 输出：$75.00/百万token

### 费用预估功能
应用内置了实时费用预估功能，在选择 Claude API 后可以：
1. 上传文件并选择目标语言
2. 点击"预估费用"按钮
3. 选择计算方式：
   - **快速估算**（默认）：基于文件大小和经验系数，准确度约78-94%
   - **API精确计算**：使用Claude API计算实际tokens，更准确但会调用API
4. 查看详细费用明细：
   - 文件大小和键值对数量
   - 输入/输出tokens数量
   - 批处理信息（批次数、每批大小）
   - 各部分费用（美元/人民币）
   - 准确度提示

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