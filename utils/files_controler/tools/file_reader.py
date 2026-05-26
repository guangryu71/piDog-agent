"""
文件读取工具 - 文件定位、完整读取、指定行读取
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import ast
import re
import ast
# 配置加载（skill_config_loader 模块不存在，使用空配置）
def get_skill_config(skill_name: str):
    return {}


def locate_file(
    filename: str,
    search_path: Optional[str] = None,
    recursive: bool = True
) -> Dict[str, Any]:
    """
    定位文件地址
    
    Args:
        filename: 文件名或通配符模式 *.py/config.json
        search_path: 搜索路径，默认当前目录
        recursive: 是否递归搜索子目录
        
    Returns:
        dict: {
            "status": "success" | "error",
            "files": ["匹配的文件路径列表"],
            "count": "找到的文件数量",
            "search_path": "搜索路径",
            "error": "错误信息"
        }
    """
    try:
        search_dir = Path(search_path) if search_path else Path.cwd()
        
        if not search_dir.exists():
            return {
                "status": "error",
                "error": f"搜索路径不存在: {search_dir}"
            }
        
        # 执行搜索
        if recursive:
            files = list(search_dir.rglob(filename))
        else:
            files = list(search_dir.glob(filename))
        
        return {
            "status": "success",
            "files": [str(f.absolute()) for f in files],
            "count": len(files),
            "search_path": str(search_dir.absolute()),
            "recursive": recursive,
            "message": f"找到{len(files)}个文件"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"文件定位失败: {str(e)}"
        }


def read_file_full(
    file_path: str,
    encoding: str = None
) -> Dict[str, Any]:
    """
    读取文件的完整内容
    
    Args:
        file_path: 文件路径
        encoding: 文件编码，默认从配置读取
        
    Returns:
        dict: {
            "status": "success" | "error",
            "content": "文件完整内容",
            "lines": "总行数",
            "size": "文件大小（字节）",
            "encoding": "使用的编码",
            "error": "错误信息"
        }
    """
    # 从配置读取默认编码
    if encoding is None:
        try:
            config = get_skill_config('files_controler')
            encoding = config.get('default_encoding', 'utf-8')
        except Exception:
            encoding = 'utf-8'
    
    # 处理相对路径，确保相对于工作空间路径
    path = Path(file_path)
    
    # 如果是相对路径，现在我们假定大模型已生成完整路径，不再自动拼接
    path = Path(file_path)
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"文件不存在: {file_path}, 尝试的完整路径: {path.absolute()}"
        }
    
    try:
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
        
        lines = content.count('\n') + 1
        size = path.stat().st_size
        
        return {
            "status": "success",
            "content": content,
            "lines": lines,
            "size": size,
            "encoding": encoding,
            "file_path": str(path.absolute()),
            "message": f"已读取{lines}行内容"
        }
        
    except UnicodeDecodeError:
        return {
            "status": "error",
            "error": f"编码错误，尝试使用其他编码（如gbk、latin-1）"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"读取失败: {str(e)}"
        }


def read_file_lines(
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    encoding: str = None
) -> Dict[str, Any]:
    """
    读取文件的指定行内容
    
    Args:
        file_path: 文件路径
        start_line: 起始行号（从1开始），None表示从头开始
        end_line: 结束行号，None表示到末尾
        encoding: 文件编码，默认从配置读取
        
    Returns:
        dict: {
            "status": "success" | "error",
            "lines": ["指定行的内容列表"],
            "start_line": "起始行号",
            "end_line": "结束行号",
            "total_lines_read": "实际读取的行数",
            "error": "错误信息"
        }
    """
    # 从配置读取默认编码
    if encoding is None:
        try:
            config = get_skill_config('files_controler')
            encoding = config.get('default_encoding', 'utf-8')
        except Exception:
            encoding = 'utf-8'
    
    path = Path(file_path)
    
    # 如果是相对路径，现在我们假定大模型已生成完整路径，不再自动拼接
    path = Path(file_path)
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"文件不存在: {file_path}, 尝试的完整路径: {path.absolute()}"
        }
    
    try:
        with open(path, 'r', encoding=encoding) as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        # 处理行号范围
        if start_line is None:
            start_line = 1
        if end_line is None:
            end_line = total_lines
        
        # 验证行号
        if start_line < 1 or start_line > total_lines:
            return {
                "status": "error",
                "error": f"起始行号超出范围: {start_line} (文件共{total_lines}行)"
            }
        
        if end_line < start_line or end_line > total_lines:
            return {
                "status": "error",
                "error": f"结束行号超出范围: {end_line} (文件共{total_lines}行，起始行{start_line})"
            }
        
        # 提取指定行（转换为0-based索引）
        selected_lines = all_lines[(start_line - 1):end_line]
        
        return {
            "status": "success",
            "lines": [line.rstrip('\n\r') for line in selected_lines],
            "start_line": start_line,
            "end_line": end_line,
            "total_lines_read": len(selected_lines),
            "total_lines_file": total_lines,
            "file_path": str(path.absolute()),
            "encoding": encoding,
            "message": f"已读取{len(selected_lines)}行内容 ({start_line}-{end_line})"
        }
        
    except UnicodeDecodeError:
        return {
            "status": "error",
            "error": f"编码错误，尝试使用其他编码（如gbk、latin-1）"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"读取失败: {str(e)}"
        }


def list_directory(dir_path: str = ".", max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
    """
    列出目录内容，支持递归获取指定深度的项目结构
    
    Args:
        dir_path: 目录路径，默认当前目录
        max_depth: 最大递归深度，默认 3
        current_depth: 当前递归深度（内部使用）
        
    Returns:
        dict: {
            "status": "success" | "error",
            "items": [目录项列表],
            "count": "项目总数",
            "files_count": "文件数量",
            "dirs_count": "目录数量",
            "directory": "目录路径",
            "max_depth": "最大递归深度",
            "structure": "树形结构字符串（可选）",
            "error": "错误信息"
        }
    """
    path = Path(dir_path)
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"目录不存在: {dir_path}"
        }
    
    if not path.is_dir():
        return {
            "status": "error",
            "error": f"路径不是目录: {dir_path}"
        }
    
    try:
        items = []
        files_count = 0
        dirs_count = 0
        
        for item in sorted(path.iterdir()):
            item_info = {
                "name": item.name,
                "path": str(item.absolute()),
                "is_file": item.is_file(),
                "is_dir": item.is_dir(),
                "suffix": item.suffix if item.is_file() else "",
                "depth": current_depth
            }
            
            # 如果是子目录且未达到最大深度，递归获取其内容
            if item.is_dir() and current_depth < max_depth - 1:
                sub_result = list_directory(
                    str(item), 
                    max_depth=max_depth, 
                    current_depth=current_depth + 1
                )
                if sub_result["status"] == "success":
                    item_info["children"] = sub_result["items"]
                    item_info["children_count"] = sub_result["count"]
            
            items.append(item_info)
            
            if item.is_file():
                files_count += 1
            else:
                dirs_count += 1
                # 累加子目录中的文件数
                if "children" in item_info:
                    for child in item_info.get("children", []):
                        if child.get("is_file"):
                            files_count += 1
                        elif child.get("is_dir"):
                            dirs_count += 1
        
        # 生成树形结构字符串（仅在第一层调用时生成）
        structure = None
        if current_depth == 0:
            structure = _generate_tree_structure(items, max_depth, prefix="", is_last=True)
        
        return {
            "status": "success",
            "items": items,
            "count": len(items),
            "files_count": files_count,
            "dirs_count": dirs_count,
            "directory": str(path.absolute()),
            "max_depth": max_depth,
            "structure": structure,
            "message": f"目录内容已列出（{files_count}个文件，{dirs_count}个目录，深度={max_depth}）"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"列出目录失败: {str(e)}"
        }


def _generate_tree_structure(items: List[Dict], max_depth: int, prefix: str = "", is_last: bool = True) -> str:
    """
    生成树形结构的字符串表示
    
    Args:
        items: 目录项列表
        max_depth: 最大深度
        prefix: 前缀字符串
        is_last: 是否是最后一项
        
    Returns:
        str: 树形结构字符串
    """
    lines = []
    
    for i, item in enumerate(items):
        is_last_item = (i == len(items) - 1)
        connector = "└── " if is_last_item else "├── "
        
        # 添加当前项
        if item["is_dir"]:
            lines.append(f"{prefix}{connector}📁 {item['name']}/")
            
            # 如果有子项且深度允许，递归处理
            if "children" in item and item["children"]:
                extension = "    " if is_last_item else "│   "
                child_lines = _generate_tree_structure(
                    item["children"], 
                    max_depth, 
                    prefix + extension, 
                    True  # 子目录总是作为独立的树处理，所以设为True
                )
                if child_lines:  # 确保有内容才添加
                    lines.append(child_lines)
        else:
            lines.append(f"{prefix}{connector}📄 {item['name']}")
    
    return "\n".join(lines)


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    获取文件信息
    
    Args:
        file_path: 文件路径
        
    Returns:
        dict: {
            "status": "success" | "error",
            "name": "文件名",
            "path": "完整路径",
            "size": "文件大小（字节）",
            "created": "创建时间",
            "modified": "修改时间",
            "is_file": "是否为文件",
            "suffix": "文件后缀",
            "error": "错误信息"
        }
    """
    path = Path(file_path)
    
    # 如果是相对路径，需要与工作空间路径拼接
    if not path.is_absolute():
        from utils.session_manager import get_workspace_path
        workspace_path = Path(get_workspace_path())
        path = workspace_path / file_path
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"文件不存在: {file_path}, 尝试的完整路径: {path.absolute()}"
        }
    
    try:
        stat = path.stat()
        
        return {
            "status": "success",
            "name": path.name,
            "path": str(path.absolute()),
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "suffix": path.suffix,
            "message": f"文件信息已获取"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"获取信息失败: {str(e)}"
        }

