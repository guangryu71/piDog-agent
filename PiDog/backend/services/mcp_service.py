"""
MCP 管理服务 —— 列出/添加/启用/禁用/删除 MCP 服务器
"""

import sys
import os
from typing import List

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from MCPS import (
    get_mcp_list,
    get_mcp_info,
    start_mcp_server,
    stop_mcp_server,
    set_mcp_enabled,
    MCP_REGISTRY,
    connect_modelscope_mcp,
    disconnect_modelscope_mcp,
    list_modelscope_connections,
    set_modelscope_token,
    get_modelscope_token,
)
from api_schemas.schemas import MCPInfo


def list_mcps() -> List[MCPInfo]:
    """列出所有已注册的 MCP 服务器"""
    items = get_mcp_list()
    return [MCPInfo(**item) for item in items]


def get_mcp(key: str) -> dict:
    """获取单个 MCP 详情"""
    info = get_mcp_info(key)
    if not info:
        return {"ok": False, "error": f"未知 MCP: {key}"}
    return {"ok": True, "mcp": info}


def operate_mcp(key: str, action: str, value: bool = None) -> dict:
    """
    操作 MCP 服务器

    Args:
        key: MCP 标识符 (browser/blender/... 或 ms_xxx 表示魔搭连接)
        action: start / stop / enable / disable / auto_start / delete / disconnect
        value: 仅在 enable/auto_start 时需要
    """
    # ---- 魔搭 MCP 远程连接操作 ----
    if key.startswith("ms_"):
        ms_name = key[3:]
        if action == "disconnect":
            return disconnect_modelscope_mcp(ms_name)
        return {"ok": False, "error": f"魔搭 MCP 不支持操作: {action}"}

    # ---- 注册表内 MCP 操作 ----
    if key not in MCP_REGISTRY:
        if action == "delete":
            return {"ok": True, "key": key, "action": action, "status": "already_removed"}
        return {"ok": False, "error": f"未知 MCP: {key}，可用: {list(MCP_REGISTRY.keys())}"}

    if action == "start":
        return start_mcp_server(key)

    elif action == "stop":
        return stop_mcp_server(key)

    elif action == "enable":
        return set_mcp_enabled(key, True)

    elif action == "disable":
        return set_mcp_enabled(key, False)

    elif action == "auto_start":
        from MCPS import set_mcp_auto_start
        return set_mcp_auto_start(key, bool(value))

    elif action == "delete":
        stop_mcp_server(key)
        del MCP_REGISTRY[key]
        return {"ok": True, "key": key, "action": action, "status": "deleted"}

    return {"ok": False, "error": f"未知操作: {action}"}


# ==================== 魔搭 MCP 广场 ====================


def modelscope_connect(name: str, label: str, sse_url: str) -> dict:
    """连接到魔搭 MCP 服务"""
    return connect_modelscope_mcp(name, label, sse_url)


def modelscope_disconnect(name: str) -> dict:
    """断开魔搭 MCP 服务"""
    return disconnect_modelscope_mcp(name)


def modelscope_set_token(token: str) -> dict:
    """设置魔搭 API Token"""
    return set_modelscope_token(token)


def modelscope_list_connections() -> list:
    """列出所有已连接的魔搭 MCP 服务"""
    return list_modelscope_connections()


def modelscope_get_status() -> dict:
    """获取魔搭 MCP 广场整体状态"""
    conns = list_modelscope_connections()
    return {
        "connected": len(conns),
        "total_tools": sum(c["tool_count"] for c in conns),
        "connections": conns,
        "has_token": bool(get_modelscope_token()),
    }


def add_mcp(key: str, name: str = None, description: str = "") -> dict:
    """
    添加自定义 MCP 服务器（注册到 MCP_REGISTRY）

    Args:
        key: 唯一标识符
        name: 显示名称，默认同 key
        description: 功能描述
    """
    if key in MCP_REGISTRY:
        return {"ok": False, "error": f"MCP '{key}' 已存在"}

    MCP_REGISTRY[key] = {
        "name": name or key,
        "description": description or f"自定义 MCP: {key}",
        "module": "",
        "server_class": "",
        "default_port": 9200 + len(MCP_REGISTRY),
        "enabled": True,
        "auto_start": False,
    }
    return {
        "ok": True,
        "key": key,
        "name": name or key,
        "status": "added",
        "message": f"MCP '{key}' 已添加。请配置 module 和 server_class 后使用。",
    }


# ==================== 魔搭 MCP 搜索 ====================


def modelscope_search(search: str = "", category: str = "", page: int = 1) -> dict:
    """搜索魔搭 MCP 广场的托管服务（含后端限流，防止重复请求压垮魔搭 API）"""
    import time
    if not hasattr(modelscope_search, '_last_call'):
        modelscope_search._last_call = 0
    now = time.time()
    if now - modelscope_search._last_call < 2.0:
        return {"success": False, "message": "rate limited", "servers": [], "total": 0}
    modelscope_search._last_call = now

    from MCPS.modelscope.api_client import search_mcp
    return search_mcp(
        search=search,
        category=category,
        page=page,
        page_size=20,
        token=get_modelscope_token(),
    )


