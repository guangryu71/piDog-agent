import subprocess
import sys
import os
import importlib.util
import json
from typing import Dict, List, Any, Union


def execute_operations(operations_dict: Dict[str, Any]) -> List[str]:
    """
    自动识别字典内operations属性数组并依次执行的方法
    
    Args:
        operations_dict: 包含operations数组的字典
        
    Returns:
        List[str]: 每个步骤执行控制台输出的结果数组
    """
    # 检查字典是否包含operations键
    if 'operations' not in operations_dict:
        return ["错误: 输入字典不包含'operations'键"]
    
    operations = operations_dict['operations']
    results = []
    
    # 遍历operations数组中的每个元素
    for operation in operations:
        # 检查operation是否包含必需的键
        if 'method_name' not in operation or 'method_source' not in operation:
            results.append("错误: 操作缺少'method_name'或'method_source'键")
            continue
        
        method_name = operation['method_name']
        method_source = operation['method_source']
        parameters = operation.get('parameters', {})
        
        # 处理参数中的转义字符
        processed_parameters = _process_parameters(parameters)
        
        # 如果是write_file操作且没有指定编码，则添加UTF-8编码
        if method_name == 'write_file' and 'encoding' not in processed_parameters:
            processed_parameters['encoding'] = 'utf-8'
        
        # 执行方法并获取结果
        result = _execute_single_operation(method_name, method_source, processed_parameters)
        results.append(result)
    
    return results


