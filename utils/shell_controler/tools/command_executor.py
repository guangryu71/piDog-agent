"""
PowerShell命令执行工具 - 执行命令、脚本、生成常用命令
"""

import subprocess
import platform
from typing import Dict, Any, Optional, List
import os
from pathlib import Path

# 配置加载（skill_config_loader 模块不存在，使用空配置）
def get_skill_config(skill_name: str):
    return {}


def get_project_root() -> str:
    """
    获取项目根目录路径
    
    Returns:
        str: 项目根目录的绝对路径
    """
    # 获取当前文件的目录（utils/shell_controler/tools/）
    current_dir = Path(__file__).parent.parent.parent.parent
    
    # 项目根目录是当前目录的父目录的父目录
    project_root = current_dir
    
    return str(project_root)


def _process_parameters_with_workspace_paths(
    parameters: Dict[str, Any],
    workspace_path: str
) -> Dict[str, Any]:
    """
    处理参数中的路径，将相对路径转换为绝对路径
    
    Args:
        parameters: 包含路径参数的字典
        workspace_path: 工作空间路径
        
    Returns:
        Dict[str, Any]: 处理后的参数字典
    """
    processed_params = parameters.copy()
    
    # 处理工作目录参数
    if 'working_directory' in processed_params:
        wd = processed_params['working_directory']
        if wd.startswith('work/') or wd.startswith('work\\'):
            # 剥离work/前缀并拼接工作空间路径
            relative_path = wd[5:] if wd.startswith('work/') else wd[5:]
            processed_params['working_directory'] = os.path.join(workspace_path, relative_path)
        elif not os.path.isabs(wd):
            # 如果是相对路径，直接拼接工作空间路径
            processed_params['working_directory'] = os.path.join(workspace_path, wd)
    
    # 处理源路径参数
    if 'source' in processed_params:
        source = processed_params['source']
        if source.startswith('work/') or source.startswith('work\\'):
            # 剥离work/前缀并拼接工作空间路径
            relative_path = source[5:] if source.startswith('work/') else source[5:]
            processed_params['source'] = os.path.join(workspace_path, relative_path)
        elif not os.path.isabs(source):
            # 如果是相对路径，直接拼接工作空间路径
            processed_params['source'] = os.path.join(workspace_path, source)
    
    # 处理目标路径参数
    if 'destination' in processed_params:
        dest = processed_params['destination']
        if dest.startswith('work/') or dest.startswith('work\\'):
            # 剥离work/前缀并拼接工作空间路径
            relative_path = dest[5:] if dest.startswith('work/') else dest[5:]
            processed_params['destination'] = os.path.join(workspace_path, relative_path)
        elif not os.path.isabs(dest):
            # 如果是相对路径，直接拼接工作空间路径
            processed_params['destination'] = os.path.join(workspace_path, dest)
    
    return processed_params


def _validate_command_safety(command: str) -> tuple:
    """
    验证命令安全性
    
    Args:
        command: 要执行的命令
        
    Returns:
        tuple: (is_safe: bool, reason: str)
    """
    try:
        config = get_skill_config('shell_controler')
        
        # 检查黑名单
        blocked = config.get('blocked_commands', [])
        for blocked_cmd in blocked:
            if blocked_cmd.lower() in command.lower():
                return False, f"命令被禁止: {blocked_cmd}"
        
        # 检查白名单（如果设置了）
        allowed = config.get('allowed_commands', [])
        if allowed and len(allowed) > 0:
            is_allowed = any(cmd.lower() in command.lower() for cmd in allowed)
            if not is_allowed:
                return False, "命令不在白名单中"
        
        return True, ""
    except Exception:
        # 如果配置加载失败，允许所有命令（降级处理）
        return True, ""


