"""
Blender MCP 服务器 —— 通过 bpy 代码控制 Blender 3D 建模

注册工具：
  - blender_execute: 执行 bpy 代码
  - blender_scene_info: 获取当前场景信息
  - blender_clear_scene: 清空场景

启动：python -m MCPS.blender.mcp_server [--port 9101]

注意：需要 Blender 正在运行且 MCP 插件已开启（默认 localhost:9876）
"""

import sys
import os

# 确保项目根目录在 path 中
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from MCPS.base_server import BaseMCPServer
from utils.blender_controler import execute_blender_operation
from utils.blender_controler.blender_mcp_client_v2 import BlenderMCPClient


class BlenderMCPServer(BaseMCPServer):
    """Blender 3D 建模 MCP 服务器"""

    def __init__(self, port: int = 9101):
        super().__init__(name="blender", port=port)
        self._client = BlenderMCPClient()

    def _register_tools(self):
        self.register_tool(
            name="blender_execute",
            description="执行 Blender Python(bpy) 代码进行 3D 建模",
            handler=lambda params: execute_blender_operation(
                code=params.get("code", ""),
                host=params.get("host", "localhost"),
                port=params.get("port", 9876),
                timeout=params.get("timeout", 30),
            ),
        )
        self.register_tool(
            name="blender_scene_info",
            description="获取当前 Blender 场景信息",
            handler=lambda params: self._get_scene_info(),
        )
        self.register_tool(
            name="blender_clear_scene",
            description="清空当前 Blender 场景",
            handler=lambda params: execute_blender_operation(
                code="import bpy; bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)",
                host=params.get("host", "localhost"),
                port=params.get("port", 9876),
            ),
        )

    def _get_scene_info(self) -> dict:
        """获取场景信息"""
        try:
            return self._client.get_scene_info()
        except Exception as e:
            return {"status": "error", "error": f"获取场景信息失败: {e}"}


# ---- CLI 入口 ----
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Blender MCP Server")
    parser.add_argument("--port", type=int, default=9101, help="监听端口")
    args = parser.parse_args()

    server = BlenderMCPServer(port=args.port)
    print(f"启动 Blender MCP 服务器 (端口 {args.port})...")
    server.run()
