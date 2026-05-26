"""
文件写入工具 - 文件写入、内容替换、行替换、目录操作
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import shutil
import time

# 配置加载（skill_config_loader 模块不存在，使用空配置）
def get_skill_config(skill_name: str):
    return {}


def _backup_file(file_path: str) -> bool:
    """
    创建文件备份
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 是否成功创建备份
    """
    try:
        config = get_skill_config('skill_files_controler')
        
        if not config.get('backup_enabled', True):
            return False
        
        backup_dir = config.get('backup_dir', './backups')
        path = Path(file_path)
        
        # 创建备份目录
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # 生成备份文件名（添加时间戳）
        timestamp = int(time.time())
        backup_filename = f"{path.stem}_{timestamp}{path.suffix}"
        backup_file = backup_path / backup_filename
        
        # 复制文件
        shutil.copy2(path, backup_file)
        
        return True
    except Exception:
        return False


def write_file(
    file_path: str,
    content: str,
    mode: str = "overwrite",
    encoding: str = None
) -> Dict[str, Any]:
    """
    写入文件内容
    
    Args:
        file_path: 文件路径
        content: 要写入的内容
        mode: 写入模式 overwrite-覆盖 / append-追加
        encoding: 文件编码，默认从配置读取
        
    Returns:
        dict: {
            "status": "success" | "error",
            "file_path": "文件路径",
            "mode": "写入模式",
            "bytes_written": "写入的字节数",
            "error": "错误信息"
        }
    """
    # 从配置读取默认编码
    if encoding is None:
        try:
            config = get_skill_config('skill_files_controler')
            encoding = config.get('default_encoding', 'utf-8')
        except Exception:
            encoding = 'utf-8'
    
    try:
        path = Path(file_path)
        
        # 如果是相对路径，需要与工作空间路径拼接
        if not path.is_absolute():
            from utils.session_manager import get_workspace_path
            workspace_path = Path(get_workspace_path())
            path = workspace_path / file_path
        
        # 如果覆盖模式且文件存在，先创建备份
        if mode == "overwrite" and path.exists():
            _backup_file(str(path))
        
        # 确保父目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        write_mode = 'a' if mode == "append" else 'w'
        
        with open(path, write_mode, encoding=encoding) as f:
            f.write(content)
        
        bytes_written = len(content.encode(encoding))
        
        return {
            "status": "success",
            "file_path": str(path.absolute()),
            "mode": mode,
            "bytes_written": bytes_written,
            "message": f"已{'追加' if mode == 'append' else '写入'}{bytes_written}字节"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"写入失败: {str(e)}"
        }


def replace_content(
    file_path: str,
    old_content: str,
    new_content: str,
    encoding: str = None
) -> Dict[str, Any]:
    """
    替换文件中的指定内容
    
    Args:
        file_path: 文件路径
        old_content: 要替换的旧内容
        new_content: 新的内容
        encoding: 文件编码，默认从配置读取
        
    Returns:
        dict: {
            "status": "success" | "error",
            "file_path": "文件路径",
            "replacements": "替换次数",
            "error": "错误信息"
        }
    """
    # 从配置读取默认编码
    if encoding is None:
        try:
            config = get_skill_config('skill_files_controler')
            encoding = config.get('default_encoding', 'utf-8')
        except Exception:
            encoding = 'utf-8'
    
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
        # 创建备份
        _backup_file(str(path))
        
        # 读取原文件内容
        with open(path, 'r', encoding=encoding) as f:
            original_content = f.read()
        
        # 检查是否包含要替换的内容
        if old_content not in original_content:
            return {
                "status": "error",
                "error": "未找到要替换的内容"
            }
        
        # 执行替换
        new_file_content = original_content.replace(old_content, new_content)
        replacement_count = original_content.count(old_content)
        
        # 写回文件
        with open(path, 'w', encoding=encoding) as f:
            f.write(new_file_content)
        
        return {
            "status": "success",
            "file_path": str(path.absolute()),
            "replacements": replacement_count,
            "message": f"已替换{replacement_count}处内容"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"替换失败: {str(e)}"
        }


def replace_lines(
    file_path: str,
    line_number: int,
    new_content: str,
    encoding: str = None
) -> Dict[str, Any]:
    """
    替换文件中的指定行
    
    Args:
        file_path: 文件路径
        line_number: 要替换的行号（从1开始）
        new_content: 新的行内容
        encoding: 文件编码，默认从配置读取
        
    Returns:
        dict: {
            "status": "success" | "error",
            "file_path": "文件路径",
            "line": "被替换的行号",
            "error": "错误信息"
        }
    """
    # 从配置读取默认编码
    if encoding is None:
        try:
            config = get_skill_config('skill_files_controler')
            encoding = config.get('default_encoding', 'utf-8')
        except Exception:
            encoding = 'utf-8'
    
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
        # 创建备份
        _backup_file(str(path))
        
        # 读取所有行
        with open(path, 'r', encoding=encoding) as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        if line_number < 1 or line_number > total_lines:
            return {
                "status": "error",
                "error": f"行号超出范围 (1-{total_lines})"
            }
        
        # 替换指定行（保留换行符）
        if lines[line_number - 1].endswith('\n'):
            lines[line_number - 1] = new_content + '\n'
        else:
            lines[line_number - 1] = new_content
        
        # 写回文件
        with open(path, 'w', encoding=encoding) as f:
            f.writelines(lines)
        
        return {
            "status": "success",
            "file_path": str(path.absolute()),
            "line": line_number,
            "message": f"已替换第{line_number}行"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"替换失败: {str(e)}"
        }


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
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"文件不存在: {file_path}"
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


def clear_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    清空文件内容（将文件内容设置为空）
    
    Args:
        file_path: 文件路径
        encoding: 文件编码，默认 utf-8
        
    Returns:
        dict: {
            "status": "success" | "error",
            "message": "操作结果消息",
            "original_size": "原始文件大小（字节）",
            "error": "错误信息"
        }
    """
    path = Path(file_path)
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"文件不存在: {file_path}"
        }
    
    if not path.is_file():
        return {
            "status": "error",
            "error": f"路径不是文件: {file_path}"
        }
    
    try:
        # 获取原始文件大小
        original_size = path.stat().st_size
        
        # 清空文件内容（以写入模式打开会清空内容）
        with open(path, 'w', encoding=encoding) as f:
            pass  # 不写入任何内容
        
        return {
            "status": "success",
            "message": f"文件内容已清空",
            "original_size": original_size,
            "file_path": str(path.absolute())
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"清空文件失败: {str(e)}"
        }


