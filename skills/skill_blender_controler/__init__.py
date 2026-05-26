"""
Blender 3D 建模专业助手（MCP 协议）
通过 MCP (Model Context Protocol) 与 Blender 通信，执行 bpy Python 脚本

核心操作方式：
- execute_blender_operation: 统一的 Blender 代码执行入口
- BlenderMCPClient: Blender MCP 客户端类
"""

from .tools import (
    # 核心工具：执行 bpy 代码
    execute_blender_operation,
    execute_blender_code,
    BlenderMCPClient
)

__all__ = [
    'execute_blender_operation',  # 核心工具（统一入口）
    'execute_blender_code',       # 便捷函数
    'BlenderMCPClient'            # 客户端类
]
