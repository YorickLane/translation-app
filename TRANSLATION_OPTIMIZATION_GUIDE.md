# 翻译系统优化指南

## 概述

本文档说明了针对 Claude 模型翻译问题的优化措施和参数调整。

## 已完成的优化

### 1. 清理测试文件
已删除以下不再需要的测试文件：
- `check_api_status.py`
- `check_claude_model.py`
- `test_credentials.py`
- `test_translation_improvements.py`

保留的重要工具：
- `check_translation_quality.py` - 质量检查工具
- `fix_translation_issues.py` - 问题修复工具

### 2. 参数优化

#### A. 批处理参数调整
```python
# 原配置
BATCH_SIZE = 10
REQUEST_DELAY = 0.5

# 新配置
BATCH_SIZE = 5        # 减小批次，提高成功率
REQUEST_DELAY = 1.0   # 增加延迟，避免速率限制
MAX_RETRIES = 3       # 添加重试机制
```

#### B. Temperature 优化
为不同语言设置了特定的 temperature：
- 繁体中文 (zh-TW): 0.05 - 极低，确保准确性
- 技术文档: 0.1
- 营销文案: 0.3
- 默认值: 0.1

#### C. 语言代码映射
解决 API 兼容性问题：
```python
'zh-TW' → 'zh-Hant'  # 繁体中文标准代码
'zh-CN' → 'zh-Hans'  # 简体中文标准代码
```

### 3. 新增高级配置文件

#### `translation_config.py`
包含：
- 批处理优化参数
- 语言特定配置
- 质量检查规则
- 术语词典
- 缓存配置

#### `translation_postprocess.py`
提供：
- 翻译后验证
- 大写规则修正
- 术语一致性检查
- 英文混入检测

### 4. 增强的错误处理

- 渐进式重试延迟 (1秒、2秒、4秒)
- 英文混入自动检测和重试
- 批次失败的详细日志记录

## 使用方法

### 1. 基本使用
系统会自动加载优化配置，无需修改现有代码。

### 2. 自定义配置
编辑 `translation_config.py` 文件：
```python
# 调整批次大小
BATCH_CONFIG = {
    "size": 3,  # 更小的批次
    "request_delay": 2.0,  # 更长的延迟
}

# 添加新语言的温度设置
TEMPERATURE_BY_LANGUAGE = {
    'ja': 0.05,  # 日语
    'ko': 0.05,  # 韩语
}
```

### 3. 质量检查
翻译完成后运行：
```bash
python check_translation_quality.py /path/to/translations/
```

### 4. 问题修复
发现问题后运行：
```bash
python fix_translation_issues.py /path/to/translations/ --all
```

## 重要提示

### 对于繁体中文
- 使用极低温度 (0.05) 避免创造性输出
- 严格验证避免英文混入
- 使用标准语言代码 zh-Hant

### 对于罗曼语系
- 自动修正大写问题
- 保持 UI 元素小写（除非句首）
- 术语一致性自动检查

### 性能优化
- 小批次处理（5个条目）
- 智能重试机制
- 缓存常见翻译

## 监控和维护

1. **查看日志**
   ```bash
   tail -f translation.log
   ```

2. **统计成功率**
   日志中会记录每批次的成功/失败情况

3. **定期质量检查**
   建议每次大批量翻译后运行质量检查

## 未来改进建议

1. **实现翻译记忆库**
   - 存储已翻译的句子
   - 避免重复 API 调用

2. **增加更多语言支持**
   - 添加日语、韩语等亚洲语言的特殊规则
   - 扩展术语词典

3. **集成到 CI/CD**
   - 自动化质量检查
   - 翻译差异报告

4. **成本优化**
   - 根据文本复杂度选择模型
   - 实现智能批次分组