def delete_lines(file_path: str, ifAll: bool = False, start_line: int = 1, end_line: Optional[int] = None, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    删除文件中的指定行范围
    
    Args:
        file_path: 文件路径
        ifAll: 是否删除所有行（清空文件内容），默认 False
        start_line: 起始行号（从1开始），默认第1行（仅在 ifAll=False 时有效）
        end_line: 结束行号（从1开始），None表示到文件末尾（仅在 ifAll=False 时有效）
        encoding: 文件编码，默认 utf-8
        
    Returns:
        dict: {
            "status": "success" | "error",
            "message": "操作结果消息",
            "deleted_lines_count": "删除的行数",
            "remaining_lines_count": "剩余行数",
            "original_lines_count": "原始总行数",
            "file_path": "文件的绝对路径",
            "error": "错误信息"
        }
    
    Examples:
        # 清空整个文件（推荐方式）
        delete_lines("test.txt", ifAll=True)
        
        # 删除前5行
        delete_lines("test.txt", ifAll=False, start_line=1, end_line=5)
        
        # 删除第10-20行
        delete_lines("test.txt", ifAll=False, start_line=10, end_line=20)
        
        # 删除最后一行
        delete_lines("test.txt", ifAll=False, start_line=-1, end_line=-1)
    """
    path = Path(file_path)
    
    if not path.exists():
        return {
            "status": "error",
            "error": f"文件不存在: {file_path}"
        }
    
    if not path.is_file():
        return {
            "status": "error",
            "error": f"路径不是文件: {file_path}"
        }
    
    try:
        # 读取所有行
        with open(path, 'r', encoding=encoding) as f:
            all_lines = f.readlines()
        
        original_lines_count = len(all_lines)
        
        if original_lines_count == 0:
            return {
                "status": "error",
                "error": "文件为空，无法删除行"
            }
        
        # 如果 ifAll 为 True，清空整个文件
        if ifAll:
            with open(path, 'w', encoding=encoding) as f:
                pass  # 不写入任何内容
            
            return {
                "status": "success",
                "message": "文件内容已全部清空",
                "deleted_lines_count": original_lines_count,
                "remaining_lines_count": 0,
                "original_lines_count": original_lines_count,
                "file_path": str(path.absolute())
            }
        
        # 处理负数索引（如 -1 表示最后一行）
        if start_line < 0:
            start_line = original_lines_count + start_line + 1
        if end_line is not None and end_line < 0:
            end_line = original_lines_count + end_line + 1
        
        # 验证行号范围
        if start_line < 1 or start_line > original_lines_count:
            return {
                "status": "error",
                "error": f"起始行号 {start_line} 超出范围（1-{original_lines_count}）"
            }
        
        if end_line is None:
            end_line = original_lines_count
        elif end_line < 1 or end_line > original_lines_count:
            return {
                "status": "error",
                "error": f"结束行号 {end_line} 超出范围（1-{original_lines_count}）"
            }
        
        if start_line > end_line:
            return {
                "status": "error",
                "error": f"起始行号 {start_line} 不能大于结束行号 {end_line}"
            }
        
        # 计算要删除的行数
        deleted_lines_count = end_line - start_line + 1
        
        # 删除指定行（转换为索引：行号-1）
        remaining_lines = all_lines[:start_line-1] + all_lines[end_line:]
        
        # 写回文件
        with open(path, 'w', encoding=encoding) as f:
            f.writelines(remaining_lines)
        
        remaining_lines_count = len(remaining_lines)
        
        return {
            "status": "success",
            "message": f"已删除第{start_line}-{end_line}行，共{deleted_lines_count}行",
            "deleted_lines_count": deleted_lines_count,
            "remaining_lines_count": remaining_lines_count,
            "original_lines_count": original_lines_count,
            "file_path": str(path.absolute())
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"删除行失败: {str(e)}"
        }


def create_directory(dir_path: str) -> Dict[str, Any]:
    """
    创建目录（自动创建所有父目录）

    Args:
        dir_path: 目录路径（绝对路径或相对工作空间的路径）

    Returns:
        dict: {"status": "success"/"error", "path": "创建的目录路径"}
    """
    from pathlib import Path
    from utils.session_manager import get_workspace_path

    path = Path(dir_path)
    if not path.is_absolute():
        workspace_path = Path(get_workspace_path())
        path = workspace_path / dir_path

    try:
        path.mkdir(parents=True, exist_ok=True)
        return {
            "status": "success",
            "path": str(path.absolute()),
            "message": f"目录已创建: {path}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"创建目录失败: {str(e)}"
        }


if __name__ == "__main__":
    # 测试示例
    result = write_file("test.txt", "Hello World")
    print(result)