def execute_command(
    command: str,
    timeout: int = None,
    capture_output: bool = True,
    working_directory: str = None
) -> Dict[str, Any]:
    """
    执行PowerShell命令
    
    Args:
        command: 要执行的PowerShell命令
        timeout: 超时时间（秒），默认从配置读取
        capture_output: 是否捕获输出
        working_directory: 工作目录路径，如果提供则在此目录下执行命令
        
    Returns:
        dict: {
            "status": "success" | "failed" | "error",
            "command": "执行的命令",
            "stdout": "标准输出",
            "stderr": "错误输出",
            "returncode": "返回码",
            "timeout": "是否超时",
            "error": "错误信息"
        }
    """
    # 验证平台
    if platform.system() != "Windows":
        return {
            "status": "error",
            "error": "当前系统不支持PowerShell，仅支持Windows"
        }
    
    # 从配置读取默认超时时间
    if timeout is None:
        try:
            config = get_skill_config('shell_controler')
            timeout = config.get('default_timeout', 30)
        except Exception:
            timeout = 30
    
    # 验证命令安全性
    is_safe, reason = _validate_command_safety(command)
    if not is_safe:
        return {
            "status": "error",
            "command": command,
            "error": f"安全验证失败: {reason}"
        }
    
    # 🔥 修复：处理命令中的相对路径，确保在工作目录下执行
    import re
    processed_command = command
    
    # 检查命令是否包含相对路径（但不包含绝对路径或特殊字符）
    # 针对Get-ChildItem命令处理路径
    if 'Get-ChildItem' in command or 'ls ' in command or 'dir ' in command:
        # 检查是否包含相对路径（不以盘符开头，不以/或\开头的路径）
        # 模式：Get-ChildItem [相对路径] 或 Get-ChildItem -Path [相对路径]
        pattern = r'(Get-ChildItem|ls|dir)(\s+-Path\s+|\s+)([^\s"\'\d][^"\s\']*|"[^"]*"|\'[^\']*\')(?=\s|$|-Recurse|-Depth)'
        matches = re.findall(pattern, command, re.IGNORECASE)
        
        for match in matches:
            full_match = f"{match[0]}{match[1]}{match[2]}"
            # 检查匹配的路径是否是相对路径（不包含冒号或以/或\开头）
            path_part = match[2].strip('"\'')
            
            # 如果是相对路径（不含冒号且不以/或\开头），则在前面加上工作目录
            if not re.search(r'[A-Za-z]:', path_part) and not path_part.startswith('/') and not path_part.startswith('\\'):
                # 获取工作空间路径
                from utils.session_manager import get_workspace_path
                workspace_path = get_workspace_path()
                
                # 构建完整路径（仅在必要时）
                full_path = os.path.join(workspace_path, path_part)
                # 用完整路径替换原命令中的相对路径
                processed_command = processed_command.replace(full_match.strip(), f'{match[0]}{match[1]}"{full_path}"')
    
    try:
        # 获取工作空间路径
        from utils.session_manager import get_workspace_path
        workspace_path = get_workspace_path()
        
        # 如果提供了工作目录，先切换到该目录再执行命令
        cwd = None
        if working_directory:
            # 现在假定大模型已提供完整路径
            if os.path.isabs(working_directory):
                cwd = working_directory
            else:
                # 如果不是绝对路径，拼接工作空间路径（为了向后兼容）
                cwd = os.path.join(workspace_path, working_directory)
            
            # 确认路径存在
            if not os.path.exists(cwd):
                return {
                    "status": "error",
                    "command": command,
                    "error": f"工作目录不存在: {cwd}"
                }
        else:
            # 默认情况下，在工作空间路径下执行命令，而不是在项目根目录
            cwd = workspace_path
            print(f"[INFO] Running command in workspace: {cwd}")
        
        # Windows PowerShell 输出使用系统编码（中文Windows=GBK），不能用 utf-8
        # 先用系统编码，遇到无法解码的字符用替换字符代替
        system_encoding = 'gbk' if platform.system() == 'Windows' else 'utf-8'
        result = subprocess.run(
            ["powershell", "-Command", processed_command],
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            encoding=system_encoding,
            errors='replace',  # 遇到无法解码的字符用替换字符代替
            cwd=cwd  # 设置工作目录
        )
        
        status = "success" if result.returncode == 0 else "failed"
        
        return {
            "status": status,
            "command": command,
            "stdout": result.stdout if capture_output else "",
            "stderr": result.stderr if capture_output else "",
            "returncode": result.returncode,
            "timeout": False,
            "message": f"命令执行{'成功' if status == 'success' else '失败'}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "command": command,
            "stdout": "",
            "stderr": f"命令执行超时 ({timeout}秒)",
            "returncode": -1,
            "timeout": True,
            "error": f"超时: {timeout}秒"
        }
    except Exception as e:
        return {
            "status": "error",
            "command": command,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "timeout": False,
            "error": f"执行失败: {str(e)}"
        }


