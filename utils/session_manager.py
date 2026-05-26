"""
会话管理器模块
用于管理智能体的工作空间路径和会话状态
"""

import os
from pathlib import Path

# 全局工作空间路径
_workspace_path = None


def set_workspace_path(path: str):
    """
    设置工作空间路径
    
    Args:
        path: 工作空间路径（绝对路径）
    """
    global _workspace_path
    _workspace_path = os.path.abspath(path)
    # 确保目录存在
    os.makedirs(_workspace_path, exist_ok=True)
    print(f"[OK] Workspace path set: {_workspace_path}")


def get_workspace_path() -> str:
    """
    获取工作空间路径
    
    Returns:
        str: 工作空间的绝对路径
    
    Raises:
        RuntimeError: 如果工作空间路径未设置
    """
    if _workspace_path is None:
        raise RuntimeError(
            "工作空间路径未设置！请先调用 set_workspace_path() 初始化。"
        )
    return _workspace_path


def is_workspace_set() -> bool:
    """
    检查工作空间路径是否已设置
    
    Returns:
        bool: 如果已设置返回 True，否则返回 False
    """
    return _workspace_path is not None


def get_absolute_path(relative_path: str) -> str:
    """
    将相对路径转换为绝对路径（相对于工作空间）
    
    Args:
        relative_path: 相对路径
    
    Returns:
        str: 绝对路径
    """
    workspace = get_workspace_path()
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.abspath(os.path.join(workspace, relative_path))
