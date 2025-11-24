#!/usr/bin/env python3
"""
翻译系统高级配置
用于优化 Claude API 翻译质量和性能
"""

# 批处理优化参数
BATCH_CONFIG = {
    "size": 15,  # 默认批次大小（适合大多数短文本）
    "request_delay": 0.3,  # 减少请求间隔（Claude API 速率限制很高）
    "max_retries": 3,  # 最大重试次数
    "retry_delays": [1.0, 2.0, 4.0],  # 渐进式重试延迟

    # 智能批处理：根据内容长度动态调整
    "dynamic_batching": True,
    "max_chars_per_batch": 3000,  # 每批最大字符数（避免超过 token 限制）
    "min_batch_size": 2,  # 最小批次大小（长文本保护）
    "max_batch_size": 25,  # 最大批次大小
}

# 语言代码映射（解决API兼容性问题）
LANGUAGE_CODE_MAPPING = {
    'zh-TW': 'zh-Hant',  # 繁体中文的标准代码
    'zh-CN': 'zh-Hans',  # 简体中文的标准代码
    'zh': 'zh-Hans',     # 简体中文简写
}

# 语言特定的 temperature 设置
TEMPERATURE_BY_LANGUAGE = {
    'zh-TW': 0.05,     # 极低，确保繁体中文准确性
    'zh-Hant': 0.05,   # 同上
    'technical': 0.1,   # 技术文档
    'marketing': 0.3,   # 营销文案
    'default': 0.1     # 默认值
}

# 输出验证强度
VALIDATION_STRENGTH = {
    'zh-TW': 'strict',    # 严格验证，避免英文混入
    'zh-Hant': 'strict',  
    'es': 'moderate',     # 中度验证
    'fr': 'moderate',
    'pt': 'moderate',
    'it': 'moderate',
    'de': 'light',        # 轻度验证
    'default': 'light'
}

# 模型推荐（根据任务类型）
MODEL_RECOMMENDATIONS = {
    'large_batch': 'claude-3-5-haiku-20241022',      # 大批量，快速
    'high_quality': 'claude-sonnet-4-5-20250929',    # 高质量（最新推荐）
    'complex': 'claude-opus-4-20250514',             # 复杂文本
    'cost_effective': 'claude-3-haiku-20240307',     # 经济实惠
    'default': 'claude-sonnet-4-5-20250929'          # 默认推荐（最新最强）
}

# 容易出错的术语映射（确保一致性）
TERM_GLOSSARY = {
    'en': {
        '确定': 'Confirm',
        '取消': 'Cancel',
        '保存': 'Save',
        '编辑': 'Edit',
        '删除': 'Delete',
        '设置': 'Settings',
        '搜索': 'Search',
        '刷新': 'Refresh',
    },
    'es': {
        '确定': 'confirmar',
        '取消': 'cancelar',
        '保存': 'guardar',
        '编辑': 'editar',
        '删除': 'eliminar',
        '设置': 'configurar',
        '搜索': 'buscar',
        '刷新': 'actualizar',
    },
    'fr': {
        '确定': 'confirmer',
        '取消': 'annuler',
        '保存': 'enregistrer',
        '编辑': 'modifier',
        '删除': 'supprimer',
        '设置': 'paramètres',
        '搜索': 'rechercher',
        '刷新': 'actualiser',
    },
    'de': {
        '确定': 'bestätigen',
        '取消': 'abbrechen',
        '保存': 'speichern',
        '编辑': 'bearbeiten',
        '删除': 'löschen',
        '设置': 'Einstellungen',
        '搜索': 'suchen',
        '刷新': 'aktualisieren',
    },
    'zh-TW': {
        '确定': '確定',
        '取消': '取消',
        '保存': '儲存',
        '编辑': '編輯',
        '删除': '刪除',
        '设置': '設定',
        '搜索': '搜尋',
        '刷新': '重新整理',
    }
}

# 质量检查规则
QUALITY_CHECK_RULES = {
    # 检查英文混入的关键词
    'english_keywords': [
        'Please', 'Enter', 'Select', 'Password', 'Login',
        'Settings', 'Edit', 'Delete', 'Clear', 'Copy',
        'Download', 'Upload', 'Cancel', 'Confirm', 'Save',
        'verification', 'progress', 'merchant', 'payment',
        'Withdrawal', 'Payment', 'Error', 'Success'
    ],
    
    # 每种语言的最大英文容忍率
    'max_english_ratio': {
        'zh-TW': 0.01,  # 1% - 繁体中文几乎不应有英文
        'es': 0.05,     # 5%
        'fr': 0.05,
        'de': 0.05,
        'it': 0.05,
        'pt': 0.05,
        'ru': 0.05,
        'default': 0.1  # 10%
    }
}

# 后处理规则
POST_PROCESSING_RULES = {
    # 罗曼语系小写处理
    'lowercase_languages': ['es', 'fr', 'it', 'pt'],
    
    # 需要保持大写的特殊词汇
    'preserve_uppercase': [
        'API', 'URL', 'ID', 'VIP', 'UI', 'OK',
        'iOS', 'Android', 'PDF', 'HTML', 'JSON'
    ]
}

# 缓存配置
CACHE_CONFIG = {
    'enabled': True,
    'ttl': 86400,  # 24小时
    'max_size': 10000  # 最多缓存10000个条目
}

# 日志配置
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'translation.log',
    'max_bytes': 10485760,  # 10MB
    'backup_count': 5
}