def get_file_structure(
    file_path: str,
    encoding: str = None
) -> Dict[str, Any]:
    """
    获取文件的结构信息，包括类、方法、属性等
    
    Args:
        file_path: 文件路径
        encoding: 文件编码，默认从配置读取
        
    Returns:
        dict: {
            "status": "success" | "error",
            "classes": [类信息列表],
            "module_vars": [模块级变量列表],
            "functions": [模块级函数列表],
            "imports": [导入语句列表],
            "docstring": "模块级文档字符串",
            "encoding": "使用的编码",
            "file_path": "文件路径",
            "error": "错误信息"
        }
    """
    # 读取整个文件内容
    read_result = read_file_full(file_path, encoding)
    
    if read_result["status"] == "error":
        return read_result
    
    content = read_result["content"]
    
    try:
        # 解析AST
        tree = ast.parse(content)
        
        result = {
            "status": "success",
            "classes": [],
            "module_vars": [],
            "functions": [],
            "imports": [],
            "docstring": None,
            "encoding": read_result["encoding"],
            "file_path": file_path,
            "message": "成功解析文件结构"
        }
        
        # 获取模块级文档字符串
        result["docstring"] = ast.get_docstring(tree)
        
        # 遍历AST节点
        for node in tree.body:
            # 类定义
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
                    "docstring": ast.get_docstring(node) or "",  # 确保文档字符串不为None
                    "methods": [],
                    "properties": [],
                    "line_number": node.lineno  # 添加行号信息
                }
                
                # 查找类中的属性和方法
                for class_node in node.body:
                    # 属性定义
                    if isinstance(class_node, ast.Assign):
                        for target in class_node.targets:
                            if isinstance(target, ast.Name):
                                class_info["properties"].append({
                                    "name": target.id,
                                    "line_number": class_node.lineno
                                })
                    # 方法定义
                    elif isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_info = {
                            "name": class_node.name,
                            "docstring": ast.get_docstring(class_node) or "",  # 确保文档字符串不为None
                            "args": [arg.arg for arg in class_node.args.args],
                            "is_async": isinstance(class_node, ast.AsyncFunctionDef),  # 添加异步方法识别
                            "line_number": class_node.lineno,  # 添加行号信息
                            "decorators": [ast.unparse(dec) for dec in class_node.decorator_list]  # 添加装饰器信息
                        }
                        class_info["methods"].append(method_info)
                
                result["classes"].append(class_info)
            
            # 模块级变量定义
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_info = {
                            "name": target.id,
                            "line_number": node.lineno,  # 添加行号信息
                            "value": ast.unparse(node.value) if hasattr(node, 'value') else None
                        }
                        result["module_vars"].append(var_info)
            
            # 模块级函数定义（包括异步函数）
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = {
                    "name": node.name,
                    "docstring": ast.get_docstring(node) or "",  # 确保文档字符串不为None
                    "args": [arg.arg for arg in node.args.args],
                    "is_async": isinstance(node, ast.AsyncFunctionDef),  # 添加异步函数识别
                    "line_number": node.lineno,  # 添加行号信息
                    "decorators": [ast.unparse(dec) for dec in node.decorator_list]  # 添加装饰器信息
                }
                result["functions"].append(func_info)
            
            # 导入语句
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    import_info = {
                        "name": alias.name,
                        "asname": alias.asname,
                        "line_number": node.lineno  # 添加行号信息
                    }
                    result["imports"].append(import_info)
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                for alias in node.names:
                    import_info = {
                        "name": f"{module}.{alias.name}",
                        "asname": alias.asname,
                        "line_number": node.lineno  # 添加行号信息
                    }
                    result["imports"].append(import_info)
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"文件结构解析失败: {str(e)}",
            "file_path": file_path
        }