def _process_parameters(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理参数中的转义字符，特别是content字段中的换行符等
    
    Args:
        parameters: 原始参数字典
        
    Returns:
        Dict[str, Any]: 处理后的参数字典
    """
    processed_params = {}
    
    for key, value in parameters.items():
        if isinstance(value, str):
            # 如果是字符串类型的参数，检查是否包含转义字符
            # 特别处理content字段，因为其中可能包含\n等转义字符
            if key == 'content':
                # 将JSON中的转义序列解析为对应的实际字符
                try:
                    processed_value = value.encode().decode('unicode_escape')
                    processed_params[key] = processed_value
                except UnicodeDecodeError:
                    # 如果解码失败，使用原始值
                    processed_params[key] = value
            else:
                # 对于其他字符串参数，也可以进行转义处理
                try:
                    processed_params[key] = value.encode().decode('unicode_escape')
                except UnicodeDecodeError:
                    processed_params[key] = value
        else:
            # 非字符串参数直接复制
            processed_params[key] = value
    
    return processed_params


def _execute_single_operation(method_name: str, method_source: str, parameters: Dict[str, Any]) -> str:
    """
    执行单个操作的方法
    
    Args:
        method_name: 方法名
        method_source: 方法所在的相对文件路径（相对于项目根目录）
        parameters: 方法参数字典
        
    Returns:
        str: 执行结果或错误信息
    """
    try:
        # 构建绝对路径 - method_source是相对于项目根目录的路径
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(base_path, method_source.lstrip('/'))
        
        # 检查文件是否存在
        if not os.path.exists(full_path):
            return f"错误: 文件不存在 - {full_path}"
        
        # 动态导入模块
        spec = importlib.util.spec_from_file_location("module", full_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 检查方法是否存在
        if not hasattr(module, method_name):
            return f"错误: 方法不存在 - {method_name} 在 {full_path} 中"
        
        method = getattr(module, method_name)
        
        # 调用方法并捕获输出
        # 注意：parameters中的路径已经是绝对路径，不需要额外处理
        try:
            result = method(**parameters)
            if result is None:
                return ""
            return str(result)
        except Exception as e:
            return f"错误: 执行方法时发生异常 - {str(e)}"
            
    except ImportError as e:
        return f"错误: 导入模块失败 - {str(e)}"
    except Exception as e:
        return f"错误: 执行操作时发生未知错误 - {str(e)}"


def execute_operations_as_subprocess(operations_dict: Dict[str, Any]) -> List[str]:
    """
    使用子进程方式执行operations数组的方法（如果需要真正的命令行输出）
    
    Args:
        operations_dict: 包含operations数组的字典
        
    Returns:
        List[str]: 每个步骤执行控制台输出的结果数组
    """
    # 检查字典是否包含operations键
    if 'operations' not in operations_dict:
        return ["错误: 输入字典不包含'operations'键"]
    
    operations = operations_dict['operations']
    results = []
    
    # 创建临时脚本来执行每个操作
    for i, operation in enumerate(operations):
        if 'method_name' not in operation or 'method_source' not in operation:
            results.append("错误: 操作缺少'method_name'或'method_source'键")
            continue
        
        method_name = operation['method_name']
        method_source = operation['method_source']
        parameters = operation.get('parameters', {})
        
        # 处理参数中的转义字符
        processed_parameters = _process_parameters(parameters)
        
        # 如果是write_file操作且没有指定编码，则添加UTF-8编码
        if method_name == 'write_file' and 'encoding' not in processed_parameters:
            processed_parameters['encoding'] = 'utf-8'
        
        # 创建临时Python脚本来执行操作
        temp_script = _create_temp_script(method_name, method_source, processed_parameters)
        
        try:
            # 执行临时脚本并捕获输出
            result = subprocess.run(
                [sys.executable, "-c", temp_script],
                capture_output=True,
                text=True,
                timeout=30  # 设置超时时间为30秒
            )
            
            # 组合stdout和stderr
            output = result.stdout
            if result.stderr:
                output += "\n错误: " + result.stderr
            
            results.append(output if output else "")
        except subprocess.TimeoutExpired:
            results.append("错误: 操作超时")
        except Exception as e:
            results.append(f"错误: 执行子进程时发生异常 - {str(e)}")
    
    return results


def _create_temp_script(method_name: str, method_source: str, parameters: Dict[str, Any]) -> str:
    """
    创建用于执行单个操作的临时脚本
    """
    # 将参数转换为Python代码字符串，同时处理转义字符
    params_items = []
    for k, v in parameters.items():
        if isinstance(v, str):
            # 对字符串参数进行转义处理
            try:
                escaped_v = v.encode().decode('unicode_escape')
                params_items.append(f'{k}={repr(escaped_v)}')
            except UnicodeDecodeError:
                params_items.append(f'{k}={repr(v)}')
        else:
            params_items.append(f'{k}={repr(v)}')
    
    params_str = ", ".join(params_items)
    
    # 构建绝对路径 - method_source是相对于项目根目录的路径
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    full_path = os.path.join(base_path, method_source.lstrip('/')).replace("\\", "/")
    
    # 如果是write_file操作且没有指定编码，添加UTF-8编码
    if method_name == 'write_file':
        if 'encoding' not in parameters:
            params_str += ", encoding='utf-8'"
    
    script = f'''
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(r"{full_path}"))))

# 动态导入模块
import importlib.util
spec = importlib.util.spec_from_file_location("module", r"{full_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# 获取方法并执行
method = getattr(module, "{method_name}")
try:
    result = method({params_str})
    if result is not None:
        print(str(result))
except Exception as e:
    print(f"错误: {{e}}")
'''
    return script


# 示例用法
if __name__ == "__main__":
    # 示例操作字典
    sample_operations = {
        "operations": [
            {
                "operation_type": "execute_method",
                "method_name": "write_file",
                "method_source": "/utils/files_controler/tools/file_writer.py",
                "parameters": {
                    "file_path": "D:/developer/myProject/buffer/smart_agent_new/workplace/student_management_system/src/__init__.py",
                    "content": "",
                    "mode": "overwrite"
                },
                "description": "创建项目主目录和初始化文件"
            },
            {
                "operation_type": "execute_method",
                "method_name": "write_file",
                "method_source": "/utils/files_controler/tools/file_writer.py",
                "parameters": {
                    "file_path": "D:/developer/myProject/buffer/smart_agent_new/workplace/student_management_system/src/student.py",
                    "content": "class Student:\\n    def __init__(self, id, name, age):\\n        self.id = id\\n        self.name = name\\n        self.age = age\\n\\n    def __str__(self):\\n        return f'Student(id={{self.id}}, name={{self.name}}, age={{self.age}})'",
                    "mode": "overwrite"
                },
                "description": "创建学生类文件"
            },
            {
                "operation_type": "execute_method",
                "method_name": "write_file",
                "method_source": "/utils/files_controler/tools/file_writer.py",
                "parameters": {
                    "file_path": "D:/developer/myProject/buffer/smart_agent_new/workplace/student_management_system/src/main.py",
                    "content": "from student import Student\\n\\nif __name__ == '__main__':\\n    student = Student(1, 'John Doe', 20)\\n    print(student)",
                    "mode": "overwrite"
                },
                "description": "创建主程序文件并测试学生类"
            }
        ],
        "stop_reason": "等待运行结果以决定下一步操作"
    }
    
    # 执行操作并打印结果
    results = execute_operations(sample_operations)
    for i, result in enumerate(results):
        print(f"操作 {i+1} 结果: {result}")