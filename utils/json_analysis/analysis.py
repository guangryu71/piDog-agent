import json
import re
from typing import Any, Dict, Union

def parse_json_string(input_str: str) -> Dict:
    """
    从包含markdown格式标记的字符串中解析JSON数据，只返回字典类型
    
    Args:
        input_str: 包含JSON数据的字符串，可能带有```json和```标记
        
    Returns:
        解析后的字典数据
        
    Raises:
        ValueError: 当字符串中不包含有效JSON、JSON格式错误或解析结果不是字典时抛出异常
    """
    # 去除首尾空白字符
    input_str = input_str.strip()
    
    # 首先尝试匹配 ```json ... ``` 或 ``` ... ``` 之间的内容
    json_pattern = r'```(?:json|JSON)?\s*\n?(.*?)\n?\s*```'
    match = re.search(json_pattern, input_str, re.DOTALL)
    
    if match:
        # 提取```之间的内容
        json_content = match.group(1).strip()
    else:
        # 如果没有找到markdown标记，尝试直接查找JSON对象
        # 找到第一个{的位置
        start_pos = input_str.find('{')
        if start_pos == -1:
            raise ValueError(f"JSON内容不是有效的对象格式（应以{{开头）\n")
        
        # 找到对应的结束位置
        brace_count = 0
        end_pos = len(input_str)
        
        for i, char in enumerate(input_str[start_pos:], start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            
            # 当计数回到0时，表示找到了完整JSON对象的结尾
            if brace_count == 0:
                end_pos = i + 1
                break
        
        json_content = input_str[start_pos:end_pos].strip()
    
    if not json_content:
        raise ValueError("无法提取有效的JSON内容")
    
    try:
        parsed_data = json.loads(json_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON格式错误: {e}\n尝试解析的内容: {json_content[:200]}...")
    
    # 确保解析结果是字典类型
    if not isinstance(parsed_data, dict):
        raise ValueError(f"解析结果不是字典类型，而是 {type(parsed_data).__name__}: {parsed_data}")
    
    return parsed_data

if __name__ == "__main__":
    pass