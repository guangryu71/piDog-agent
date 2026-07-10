"""
MCP 路由 —— 本地 MCP + 魔搭 MCP 广场
"""

from fastapi import APIRouter
from api_schemas.schemas import MCPSwitchRequest
from services import mcp_service

router = APIRouter(prefix="/api/mcp", tags=["MCP"])


# ==================== 通用 MCP 管理 ====================


@router.get("")
def list_mcps():
    """列出所有 MCP 服务器（含魔搭）"""
    return mcp_service.list_mcps()


@router.get("/{key}")
def get_mcp(key: str):
    """获取单个 MCP 详情"""
    return mcp_service.get_mcp(key)


@router.post("/operate")
def operate_mcp(req: MCPSwitchRequest):
    """操作 MCP：start / stop / enable / disable / auto_start / delete / disconnect"""
    return mcp_service.operate_mcp(
        key=req.key,
        action=req.action,
        value=req.value,
    )


@router.post("/add")
def add_mcp(req: dict):
    """添加自定义 MCP"""
    return mcp_service.add_mcp(
        key=req.get("key", ""),
        name=req.get("name"),
        description=req.get("description", ""),
    )


# ==================== 魔搭 MCP 广场 ====================


@router.post("/modelscope/connect")
def modelscope_connect(req: dict):
    """连接魔搭 MCP 服务"""
    return mcp_service.modelscope_connect(
        name=req.get("name", ""),
        label=req.get("label", ""),
        sse_url=req.get("sse_url", ""),
    )


@router.post("/modelscope/disconnect")
def modelscope_disconnect(req: dict):
    """断开魔搭 MCP 服务"""
    return mcp_service.modelscope_disconnect(
        name=req.get("name", ""),
    )


@router.post("/modelscope/token")
def modelscope_set_token(req: dict):
    """设置魔搭 API Token"""
    return mcp_service.modelscope_set_token(
        token=req.get("token", ""),
    )


@router.get("/modelscope/connections")
def modelscope_list_connections():
    """列出所有已连接的魔搭 MCP 服务"""
    return mcp_service.modelscope_list_connections()


@router.get("/modelscope/status")
def modelscope_get_status():
    """获取魔搭 MCP 广场整体状态"""
    return mcp_service.modelscope_get_status()


@router.get("/modelscope/search")
def modelscope_search(search: str = "", category: str = "", page: int = 1):
    """搜索魔搭 MCP 广场的托管服务"""
    # 防御：前端可能传来 NaN，强制转整数
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    if page < 1:
        page = 1
    return mcp_service.modelscope_search(search=search, category=category, page=page)


@router.get("/modelscope/categories")
def modelscope_categories():
    """获取魔搭 MCP 服务分类列表"""
    return mcp_service.modelscope_categories()


@router.post("/modelscope/deploy/{server_id:path}")
def modelscope_deploy(server_id: str, req: dict = None):
    """
    一键部署并连接 MCP 服务

    直接调用魔搭 API 生成 SSE URL 并自动连接。
    无需手动前往魔搭网站获取连接地址。
    """
    env_info = (req or {}).get("env_info") if req else None
    return mcp_service.modelscope_deploy(server_id, env_info=env_info)
