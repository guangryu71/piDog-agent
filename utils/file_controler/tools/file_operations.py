"""
文件操作工具 —— 删除文件、目录等（需要用户审批）
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional


def delete_file(path: str, recursive: bool = False) -> Dict[str, Any]:
    """
    删除文件或空目录。删除前会检查路径合法性。

    Args:
        path: 要删除的文件或目录路径（绝对路径或相对于工作目录）
        recursive: 是否递归删除目录及其内容（相当于 rm -rf），默认 False

    Returns:
        {"status": "success"/"error", "path": "...", "message": "...", "error": "..."}
    """
    target = Path(path)

    if not target.exists():
        return {"status": "error", "error": f"路径不存在: {path}"}

    try:
        if target.is_file():
            target.unlink()
            return {
                "status": "success",
                "path": str(target.absolute()),
                "type": "file",
                "message": f"已删除文件: {target.name}",
            }

        elif target.is_dir():
            if recursive:
                shutil.rmtree(target)
                return {
                    "status": "success",
                    "path": str(target.absolute()),
                    "type": "directory",
                    "recursive": True,
                    "message": f"已递归删除目录: {target.name}",
                }
            else:
                # 仅删除空目录
                try:
                    target.rmdir()
                    return {
                        "status": "success",
                        "path": str(target.absolute()),
                        "type": "directory",
                        "recursive": False,
                        "message": f"已删除空目录: {target.name}",
                    }
                except OSError:
                    return {
                        "status": "error",
                        "error": f"目录非空，如需删除请设置 recursive=true: {path}",
                    }

        return {"status": "error", "error": f"不支持的路径类型: {path}"}

    except PermissionError:
        return {"status": "error", "error": f"权限不足，无法删除: {path}"}
    except Exception as e:
        return {"status": "error", "error": f"删除失败: {e}"}
