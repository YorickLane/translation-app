# 创建新的Google Cloud项目指南

## 🚀 快速创建新项目

### 1. 创建新项目
1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 点击顶部项目选择器旁的下拉箭头
3. 点击"新建项目"
4. 输入项目名称（如：`translation-app-2025`）
5. 点击"创建"

### 2. 启用Translation API
1. 在新项目中，访问"API和服务" → "库"
2. 搜索"Cloud Translation API"
3. 点击并启用API

### 3. 创建新的服务账号
1. 访问"IAM和管理" → "服务账号"
2. 点击"创建服务账号"
3. 输入名称（如：`translation-service`）
4. 授予角色：`Cloud Translation API User`
5. 创建密钥（JSON格式）
6. 下载并保存为 `serviceKey.json`

### 4. 启用计费（如果需要）
- 新项目可能需要关联计费账号
- Google提供300美元免费额度给新用户

## ⚡ 预期效果
- 新项目没有历史限制
- 全新的API配额
- 可能解决速率限制问题 