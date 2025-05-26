# Google Translation API 使用建议

## 🚨 当前问题：用户速率限制

如果您遇到 "403 User Rate Limit Exceeded" 错误，这是Google的保护机制。

### 立即解决方案：

1. **等待15-30分钟**
   - Google的用户速率限制通常会在15-30分钟后自动重置
   - 这是最简单有效的解决方案

2. **使用小文件测试**
   ```bash
   # 上传 test-small.json 文件（只有5个项目）
   # 这样可以验证API是否恢复正常
   ```

3. **分批处理大文件**
   ```bash
   # 您的文件已经分割成7个小文件：
   # zh-cn_part1.json (100项)
   # zh-cn_part2.json (100项)
   # ...
   # zh-cn_part7.json (60项)
   
   # 建议每次只翻译1个文件，间隔5-10分钟
   ```

### 长期解决方案：

1. **检查配额设置**
   - 访问 Google Cloud Console > IAM & Admin > Quotas
   - 搜索 "Translation API"
   - 确认每分钟请求数限制

2. **申请配额增加**
   - 如果经常遇到限制，可以申请增加配额
   - 在配额页面点击"INCREASE REQUESTS"

3. **优化翻译策略**
   - 减少并发请求
   - 增加请求间隔
   - 分批处理大文件

## 📊 当前配额状态

根据您的Google Cloud Console截图：
- ✅ Number of v2 default requests per minute: 300,000 (0% 使用)
- ✅ AutoML model characters per minute: 10,000 (0% 使用)

配额充足，问题是临时的用户速率限制。

## 🔄 建议的操作流程

1. **等待30分钟**
2. **测试小文件** (`test-small.json`)
3. **如果成功，逐个翻译分割文件**
4. **每个文件间隔5-10分钟**

## 📞 需要帮助？

如果问题持续存在，请：
1. 检查Google Cloud项目计费状态
2. 确认服务账号权限
3. 联系Google Cloud支持

## 🚨 常见问题解决

### 速率限制错误 (Rate Limit Exceeded)

如果遇到 `403 User Rate Limit Exceeded` 错误，请尝试以下解决方案：

#### 1. 减少同时翻译的语言数量
- **建议**：一次选择 1-3 种语言进行翻译
- **原因**：避免短时间内发送过多API请求

#### 2. 等待后重试
- **等待时间**：5-10 分钟
- **原因**：Google API有时间窗口限制

#### 3. 检查Google Cloud配额设置

访问 [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Quotas：

- **Translation API requests per minute**: 默认 300/分钟
- **Translation API requests per day**: 默认 无限制
- **Characters per minute**: 默认 10,000,000/分钟

#### 4. 升级API配额（如需要）

1. 在Google Cloud Console中找到Translation API配额
2. 点击配额项目
3. 点击"EDIT QUOTAS"
4. 申请增加配额限制

## 💡 最佳实践

### 文件大小建议
- **小文件** (< 1KB): 可同时翻译多种语言
- **中等文件** (1-10KB): 建议 2-3 种语言
- **大文件** (> 10KB): 建议逐个语言翻译

### 翻译策略
1. **优先翻译**：先翻译最重要的语言
2. **分批处理**：将大量语言分成多批处理
3. **错峰使用**：避开API使用高峰期

### 成本优化
- **预估成本**：Translation API按字符收费
- **批量翻译**：一次处理多个相关文件
- **缓存结果**：避免重复翻译相同内容

## 🔧 故障排除

### 认证错误
```
翻译失败：认证错误，请检查Google Cloud凭证
```
**解决方案**：
1. 确认 `serviceKey.json` 文件存在
2. 检查服务账号权限
3. 验证API是否已启用

### 配额用完
```
翻译失败：API配额已用完
```
**解决方案**：
1. 等待配额重置（通常每天重置）
2. 申请增加配额
3. 考虑使用多个项目分散负载

### 网络错误
```
翻译失败：服务暂时不可用
```
**解决方案**：
1. 检查网络连接
2. 稍后重试
3. 确认Google服务状态

## 📊 监控使用情况

### Google Cloud Console监控
1. 访问 APIs & Services → Dashboard
2. 查看Translation API使用统计
3. 设置配额警报

### 应用内监控
- 查看控制台日志了解翻译进度
- 注意错误消息和重试次数
- 记录翻译成功率

## 🎯 推荐配置

### 免费层用户
- 每次翻译：1-2种语言
- 文件大小：< 5KB
- 使用频率：每小时不超过3次

### 付费用户
- 每次翻译：3-5种语言
- 文件大小：< 50KB
- 可根据配额调整使用频率

## 📞 获取帮助

如果问题持续存在：
1. 查看 [Google Cloud Translation API 文档](https://cloud.google.com/translate/docs)
2. 检查 [Google Cloud 状态页面](https://status.cloud.google.com/)
3. 联系 Google Cloud 支持团队 