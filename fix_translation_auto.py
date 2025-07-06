#!/usr/bin/env python3
"""
自动修复翻译问题（非交互版本）
"""

import json
import os
import sys
import time
import logging
from translate_claude import translate_with_claude
from config import CLAUDE_MODEL, REQUEST_DELAY

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_json_file(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(filepath, data):
    """保存JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def contains_english_keywords(text):
    """检查是否包含英文关键词"""
    keywords = [
        'Please', 'Enter', 'Select', 'Password', 'Login',
        'Settings', 'Edit', 'Delete', 'Clear', 'Copy',
        'Download', 'Upload', 'Cancel', 'Confirm', 'Save',
        'verification', 'progress', 'merchant', 'payment',
        'Withdrawal', 'Payment', 'Error', 'Success'
    ]
    
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True
    return False

def fix_english_contamination(filepath, language_code, source_file):
    """修复英文混入问题"""
    logger.info(f"修复英文混入: {filepath}")
    
    data = load_json_file(filepath)
    source_data = load_json_file(source_file)
    
    # 找出需要重新翻译的条目
    items_to_fix = {}
    for key, value in data.items():
        if isinstance(value, str) and contains_english_keywords(value):
            if key in source_data:
                items_to_fix[key] = source_data[key]
    
    if not items_to_fix:
        logger.info("没有发现英文混入问题")
        return
    
    logger.info(f"发现 {len(items_to_fix)} 个英文混入问题，开始修复...")
    
    # 分批翻译
    fixed_count = 0
    batch_size = 5
    items = list(items_to_fix.items())
    
    for i in range(0, len(items), batch_size):
        batch = dict(items[i:i+batch_size])
        try:
            logger.info(f"翻译批次 {i//batch_size + 1}/{(len(items) + batch_size - 1)//batch_size}")
            translated = translate_with_claude(batch, language_code, CLAUDE_MODEL)
            
            # 更新数据
            for key, value in translated.items():
                if key in data:
                    old_value = data[key]
                    data[key] = value
                    fixed_count += 1
                    logger.info(f"修复: {key}: '{old_value}' → '{value}'")
            
            # 保存进度
            save_json_file(filepath, data)
            
            # 请求间隔
            if i + batch_size < len(items):
                time.sleep(REQUEST_DELAY)
                
        except Exception as e:
            logger.error(f"批次翻译失败: {e}")
            # 继续处理下一批
    
    logger.info(f"修复完成，共修复 {fixed_count} 个条目")

def fix_missing_translations(filepath, language_code, source_file):
    """修复缺失的翻译"""
    logger.info(f"检查缺失的翻译: {filepath}")
    
    data = load_json_file(filepath)
    source_data = load_json_file(source_file)
    
    # 找出缺失的键
    missing_keys = set(source_data.keys()) - set(data.keys())
    
    if not missing_keys:
        logger.info("没有缺失的翻译")
        return
    
    logger.info(f"发现 {len(missing_keys)} 个缺失的翻译，开始修复...")
    
    # 准备要翻译的内容
    items_to_translate = {key: source_data[key] for key in missing_keys}
    
    # 分批翻译
    added_count = 0
    batch_size = 5
    items = list(items_to_translate.items())
    
    for i in range(0, len(items), batch_size):
        batch = dict(items[i:i+batch_size])
        try:
            logger.info(f"翻译批次 {i//batch_size + 1}/{(len(items) + batch_size - 1)//batch_size}")
            translated = translate_with_claude(batch, language_code, CLAUDE_MODEL)
            
            # 添加到数据
            for key, value in translated.items():
                data[key] = value
                added_count += 1
                logger.info(f"添加: {key}: '{value}'")
            
            # 保存进度
            save_json_file(filepath, data)
            
            # 请求间隔
            if i + batch_size < len(items):
                time.sleep(REQUEST_DELAY)
                
        except Exception as e:
            logger.error(f"批次翻译失败: {e}")
            # 继续处理下一批
    
    logger.info(f"添加完成，共添加 {added_count} 个翻译")

def main():
    if len(sys.argv) < 2:
        print("使用方法: python fix_translation_auto.py <目录路径>")
        sys.exit(1)
    
    target_path = sys.argv[1]
    
    if not os.path.exists(target_path):
        print(f"错误: 路径不存在 - {target_path}")
        sys.exit(1)
    
    # 默认使用zh-CN.json作为源文件
    source_filename = "zh-CN.json"
    
    # 需要修复的语言
    languages_to_fix = {
        'es.json': 'es',
        'fr.json': 'fr',
        'it.json': 'it',
        'pt.json': 'pt',
        'de.json': 'de',
        'zh-TW.json': 'zh-TW'
    }
    
    if os.path.isdir(target_path):
        source_file = os.path.join(target_path, source_filename)
        if not os.path.exists(source_file):
            print(f"错误: 源文件不存在 - {source_file}")
            sys.exit(1)
        
        # 处理每个需要修复的语言文件
        for filename, lang_code in languages_to_fix.items():
            filepath = os.path.join(target_path, filename)
            if os.path.exists(filepath):
                print(f"\n{'='*60}")
                print(f"处理文件: {filename}")
                print(f"{'='*60}\n")
                
                # 先修复英文混入
                fix_english_contamination(filepath, lang_code, source_file)
                
                # 再修复缺失的翻译
                fix_missing_translations(filepath, lang_code, source_file)
                
                print(f"\n✅ {filename} 处理完成")
                
                # 文件间延迟
                time.sleep(2)
    
    print("\n🎉 所有文件处理完成！")

if __name__ == "__main__":
    main()