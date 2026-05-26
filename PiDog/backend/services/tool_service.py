"""
工具管理服务 —— 展示已注册的工具列表
"""

from typing import List, Optional
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from utils.tool_registry import get_tool_schemas, get_function_info
from api_schemas.schemas import ToolInfo


def list_tools() -> List[ToolInfo]:
    """列出所有已注册的工具"""
    schemas = get_tool_schemas()
    tools = []
    for s in schemas:
        name = s["function"]["name"]
        desc = s["function"]["description"]
        info = get_function_info(name) or {}
        tools.append(ToolInfo(
            name=name,
            description=desc,
            module=info.get("module") or "N/A",
            function_name=info.get("function") or "N/A",
        ))
    return tools


def get_tool(name: str) -> Optional[ToolInfo]:
    """获取单个工具详情"""
    schemas = get_tool_schemas()
    for s in schemas:
        if s["function"]["name"] == name:
            info = get_function_info(name) or {}
            return ToolInfo(
                name=name,
                description=s["function"]["description"],
                module=info.get("module") or "N/A",
                function_name=info.get("function") or "N/A",
            )
    return None
