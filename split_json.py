#!/usr/bin/env python3
"""
JSON文件分割工具
将大的JSON文件分割成多个小文件，避免API速率限制
"""

import json
import os
import sys
from math import ceil


def split_json_file(input_file, max_items_per_file=100):
    """
    将JSON文件分割成多个小文件

    Args:
        input_file: 输入的JSON文件路径
        max_items_per_file: 每个文件的最大项目数
    """

    # 读取原始文件
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("错误：只支持对象类型的JSON文件")
        return

    total_items = len(data)
    print(f"原始文件包含 {total_items} 个项目")

    if total_items <= max_items_per_file:
        print(f"文件大小合适（<= {max_items_per_file}项），无需分割")
        return

    # 计算需要分割成多少个文件
    num_files = ceil(total_items / max_items_per_file)
    print(f"将分割成 {num_files} 个文件，每个文件最多 {max_items_per_file} 项")

    # 获取文件名（不含扩展名）
    base_name = os.path.splitext(input_file)[0]

    # 分割数据
    items = list(data.items())
    for i in range(num_files):
        start_idx = i * max_items_per_file
        end_idx = min((i + 1) * max_items_per_file, total_items)

        # 创建子文件数据
        chunk_data = dict(items[start_idx:end_idx])

        # 生成文件名
        output_file = f"{base_name}_part{i+1}.json"

        # 写入文件
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunk_data, f, ensure_ascii=False, indent=2)

        print(f"创建文件: {output_file} ({len(chunk_data)} 项)")

    print(f"\n分割完成！请分别翻译这 {num_files} 个文件。")
    print("建议：每次只翻译1个文件到1-2种语言，避免API速率限制。")


def merge_translated_files(pattern, output_file):
    """
    合并翻译后的文件

    Args:
        pattern: 文件名模式，如 "zh_part*.json"
        output_file: 输出文件名
    """
    import glob

    files = sorted(glob.glob(pattern))
    if not files:
        print(f"未找到匹配的文件: {pattern}")
        return

    merged_data = {}

    for file in files:
        print(f"合并文件: {file}")
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged_data.update(data)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)

    print(f"合并完成: {output_file} ({len(merged_data)} 项)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  分割文件: python split_json.py <input_file> [max_items_per_file]")
        print("  合并文件: python split_json.py --merge <pattern> <output_file>")
        print("")
        print("示例:")
        print("  python split_json.py large_file.json 100")
        print("  python split_json.py --merge 'zh_part*.json' zh_complete.json")
        sys.exit(1)

    if sys.argv[1] == "--merge":
        if len(sys.argv) < 4:
            print("合并模式需要提供文件模式和输出文件名")
            sys.exit(1)
        merge_translated_files(sys.argv[2], sys.argv[3])
    else:
        input_file = sys.argv[1]
        max_items = int(sys.argv[2]) if len(sys.argv) > 2 else 100

        if not os.path.exists(input_file):
            print(f"文件不存在: {input_file}")
            sys.exit(1)

        split_json_file(input_file, max_items)
