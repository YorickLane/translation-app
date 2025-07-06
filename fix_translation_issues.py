#!/usr/bin/env python3
"""
修复现有翻译文件中的问题
主要修复：
1. 繁体中文中的英文内容
2. 其他语言中的英文短语
3. 不当的大写问题
"""

import json
import os
import argparse
import shutil
from datetime import datetime
from translate_claude import translate_with_claude, CLAUDE_MODEL


def load_json_file(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(filepath, data):
    """保存JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def backup_file(filepath):
    """备份原文件"""
    backup_path = filepath + f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    shutil.copy2(filepath, backup_path)
    print(f"已备份到: {backup_path}")
    return backup_path


def find_english_entries(data, language_code):
    """查找需要重新翻译的英文条目"""
    if language_code == 'en':
        return {}
    
    english_entries = {}
    
    # 常见的英文UI词汇
    english_keywords = [
        'Please', 'Enter', 'Select', 'Password', 'Login',
        'Settings', 'Edit', 'Delete', 'Clear', 'Copy',
        'Download', 'Upload', 'Cancel', 'Confirm', 'Save',
        'verification', 'progress', 'merchant', 'payment',
        'Withdrawal', 'Payment'
    ]
    
    for key, value in data.items():
        if isinstance(value, str):
            # 检查是否包含英文关键词
            value_lower = value.lower()
            for keyword in english_keywords:
                if keyword.lower() in value_lower:
                    english_entries[key] = value
                    break
    
    return english_entries


def fix_traditional_chinese(filepath, source_file_path):
    """修复繁体中文文件"""
    print(f"\n修复繁体中文文件: {filepath}")
    
    # 加载文件
    data = load_json_file(filepath)
    source_data = load_json_file(source_file_path)
    
    # 查找英文条目
    english_entries = find_english_entries(data, 'zh-TW')
    
    if not english_entries:
        print("✅ 没有发现需要修复的英文条目")
        return
    
    print(f"发现 {len(english_entries)} 个需要修复的英文条目")
    
    # 备份原文件
    backup_file(filepath)
    
    # 批量翻译
    fixed_count = 0
    batch_size = 10
    entries_list = list(english_entries.items())
    
    for i in range(0, len(entries_list), batch_size):
        batch = dict(entries_list[i:i+batch_size])
        print(f"\n翻译批次 {i//batch_size + 1}/{(len(entries_list) + batch_size - 1)//batch_size}")
        
        # 获取对应的源文本
        source_batch = {k: source_data.get(k, v) for k, v in batch.items()}
        
        try:
            # 使用改进后的翻译函数
            translated = translate_with_claude(source_batch, 'zh-TW', CLAUDE_MODEL)
            
            # 更新数据
            for key, new_value in translated.items():
                old_value = data[key]
                data[key] = new_value
                fixed_count += 1
                print(f"  ✓ {key}: \"{old_value}\" → \"{new_value}\"")
                
        except Exception as e:
            print(f"  ✗ 翻译失败: {e}")
    
    # 保存修复后的文件
    save_json_file(filepath, data)
    print(f"\n✅ 修复完成！共修复 {fixed_count} 个条目")


def fix_capitalization(filepath, language_code):
    """修复大写问题"""
    print(f"\n修复大写问题: {filepath}")
    
    # 罗曼语系应该使用小写
    if language_code not in ['es', 'fr', 'it', 'pt']:
        print("该语言不需要修复大写问题")
        return
    
    data = load_json_file(filepath)
    backup_file(filepath)
    
    fixed_count = 0
    
    for key, value in data.items():
        if isinstance(value, str) and len(value) > 0:
            words = value.split()
            
            # 单个词的UI元素
            if len(words) == 1 and words[0][0].isupper() and words[0][1:].islower():
                # 转换为小写
                new_value = value.lower()
                data[key] = new_value
                fixed_count += 1
                print(f"  ✓ {key}: \"{value}\" → \"{new_value}\"")
    
    if fixed_count > 0:
        save_json_file(filepath, data)
        print(f"\n✅ 修复完成！共修复 {fixed_count} 个大写问题")
    else:
        print("✅ 没有发现需要修复的大写问题")


def fix_missing_translations(filepath, language_code, source_file_path):
    """修复缺失的翻译（英文短语）"""
    print(f"\n修复缺失的翻译: {filepath}")
    
    data = load_json_file(filepath)
    source_data = load_json_file(source_file_path)
    
    # 查找英文条目
    english_entries = find_english_entries(data, language_code)
    
    if not english_entries:
        print("✅ 没有发现需要修复的英文条目")
        return
    
    print(f"发现 {len(english_entries)} 个需要修复的英文条目")
    
    # 只显示前5个
    for i, (key, value) in enumerate(list(english_entries.items())[:5]):
        print(f"  - {key}: \"{value}\"")
    if len(english_entries) > 5:
        print(f"  ... 还有 {len(english_entries) - 5} 个")
    
    # 询问是否继续
    response = input("\n是否修复这些条目？(y/n): ")
    if response.lower() != 'y':
        print("已取消")
        return
    
    backup_file(filepath)
    
    # 批量翻译
    fixed_count = 0
    batch_size = 5  # 减小批次大小以提高成功率
    entries_list = list(english_entries.items())
    
    for i in range(0, len(entries_list), batch_size):
        batch = dict(entries_list[i:i+batch_size])
        print(f"\n翻译批次 {i//batch_size + 1}/{(len(entries_list) + batch_size - 1)//batch_size}")
        
        # 获取对应的源文本
        source_batch = {k: source_data.get(k, v) for k, v in batch.items()}
        
        try:
            # 使用改进后的翻译函数
            translated = translate_with_claude(source_batch, language_code, CLAUDE_MODEL)
            
            # 更新数据
            for key, new_value in translated.items():
                old_value = data[key]
                # 验证新值不是英文
                if new_value != old_value and not all(ord(c) < 128 for c in new_value.replace(' ', '')):
                    data[key] = new_value
                    fixed_count += 1
                    print(f"  ✓ {key}: \"{old_value}\" → \"{new_value}\"")
                else:
                    print(f"  ✗ {key}: 翻译结果仍为英文，跳过")
                    
        except Exception as e:
            print(f"  ✗ 翻译失败: {e}")
    
    # 保存修复后的文件
    save_json_file(filepath, data)
    print(f"\n✅ 修复完成！共修复 {fixed_count} 个条目")


def main():
    parser = argparse.ArgumentParser(description='修复翻译文件中的问题')
    parser.add_argument('path', help='要修复的文件或目录路径')
    parser.add_argument('--source', default='zh-CN.json', help='源语言文件（默认：zh-CN.json）')
    parser.add_argument('--fix-caps', action='store_true', help='修复大写问题')
    parser.add_argument('--fix-english', action='store_true', help='修复英文混入问题')
    parser.add_argument('--all', action='store_true', help='修复所有问题')
    
    args = parser.parse_args()
    
    if args.all:
        args.fix_caps = True
        args.fix_english = True
    
    if not args.fix_caps and not args.fix_english:
        print("请指定要修复的问题类型：--fix-caps, --fix-english 或 --all")
        return
    
    if os.path.isdir(args.path):
        # 处理目录
        source_file = os.path.join(args.path, args.source)
        if not os.path.exists(source_file):
            print(f"错误：找不到源文件 {source_file}")
            return
        
        for filename in sorted(os.listdir(args.path)):
            if filename.endswith('.json') and filename != args.source:
                filepath = os.path.join(args.path, filename)
                language_code = filename.replace('.json', '')
                
                print(f"\n{'='*60}")
                print(f"处理文件: {filename}")
                print(f"{'='*60}")
                
                if language_code == 'zh-TW' and args.fix_english:
                    fix_traditional_chinese(filepath, source_file)
                elif args.fix_english:
                    fix_missing_translations(filepath, language_code, source_file)
                
                if args.fix_caps:
                    fix_capitalization(filepath, language_code)
    
    elif os.path.isfile(args.path):
        # 处理单个文件
        filename = os.path.basename(args.path)
        language_code = filename.replace('.json', '')
        
        # 查找源文件
        dir_path = os.path.dirname(args.path)
        source_file = os.path.join(dir_path, args.source)
        
        if not os.path.exists(source_file):
            print(f"错误：找不到源文件 {source_file}")
            return
        
        if language_code == 'zh-TW' and args.fix_english:
            fix_traditional_chinese(args.path, source_file)
        elif args.fix_english:
            fix_missing_translations(args.path, language_code, source_file)
        
        if args.fix_caps:
            fix_capitalization(args.path, language_code)
    
    else:
        print(f"错误: 路径不存在: {args.path}")


if __name__ == "__main__":
    main()