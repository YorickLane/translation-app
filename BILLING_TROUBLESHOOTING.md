# Google Cloud 计费账号问题排查

## 🚨 常见错误："User Rate Limit Exceeded"

如果您遇到这个错误，通常是计费账号的问题，而不是真正的速率限制。

## 🔍 检查步骤

### 1. 检查计费账号状态
1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 点击左上角的导航菜单 ☰
3. 选择 "结算" (Billing)
4. 检查您的计费账号状态

### 2. 常见问题和解决方案

#### ❌ 问题：计费账号已暂停
**症状**：显示"账号已暂停"或"需要验证"
**解决方案**：
- 更新付款方式
- 验证身份信息
- 联系Google支持

#### ❌ 问题：未关联计费账号
**症状**：项目没有关联任何计费账号
**解决方案**：
1. 在项目设置中点击"关联计费账号"
2. 选择现有账号或创建新账号
3. 确认关联

#### ❌ 问题：免费试用已过期
**症状**：$300免费额度已用完或过期
**解决方案**：
- 升级到付费账号
- 或创建新项目使用新的免费试用

### 3. 验证API是否启用
1. 访问 APIs & Services → Library
2. 搜索 "Cloud Translation API"
3. 确保状态显示为"已启用"

### 4. 检查配额使用情况
1. 访问 IAM & Admin → Quotas
2. 搜索 "Translation API"
3. 查看使用率和限制

## ✅ 修复后的验证

修复计费问题后，使用以下命令验证：

```bash
# 测试API连接
python test_credentials.py

# 或使用小文件测试
python check_api_status.py --once
```

## 💡 预防措施

1. **设置预算警报**
   - 在Billing中设置预算
   - 配置邮件提醒

2. **监控使用情况**
   - 定期检查API使用量
   - 关注异常消费

3. **备用方案**
   - 考虑使用Claude API作为备份
   - 准备多个Google Cloud项目

## 📞 需要帮助？

如果问题持续存在：
1. 检查 [Google Cloud Status](https://status.cloud.google.com/)
2. 访问 [Google Cloud Support](https://cloud.google.com/support)
3. 查看账单历史记录找出问题原因 