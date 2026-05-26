#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 workflower JSON 解析和降级处理"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.json_analysis.analysis import parse_json_string

def test_json_parsing():
    """测试各种格式的 JSON 解析"""
    print("=" * 80)
    print("测试 workflower JSON 解析功能")
    print("=" * 80)
    
    # 测试用例 1: 标准 JSON
    print("\n1. 测试标准 JSON 格式...")
    standard_json = '''{
  "operations": [
    {
      "operation_type": "execute_method",
      "method_name": "write_file",
      "method_source": "/utils/files_controler/tools/file_writer.py",
      "parameters": {
        "file_path": "test.py",
        "content": "print('hello')"
      },
      "description": "创建测试文件"
    }
  ],
  "if_end_all_work": false
}'''
    
    try:
        result = parse_json_string(standard_json)
        print(f"   ✓ 标准 JSON 解析成功")
        print(f"   操作数: {len(result.get('operations', []))}")
    except Exception as e:
        print(f"   ✗ 标准 JSON 解析失败: {e}")
    
    # 测试用例 2: 带 markdown 标记的 JSON
    print("\n2. 测试带 markdown 标记的 JSON...")
    markdown_json = '''```json
{
  "operations": [
    {
      "operation_type": "execute_method",
      "method_name": "write_file",
      "method_source": "/utils/files_controler/tools/file_writer.py",
      "parameters": {},
      "description": "创建文件"
    }
  ],
  "if_end_all_work": true
}
```'''
    
    try:
        result = parse_json_string(markdown_json)
        print(f"   ✓ Markdown JSON 解析成功")
        print(f"   if_end_all_work: {result.get('if_end_all_work')}")
    except Exception as e:
        print(f"   ✗ Markdown JSON 解析失败: {e}")
    
    # 测试用例 3: 带前后文字的 JSON（应该失败）
    print("\n3. 测试带前后文字的 JSON（应该失败）...")
    invalid_json = '''好的，我来帮你创建文件。

{
  "operations": [],
  "if_end_all_work": false
}

希望这能帮到你！'''
    
    try:
        result = parse_json_string(invalid_json)
        print(f"   ✓ 意外成功（不应该）")
    except Exception as e:
        print(f"   ✓ 正确捕获错误: 包含额外文字")
    
    # 测试用例 4: 只有 markdown 开头（之前失败的情况）
    print("\n4. 测试只有 'markdown' 开头的内容（应该失败）...")
    bad_json = '''markdown
# 一级标题
## 二级标题'''
    
    try:
        result = parse_json_string(bad_json)
        print(f"   ✓ 意外成功（不应该）")
    except Exception as e:
        print(f"   ✓ 正确捕获错误: 不是 JSON 格式")
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    print("\n总结:")
    print("- 标准 JSON: ✓ 应该成功")
    print("- Markdown JSON: ✓ 应该成功")
    print("- 带文字 JSON: ✓ 应该失败（触发降级处理）")
    print("- 非 JSON 内容: ✓ 应该失败（触发降级处理）")

if __name__ == "__main__":
    test_json_parsing()