def find_method(
    file_path: str,
    method_names: List[str],
    class_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    查找指定的方法并返回其内容和范围
    
    Args:
        file_path: 文件路径
        method_names: 要查找的方法名列表
        class_names: 要查找的类名列表，与method_names一一对应
    
    Returns:
        dict: {
            "status": "success" | "error",
            "results": [方法信息列表],
            "not_found": [未找到的方法列表],
            "file_path": "文件路径",
            "error": "错误信息"
        }
    """
    # 读取整个文件内容
    read_result = read_file_full(file_path)
    
    if read_result["status"] == "error":
        return read_result
    
    content = read_result["content"]
    
    try:
        # 解析AST
        tree = ast.parse(content)
        
        results = []
        not_found = []
        
        # 创建方法查找映射
        method_map = {}
        if class_names:
            for cls_name, meth_name in zip(class_names, method_names):
                if cls_name not in method_map:
                    method_map[cls_name] = []
                method_map[cls_name].append(meth_name)
        else:
            # 没有指定类名时，查找所有方法
            method_map[None] = method_names
        
        # 遍历AST节点
        for node in tree.body:
            # 如果是类定义且在查找列表中
            if isinstance(node, ast.ClassDef):
                cls_name = node.name
                
                # 检查是否需要查找此类中的方法
                if cls_name in method_map:
                    methods_to_find = method_map[cls_name]
                    
                    # 查找类中的方法
                    for class_node in node.body:
                        if isinstance(class_node, ast.FunctionDef):
                            if class_node.name in methods_to_find:
                                # 获取方法的起始和结束行号
                                start_line = class_node.lineno - 1  # 转换为0-based
                                end_line = class_node.body[-1].lineno if class_node.body else start_line
                                
                                # 提取方法内容
                                lines = content.splitlines()
                                method_content = "\n".join(lines[start_line:end_line])
                                
                                results.append({
                                    "class_name": cls_name,
                                    "method_name": class_node.name,
                                    "start_line": start_line,
                                    "end_line": end_line - 1,  # 转换为0-based
                                    "content": method_content,
                                    "docstring": ast.get_docstring(class_node)
                                })
                                
                                methods_to_find.remove(class_node.name)
                    
                    # 记录未找到的方法
                    not_found.extend([
                                        {
                                            "class_name": cls_name,
                                            "method_name": name
                                        } for name in methods_to_find
                                    ])
                    
                    # 从查找列表中移除已处理的类
                    del method_map[cls_name]
            
        # 查找模块级函数（没有类名的方法）
        if None in method_map:
            methods_to_find = method_map[None]
            
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name in methods_to_find:
                    # 获取方法的起始和结束行号
                    start_line = node.lineno - 1  # 转换为0-based
                    end_line = node.body[-1].lineno if node.body else start_line
                    
                    # 提取方法内容
                    lines = content.splitlines()
                    method_content = "\n".join(lines[start_line:end_line])
                    
                    results.append({
                        "method_name": node.name,
                        "start_line": start_line,
                        "end_line": end_line - 1,  # 转换为0-based
                        "content": method_content,
                        "docstring": ast.get_docstring(node)
                    })
                    
                    methods_to_find.remove(node.name)
            
            # 记录未找到的方法
            not_found.extend([
                                {
                                    "method_name": name
                                } for name in methods_to_find
                            ])
        
        return {
            "status": "success",
            "results": results,
            "not_found": not_found,
            "file_path": file_path,
            "message": f"找到 {len(results)} 个方法，未找到 {len(not_found)} 个方法"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"方法查找失败: {str(e)}",
            "file_path": file_path
        }


if __name__ == "__main__":
    # 测试示例
    # result = locate_file("*.py")
    # print(result)
    result=get_file_structure("D:\\developer\\myProject\\buffer\\samrt_agent\\utils\\memery_manager.py")
    print(result)