def validate_python_syntax(file_path: str) -> Dict[str, Any]:
    """
    验证 Python 文件的语法正确性（使用 py_compile）
    
    Args:
        file_path: Python 文件路径
        
    Returns:
        dict: {
            "status": "success" | "failed" | "error",
            "file_path": "文件路径",
            "message": "验证结果消息",
            "error": "错误信息（如果有）"
        }
    """
    import os
    from pathlib import Path
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {
            "status": "error",
            "file_path": file_path,
            "message": "文件不存在",
            "error": f"文件不存在: {file_path}"
        }
    
    # 检查是否为 Python 文件
    if not file_path.endswith('.py'):
        return {
            "status": "error",
            "file_path": file_path,
            "message": "不是 Python 文件",
            "error": "只支持 .py 文件"
        }
    
    try:
        import py_compile
        
        # 将相对路径转换为绝对路径
        abs_path = str(Path(file_path).resolve())
        
        # 执行语法检查
        py_compile.compile(abs_path, doraise=True)
        
        return {
            "status": "success",
            "file_path": abs_path,
            "message": "Python 语法验证通过",
            "error": None
        }
        
    except py_compile.PyCompileError as e:
        # 语法错误
        error_msg = str(e)
        return {
            "status": "failed",
            "file_path": file_path,
            "message": "Python 语法验证失败",
            "error": error_msg
        }
    except Exception as e:
        # 其他错误
        return {
            "status": "error",
            "file_path": file_path,
            "message": "验证过程出错",
            "error": f"验证失败: {str(e)}"
        }


def validate_multiple_python_files(file_paths: List[str]) -> Dict[str, Any]:
    """
    批量验证多个 Python 文件的语法
    
    Args:
        file_paths: Python 文件路径列表
        
    Returns:
        dict: {
            "status": "success" | "partial_success" | "failed",
            "total": "总文件数",
            "passed": "通过数量",
            "failed": "失败数量",
            "results": [
                {
                    "file_path": "文件路径",
                    "status": "success" | "failed" | "error",
                    "message": "验证结果",
                    "error": "错误信息"
                }
            ]
        }
    """
    results = []
    passed_count = 0
    failed_count = 0
    
    for file_path in file_paths:
        result = validate_python_syntax(file_path)
        results.append(result)
        
        if result['status'] == 'success':
            passed_count += 1
        else:
            failed_count += 1
    
    # 确定总体状态
    if failed_count == 0:
        overall_status = "success"
    elif passed_count == 0:
        overall_status = "failed"
    else:
        overall_status = "partial_success"
    
    return {
        "status": overall_status,
        "total": len(file_paths),
        "passed": passed_count,
        "failed": failed_count,
        "results": results
    }


def execute_script(
    script_path: str,
    args: Optional[List[str]] = None,
    timeout: int = None
) -> Dict[str, Any]:
    """
    执行PowerShell脚本文件
    
    Args:
        script_path: 脚本文件路径 (.ps1)
        args: 脚本参数列表
        timeout: 超时时间（秒），默认从配置读取
        
    Returns:
        dict: 执行结果
    """
    from pathlib import Path
    
    script = Path(script_path)
    
    if not script.exists():
        return {
            "status": "error",
            "error": f"脚本文件不存在: {script_path}"
        }
    
    if not script.suffix == '.ps1':
        return {
            "status": "error",
            "error": "脚本文件必须是.ps1格式"
        }
    
    # 从配置读取默认超时时间
    if timeout is None:
        try:
            config = get_skill_config('shell_controler')
            timeout = 60  # 脚本执行默认60秒
        except Exception:
            timeout = 60
    
    # 构建执行命令
    cmd_parts = [f"& '{script.absolute()}'"]
    if args:
        cmd_parts.extend(args)
    
    command = " ".join(cmd_parts)
    
    return execute_command(command, timeout)


