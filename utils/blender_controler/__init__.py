"""
Blender 3D 建模工具 - 从 skills/skill_blender_controler/tools 迁移到 utils 统一管理
通过 TCP Socket 与 Blender MCP 服务通信

MCP 服务器版本：MCPS/blender/mcp_server.py（端口 9101，JSON-RPC 2.0）
"""

from typing import Dict, Any
from .blender_mcp_client_v2 import execute_blender_code, BlenderMCPClient


def execute_blender_operation(
    code: str,
    host: str = "localhost",
    port: int = 9876,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    执行 Blender 操作（统一入口）
    将 Blender Python 代码发送给 Blender MCP 服务执行。
    """
    return execute_blender_code(code, host=host, port=port, timeout=timeout)


__all__ = ['execute_blender_operation', 'execute_blender_code', 'BlenderMCPClient']
