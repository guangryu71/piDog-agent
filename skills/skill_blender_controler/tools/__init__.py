"""
Blender 3D 建模控制工具
通过 TCP Socket (line-delimited JSON) 与 Blender MCP 服务通信
消息格式: {"type": "execute_code", "params": {"code": "..."}}

核心工具：execute_blender_operation
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
    
    这是唯一的工具函数，所有 Blender 操作都通过这个函数完成。
    将 Blender Python 代码发送给 Blender MCP 服务执行。
    
    Args:
        code: Blender Python 代码字符串（使用 bpy 模块）
        host: MCP 服务器地址，默认 "localhost"
        port: MCP 服务器端口，默认 9876
        timeout: 超时时间（秒），默认 30
        
    Returns:
        dict: 执行结果
            {
                "status": "success" | "error",
                "result": "执行结果",
                "message": "成功消息",
                "error": "错误信息"
            }
    
    Examples:
        >>> # 创建基本几何体
        >>> code = '''
        ... import bpy
        ... # 创建立方体
        ... bpy.ops.mesh.primitive_cube_add()
        ... # 重命名
        ... bpy.context.object.name = "MyCube"
        ... '''
        >>> result = execute_blender_operation(code)
        
        >>> # 创建复杂场景
        >>> code = '''
        ... import bpy
        ... import math
        ... 
        ... # 创建多个球体
        ... for i in range(5):
        ...     bpy.ops.mesh.primitive_sphere_add(
        ...         radius=0.5,
        ...         location=(i * 2, 0, 0)
        ...     )
        ... 
        ... # 添加材质
        ... mat = bpy.data.materials.new(name="Red")
        ... mat.diffuse_color = (1, 0, 0, 1)
        ... bpy.context.object.data.materials.append(mat)
        ... '''
        >>> result = execute_blender_operation(code)
        
        >>> # 获取场景信息
        >>> code = '''
        ... import bpy
        ... print(f"场景中有 {len(bpy.data.objects)} 个对象")
        ... for obj in bpy.data.objects:
        ...     print(f"  - {obj.name} ({obj.type})")
        ... '''
        >>> result = execute_blender_operation(code)
    """
    return execute_blender_code(code, host=host, port=port, timeout=timeout)


# 导出主要功能
__all__ = ['execute_blender_operation', 'execute_blender_code', 'BlenderMCPClient']