def generate_file_operation_command(
    operation: str,
    source: str,
    destination: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成文件操作相关的PowerShell命令
    
    Args:
        operation: 操作类型 copy/move/delete/rename/create_dir/list
        source: 源文件/目录路径
        destination: 目标路径（可选）
        
    Returns:
        dict: {
            "status": "success" | "error",
            "command": "生成的PowerShell命令",
            "operation": "操作类型",
            "error": "错误信息"
        }
    """
    commands = {
        "copy": f"Copy-Item -Path '{source}' -Destination '{destination}' -Force",
        "move": f"Move-Item -Path '{source}' -Destination '{destination}' -Force",
        "delete": f"Remove-Item -Path '{source}' -Recurse -Force",
        "rename": f"Rename-Item -Path '{source}' -NewName '{destination}'",
        "create_dir": f"New-Item -ItemType Directory -Path '{source}' -Force",
        "list": f"Get-ChildItem -Path '{source}' | Select-Object Name, Length, LastWriteTime",
    }
    
    if operation not in commands:
        return {
            "status": "error",
            "error": f"不支持的操作: {operation}，支持的操作: {list(commands.keys())}"
        }
    
    return {
        "status": "success",
        "command": commands[operation],
        "operation": operation,
        "message": f"已生成{operation}命令"
    }


def generate_system_info_command(
    info_type: str = "basic"
) -> Dict[str, Any]:
    """
    生成系统信息查询命令
    
    Args:
        info_type: 信息类型 basic/network/disk/process/service/memory
        
    Returns:
        dict: {
            "status": "success" | "error",
            "command": "生成的PowerShell命令",
            "info_type": "信息类型",
            "error": "错误信息"
        }
    """
    commands = {
        "basic": "Get-ComputerInfo | Select-Object CsName, OsName, OsVersion, TotalPhysicalMemory",
        "network": "Get-NetIPConfiguration | Format-List",
        "disk": "Get-Volume | Select-Object DriveLetter, FileSystemLabel, SizeRemaining, Size",
        "process": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 20",
        "service": "Get-Service | Where-Object {$_.Status -eq 'Running'}",
        "memory": "Get-Counter '\\Memory\\Available MBytes' | Select-Object -ExpandProperty CounterSamples",
    }
    
    if info_type not in commands:
        return {
            "status": "error",
            "error": f"不支持的信息类型: {info_type}，支持的类型: {list(commands.keys())}"
        }
    
    return {
        "status": "success",
        "command": commands[info_type],
        "info_type": info_type,
        "message": f"已生成{info_type}查询命令"
    }


def generate_search_command(
    search_type: str,
    pattern: str,
    path: str = "."
) -> Dict[str, Any]:
    """
    生成搜索命令
    
    Args:
        search_type: 搜索类型 file/content/directory
        pattern: 搜索模式（支持通配符）
        path: 搜索路径
        
    Returns:
        dict: {
            "status": "success" | "error",
            "command": "生成的搜索命令",
            "search_type": "搜索类型",
            "error": "错误信息"
        }
    """
    if search_type == "file":
        command = f"Get-ChildItem -Path '{path}' -Filter '{pattern}' -Recurse -File"
    elif search_type == "content":
        command = f"Get-ChildItem -Path '{path}' -Recurse -File | Select-String -Pattern '{pattern}'"
    elif search_type == "directory":
        command = f"Get-ChildItem -Path '{path}' -Filter '{pattern}' -Recurse -Directory"
    else:
        return {
            "status": "error",
            "error": f"不支持的搜索类型: {search_type}，支持的类型: file/content/directory"
        }
    
    return {
        "status": "success",
        "command": command,
        "search_type": search_type,
        "pattern": pattern,
        "path": path,
        "message": f"已生成{search_type}搜索命令"
    }


def generate_git_command(
    operation: str,
    repo_path: Optional[str] = None,
    branch: Optional[str] = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成Git相关命令
    
    Args:
        operation: 操作类型 status/pull/push/commit/clone/log
        repo_path: 仓库路径
        branch: 分支名
        message: 提交消息
        
    Returns:
        dict: {
            "status": "success" | "error",
            "command": "生成的Git命令",
            "operation": "操作类型",
            "error": "错误信息"
        }
    """
    base_cmd = "git"
    
    if repo_path and operation != "clone":
        base_cmd += f" -C '{repo_path}'"
    
    commands = {
        "status": f"{base_cmd} status",
        "pull": f"{base_cmd} pull" + (f" origin {branch}" if branch else ""),
        "push": f"{base_cmd} push" + (f" origin {branch}" if branch else ""),
        "commit": f"{base_cmd} commit -m '{message}'" if message else f"{base_cmd} commit",
        "clone": f"{base_cmd} clone {repo_path}" if repo_path else base_cmd,
        "log": f"{base_cmd} log --oneline -10",
    }
    
    if operation not in commands:
        return {
            "status": "error",
            "error": f"不支持的Git操作: {operation}，支持的操作: {list(commands.keys())}"
        }
    
    return {
        "status": "success",
        "command": commands[operation],
        "operation": operation,
        "message": f"已生成git {operation}命令"
    }


def get_command_help(command_name: str) -> Dict[str, Any]:
    """
    获取PowerShell命令的帮助信息
    
    Args:
        command_name: 命令名称
        
    Returns:
        dict: {
            "status": "success" | "error",
            "command": "查询的命令名称",
            "help": "帮助信息",
            "error": "错误信息"
        }
    """
    help_command = f"Get-Help {command_name} -Detailed"
    result = execute_command(help_command)
    
    if result["status"] == "success":
        return {
            "status": "success",
            "command": command_name,
            "help": result["stdout"],
            "message": f"已获取{command_name}的帮助信息"
        }
    else:
        return {
            "status": "error",
            "command": command_name,
            "error": f"获取帮助失败: {result.get('error', result.get('stderr', ''))}"
        }


if __name__ == "__main__":
    # 测试示例
    result = execute_command("Get-Host | Select-Object Version")
    print(result)
