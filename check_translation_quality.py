#!/usr/bin/env python3
"""
翻译质量检查工具 V2
更智能的语言检测，减少误报
"""

import json
import os
import re
from collections import defaultdict
import argparse


def load_json_file(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def contains_english_keywords(text, lang_code):
    """检查文本是否包含英文关键词（更智能）"""
    # 常见的英文UI词汇
    keywords = [
        'Please', 'Enter', 'Select', 'Password', 'Login',
        'Settings', 'Edit', 'Delete', 'Clear', 'Copy',
        'Download', 'Upload', 'Cancel', 'Confirm', 'Save',
        'verification', 'progress', 'merchant', 'payment',
        'Withdrawal', 'Payment', 'Error', 'Success'
    ]
    
    # 语言特定的豁免词汇（这些词在该语言中是正确的）
    language_exemptions = {
        'es': ['confirmar', 'cancelar', 'editar', 'error'],
        'pt': ['confirmar', 'cancelar', 'editar', 'upload', 'login', 'download'],
        'fr': ['confirmer', 'entrer', 'enter', 'error'],
        'it': ['password', 'login', 'cancella', 'download', 'upload', 'error'],
        'de': ['download', 'upload', 'center', 'service', 'error']
    }
    
    # 全局豁免词汇（品牌名、技术术语等）
    global_exemptions = ['APP', 'iOS', 'Android', 'ID', 'VIP', 'API', 'URL', 'T+1', 
                        'USDT', 'H5', 'PC', 'OK', 'PDF', 'HTML', 'JSON']
    
    text_lower = text.lower()
    exemptions = language_exemptions.get(lang_code, [])
    
    for keyword in keywords:
        if keyword.lower() in text_lower:
            # 检查是否在豁免列表中
            is_exempted = False
            
            # 检查语言特定豁免
            for exemption in exemptions:
                if exemption in text_lower:
                    is_exempted = True
                    break
            
            # 检查全局豁免
            for exemption in global_exemptions:
                if exemption.lower() in text_lower:
                    is_exempted = True
                    break
            
            if not is_exempted:
                return True, keyword
    
    return False, None


def check_english_in_non_english_file(data, language_code):
    """检查非英文文件中的英文内容"""
    if language_code == 'en':
        return []
    
    issues = []
    
    for key, value in data.items():
        if isinstance(value, str):
            has_english, keyword = contains_english_keywords(value, language_code)
            if has_english:
                issues.append({
                    'key': key,
                    'value': value,
                    'issue': f'包含英文词汇: {keyword}'
                })
    
    return issues


def check_capitalization_issues(data, language_code):
    """检查大写问题"""
    issues = []
    
    # 罗曼语系语言应该使用小写
    lowercase_languages = ['es', 'fr', 'it', 'pt']
    
    if language_code in lowercase_languages:
        # 检查是否有不当的大写
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 0:
                # 跳过缩写词和品牌名
                if value.isupper() or len(value) <= 3:
                    continue
                
                # 跳过包含特殊词汇的条目
                skip_words = ['VIP', 'APP', 'USDT', 'ID', 'PC', 'H5', 'API']
                should_skip = any(word in value for word in skip_words)
                if should_skip:
                    continue
                
                # 检查首字母大写的单词（不在句首）
                words = value.split()
                if len(words) == 1 and words[0][0].isupper() and words[0][1:].islower():
                    # 单个词且首字母大写
                    issues.append({
                        'key': key,
                        'value': value,
                        'issue': f'{language_code}语言UI元素应该使用小写'
                    })
    
    return issues


def check_translation_consistency(data, reference_keys):
    """检查翻译完整性"""
    missing_keys = []
    
    for key in reference_keys:
        if key not in data:
            missing_keys.append(key)
    
    return missing_keys


def analyze_language_file(filepath, reference_data=None):
    """分析单个语言文件"""
    filename = os.path.basename(filepath)
    language_code = filename.replace('.json', '')
    
    print(f"\n{'='*60}")
    print(f"分析文件: {filename}")
    print(f"{'='*60}")
    
    try:
        data = load_json_file(filepath)
        
        # 1. 检查英文混入
        english_issues = check_english_in_non_english_file(data, language_code)
        if english_issues:
            print(f"\n❌ 发现 {len(english_issues)} 个英文混入问题:")
            for issue in english_issues[:10]:  # 只显示前10个
                print(f"  - {issue['key']}: \"{issue['value']}\" ({issue['issue']})")
            if len(english_issues) > 10:
                print(f"  ... 还有 {len(english_issues) - 10} 个问题")
        
        # 2. 检查大写问题
        cap_issues = check_capitalization_issues(data, language_code)
        if cap_issues:
            print(f"\n⚠️  发现 {len(cap_issues)} 个大写问题:")
            for issue in cap_issues[:5]:
                print(f"  - {issue['key']}: \"{issue['value']}\" ({issue['issue']})")
            if len(cap_issues) > 5:
                print(f"  ... 还有 {len(cap_issues) - 5} 个问题")
        
        # 3. 检查缺失的键
        if reference_data:
            missing_keys = check_translation_consistency(data, reference_data.keys())
            if missing_keys:
                print(f"\n⚠️  缺失 {len(missing_keys)} 个翻译键:")
                for key in missing_keys[:5]:
                    print(f"  - {key}")
                if len(missing_keys) > 5:
                    print(f"  ... 还有 {len(missing_keys) - 5} 个缺失")
        
        # 4. 统计信息
        print(f"\n📊 统计信息:")
        print(f"  - 总条目数: {len(data)}")
        print(f"  - 英文混入率: {len(english_issues)/len(data)*100:.1f}%")
        
        if not english_issues and not cap_issues and not (reference_data and missing_keys):
            print(f"\n✅ 文件质量良好!")
        
        return {
            'language': language_code,
            'total_entries': len(data),
            'english_issues': len(english_issues),
            'cap_issues': len(cap_issues),
            'missing_keys': len(missing_keys) if reference_data else 0
        }
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return None


def check_directory(directory_path):
    """检查目录中的所有语言文件"""
    print(f"检查目录: {directory_path}")
    
    # 首先加载参考文件（中文）
    reference_file = os.path.join(directory_path, 'zh-CN.json')
    reference_data = None
    
    if os.path.exists(reference_file):
        reference_data = load_json_file(reference_file)
        print(f"使用 zh-CN.json 作为参考 ({len(reference_data)} 个键)")
    
    # 分析所有JSON文件
    results = []
    for filename in sorted(os.listdir(directory_path)):
        if filename.endswith('.json') and filename != 'zh-CN.json':
            filepath = os.path.join(directory_path, filename)
            result = analyze_language_file(filepath, reference_data)
            if result:
                results.append(result)
    
    # 汇总报告
    print(f"\n{'='*60}")
    print("汇总报告")
    print(f"{'='*60}")
    
    total_issues = sum(r['english_issues'] + r['cap_issues'] + r['missing_keys'] for r in results)
    
    if total_issues == 0:
        print("✅ 所有文件质量良好!")
    else:
        print(f"⚠️  发现总计 {total_issues} 个问题")
        print("\n问题分布:")
        
        # 按问题数量排序
        sorted_results = sorted(results, 
                              key=lambda x: x['english_issues'] + x['cap_issues'] + x['missing_keys'], 
                              reverse=True)
        
        for i, result in enumerate(sorted_results[:10]):
            total = result['english_issues'] + result['cap_issues'] + result['missing_keys']
            if total > 0:
                parts = []
                if result['english_issues'] > 0:
                    parts.append(f"英文混入: {result['english_issues']}")
                if result['cap_issues'] > 0:
                    parts.append(f"大写问题: {result['cap_issues']}")
                if result['missing_keys'] > 0:
                    parts.append(f"缺失翻译: {result['missing_keys']}")
                
                print(f"{i+1}. {result['language']}.json - {total} 个问题 ({', '.join(parts)})")
        
        # 总结
        print(f"\n📊 质量总结:")
        excellent = [r for r in results if r['english_issues'] == 0 and r['cap_issues'] == 0 and r['missing_keys'] == 0]
        good = [r for r in results if r['english_issues'] < 5 and r['cap_issues'] < 5 and r['missing_keys'] < 10]
        
        if excellent:
            print(f"  - 优秀: {', '.join([r['language'] + '.json' for r in excellent])}")
        if good and len(good) != len(excellent):
            print(f"  - 良好: {', '.join([r['language'] + '.json' for r in good if r not in excellent])}")


def main():
    parser = argparse.ArgumentParser(description='检查翻译文件质量 V2')
    parser.add_argument('path', help='要检查的文件或目录路径')
    parser.add_argument('--strict', action='store_true', help='使用严格模式')
    
    args = parser.parse_args()
    
    if os.path.isdir(args.path):
        check_directory(args.path)
    elif os.path.isfile(args.path):
        analyze_language_file(args.path)
    else:
        print(f"错误: 路径不存在: {args.path}")


if __name__ == "__main__":
    main()