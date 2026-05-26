"""
测试thinker_json模块的功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.json_analysis.thinker_json import parse_json_string

def test_parse_json_string():
    """测试JSON解析功能"""
    # 测试基本JSON对象
    json_str = '{"if_have_error_and_re-execute": false, "suggestion": "test"}'
    result = parse_json_string(json_str)
    print("Basic JSON test:", result)
    assert isinstance(result, dict)
    assert "if_have_error_and_re-execute" in result
    assert result["suggestion"] == "test"
    
    # 测试带markdown标记的JSON
    md_json_str = '```json\n{"if_have_error_and_re-execute": true, "error_position": "test", "suggestion": "fix this"}\n```'
    result2 = parse_json_string(md_json_str)
    print("Markdown JSON test:", result2)
    assert isinstance(result2, dict)
    assert result2["if_have_error_and_re-execute"] == True
    assert result2["error_position"] == "test"
    assert result2["suggestion"] == "fix this"
    
    # 测试checker可能返回的格式
    checker_json = '{"if_have_error_and_re-execute": false, "error_position": "", "suggestion": "对当前阶段工作的总结和下一步建议"}'
    result3 = parse_json_string(checker_json)
    print("Checker JSON test:", result3)
    assert result3["if_have_error_and_re-execute"] == False
    assert result3["suggestion"] == "对当前阶段工作的总结和下一步建议"
    
    print("所有测试通过！")

if __name__ == "__main__":
    test_parse_json_string()