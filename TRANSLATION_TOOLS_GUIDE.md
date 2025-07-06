# 翻译工具使用指南

## 概述

本文档介绍了改进后的翻译系统和新增的质量检查、修复工具。

## 主要改进

### 1. 翻译脚本改进 (translate_claude.py)

#### 已修复的问题：
- ✅ 移除了强制首字母大写规则
- ✅ 为不同语言添加了特定的大写规则
- ✅ 加强了对繁体中文的支持
- ✅ 添加了英文检测和重试机制
- ✅ 改进了错误处理，失败批次会自动重试

#### 语言特定规则：
- **英语**：UI元素使用首字母大写（Confirm, Cancel）
- **德语**：只有名词大写，动词小写（speichern, Einstellungen）
- **罗曼语系**（西/法/意/葡）：UI元素小写（confirmar, annuler）
- **繁体中文**：确保翻译为繁体而非英文

### 2. 质量检查工具 (check_translation_quality.py)

检查语言包中的常见问题：

```bash
# 检查单个文件
python check_translation_quality.py /path/to/language.json

# 检查整个目录
python check_translation_quality.py /path/to/locales/
```

#### 检查项目：
- 英文混入检测（非英文文件中的英文内容）
- 大写问题检测（罗曼语系的不当大写）
- 翻译完整性（缺失的键）
- 生成详细报告和修复建议

### 3. 自动修复工具 (fix_translation_issues.py)

批量修复现有翻译问题：

```bash
# 修复所有问题
python fix_translation_issues.py /path/to/locales/ --all

# 只修复英文混入
python fix_translation_issues.py /path/to/locales/ --fix-english

# 只修复大写问题
python fix_translation_issues.py /path/to/locales/ --fix-caps

# 修复单个文件
python fix_translation_issues.py /path/to/zh-TW.json --fix-english
```

#### 功能特点：
- 自动备份原文件
- 批量处理，支持重试
- 交互式确认
- 详细的修复日志

## 使用流程

### 1. 检查现有问题

```bash
# 先检查 x-project 的语言包
python check_translation_quality.py /Users/fengxiu/Documents/WordSpace/WT/x-project/apps/seller-h5/src/locales/
```

### 2. 修复问题

```bash
# 修复繁体中文
python fix_translation_issues.py /Users/fengxiu/Documents/WordSpace/WT/x-project/apps/seller-h5/src/locales/zh-TW.json --fix-english

# 修复所有文件
python fix_translation_issues.py /Users/fengxiu/Documents/WordSpace/WT/x-project/apps/seller-h5/src/locales/ --all
```

### 3. 验证修复结果

```bash
# 再次运行质量检查
python check_translation_quality.py /Users/fengxiu/Documents/WordSpace/WT/x-project/apps/seller-h5/src/locales/
```

## 注意事项

1. **API 限制**：修复工具会调用 Claude API，请注意 API 使用限制
2. **备份**：工具会自动备份，但建议先手动备份重要文件
3. **人工审核**：自动修复后建议人工审核关键翻译
4. **批次大小**：如果遇到 API 错误，可以在代码中调整 batch_size

## 常见问题

### Q: 为什么繁体中文会出现大量英文？
A: 可能是因为：
- API 调用时语言代码不匹配（zh-TW vs zh-Hant）
- 提示词不够明确，模型误解了要求
- 批处理时某些批次完全失败

### Q: 如何处理特殊的品牌名或专有名词？
A: 可以在翻译前创建词典，或在翻译后手动调整。

### Q: 修复工具运行很慢？
A: 为了避免 API 限制，工具会在批次间添加延迟。可以根据需要调整 REQUEST_DELAY。

## 后续优化建议

1. 建立术语词典，确保关键词翻译一致
2. 实现增量翻译，只处理新增或修改的条目
3. 添加翻译记忆功能，避免重复翻译相同内容
4. 集成到 CI/CD 流程，自动检查翻译质量