def modelscope_categories() -> list:
    """获取魔搭 MCP 服务分类列表"""
    from MCPS.modelscope.api_client import list_categories
    return list_categories()


def modelscope_deploy(server_id: str, env_info: dict = None) -> dict:
    """
    一键部署并连接 MCP 服务

    流程：
      1. 获取服务详情，检查是否支持托管部署
      2. 若是托管服务 → 调用 deploy API 生成 SSE URL → 自动连接
      3. 若是本地服务 → 返回 server_config 告知用户如何运行
      4. 若需环境变量 → 返回 env_schema 要求用户配置
    """
    from MCPS.modelscope.api_client import ModelScopeAPIClient
    from MCPS import connect_modelscope_mcp

    token = get_modelscope_token()
    client = ModelScopeAPIClient(token)

    # 1. 获取服务详情（判断类型 + 获取 env_schema）
    detail = client.get_mcp_detail(server_id)
    if not detail.get("success", True) and "error" in detail.get("message", ""):
        # 尝试无 token 获取详情
        public_client = ModelScopeAPIClient()
        detail = public_client.get_mcp_detail(server_id)

    is_hosted = detail.get("is_hosted", False)
    env_schema = detail.get("env_schema", {})
    server_config = detail.get("server_config", [])
    operational_urls = detail.get("operational_urls", [])

    # 提取名称
    name = server_id.split("/")[-1] if "/" in server_id else server_id
    zh_locale = (detail.get("locales") or {}).get("zh", {}) or {}
    label = zh_locale.get("name") or detail.get("name") or name

    # ---- 分支 1：已有托管 URL（之前已部署过） ----
    if operational_urls and len(operational_urls) > 0:
        sse_url = operational_urls[0].get("url", "")
        if sse_url:
            conn_result = connect_modelscope_mcp(name, label, sse_url)
            if conn_result.get("ok"):
                return {"ok": True, "server_id": server_id, "name": name, "label": label,
                        "sse_url": sse_url, "tools": conn_result.get("tools", 0),
                        "tool_list": conn_result.get("tool_list", [])}
            return {"ok": True, "sse_url": sse_url, "warning": "已有托管 URL 但自动连接失败"}

    # ---- 分支 2：需要环境变量 ----
    if env_schema:
        required_vars = list(env_schema.keys()) if isinstance(env_schema, dict) else []
        if required_vars and not env_info:
            return {
                "ok": False, "error": f"此 MCP 需要配置环境变量",
                "need_env": True, "env_schema": env_schema,
                "server_id": server_id, "name": name, "label": label,
            }

    # ---- 分支 3：托管服务 → 调用 deploy API ----
    if is_hosted:
        if not token:
            return {"ok": False, "error": "请先配置魔搭 API Token 以部署托管 MCP 服务"}

        from MCPS.modelscope.api_client import deploy_mcp
        result = deploy_mcp(server_id, token=token, env_info=env_info or {})
        if not result.get("success"):
            http_code = result.get("http_code", 0)
            msg = result.get("message", "部署失败")
            return {"ok": False, "error": f"部署失败 (HTTP {http_code}): {msg}"}

        data = result.get("data", {})
        sse_url = data.get("url", "")
        if not sse_url:
            return {"ok": False, "error": "部署成功但未获取到 SSE URL"}

        conn_result = connect_modelscope_mcp(name, label, sse_url)
        if conn_result.get("ok"):
            return {"ok": True, "server_id": server_id, "name": name, "label": label,
                    "sse_url": sse_url, "tools": conn_result.get("tools", 0),
                    "tool_list": conn_result.get("tool_list", [])}
        return {"ok": True, "sse_url": sse_url, "warning": "部署成功但自动连接失败，可手动添加", "name": name}

    # ---- 分支 4：本地命令型服务 ----
    # 提取运行命令
    cmd_hint = ""
    if server_config and len(server_config) > 0:
        for cfg in server_config:
            if isinstance(cfg, dict):
                for key, val in cfg.items():
                    if isinstance(val, dict) and "command" in val:
                        cmd = val["command"]
                        args = " ".join(val.get("args", []))
                        cmd_hint = f"{cmd} {args}".strip()
                    elif isinstance(val, dict) and "url" in val:
                        cmd_hint = f"SSE: {val['url']}"

    return {
        "ok": False,
        "error": "此 MCP 为本地命令型服务，不支持云端部署",
        "is_local": True,
        "server_id": server_id,
        "name": name,
        "label": label,
        "server_config": server_config,
        "command_hint": cmd_hint,
    }
