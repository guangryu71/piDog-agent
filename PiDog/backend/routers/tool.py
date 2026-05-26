"""
工具路由 —— 查看已注册工具
"""

from fastapi import APIRouter
from services import tool_service

router = APIRouter(prefix="/api/tools", tags=["Tools"])


@router.get("")
def list_tools():
    """列出所有工具"""
    return tool_service.list_tools()


@router.get("/{name}")
def get_tool(name: str):
    """获取单个工具详情"""
    result = tool_service.get_tool(name)
    if result is None:
        return {"error": f"Tool '{name}' not found"}
    return result
