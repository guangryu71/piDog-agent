"""
MCP 模块 —— 集中管理所有 MCP 服务器

架构：
  MCPS/
  ├── __init__.py           # 注册表 + MCP 管理接口
  ├── base_server.py        # MCP 服务器基类（JSON-RPC 2.0 over HTTP）
  ├── browser/              # 浏览器自动化 MCP
  │   ├── __init__.py
  │   ├── mcp_server.py     # 服务器实现
  │   └── README.md
  ├── blender/              # Blender 3D 建模 MCP
  │   ├── __init__.py
  │   ├── mcp_server.py     # 服务器实现
  │   └── README.md
  └── modelscope/           # 魔搭 MCP 广场连接器
      ├── __init__.py
      ├── connector.py      # SSE 连接器 + 工具调用
      └── README.md

MCP 注册表（MCP_REGISTRY）：
  与 tool_registry.py 的 SKILL_REGISTRY 风格一致，
  每项定义 name、description、server 入口、状态等。

魔搭 MCP 广场集成：
  支持通过 SSE 协议连接魔搭社区 9200+ 托管 MCP 服务。
  连接成功后自动发现工具，可像本地 MCP 一样调用。
"""

import os
import sys
import json
import subprocess
import threading
from typing import Dict, List, Optional, Any

# ================================================================
# MCP 注册表 —— 定义所有可用的 MCP 服务器
# ================================================================

MCP_REGISTRY: Dict[str, Dict[str, Any]] = {
    "browser": {
        "name": "浏览器自动化",
        "description": "基于 Playwright 的浏览器控制：打开网页、点击、输入、截图、获取快照等",
        "module": "MCPS.browser.mcp_server",
        "server_class": "BrowserMCPServer",
        "default_port": 9100,
        "enabled": True,
        "auto_start": False,
        "type": "local",  # 本地 MCP 服务器
    },
    "blender": {
        "name": "Blender 3D 建模",
        "description": "通过 bpy Python 代码控制 Blender 进行 3D 建模：创建几何体、材质、灯光、渲染",
        "module": "MCPS.blender.mcp_server",
        "server_class": "BlenderMCPServer",
        "default_port": 9101,
        "enabled": True,
        "auto_start": False,
        "type": "local",
    },
    "modelscope": {
        "name": "魔搭 MCP 广场",
        "description": "连接魔搭社区 9200+ 托管 MCP 服务（SSE 协议），自动发现并调用工具",
        "module": "",
        "server_class": "",
        "default_port": 0,
        "enabled": True,
        "auto_start": False,
        "type": "hub",  # MCP 市场/连接器
    },
}


# ================================================================
# MCP 服务器管理器 —— 运行时状态
# ================================================================

_running_servers: Dict[str, Any] = {}  # name → {"process": ..., "port": ...}
_modelscope_connections: Dict[str, Any] = {}  # name → ModelScopeMCPConnection
_modelscope_token: str = ""  # 魔搭 API Token


def get_mcp_list() -> List[Dict[str, Any]]:
    """获取所有 MCP 服务器列表（含运行状态 + 魔搭已连接服务）"""
    result = []
    # 本地 + hub 类型
    for key, info in MCP_REGISTRY.items():
        running = key in _running_servers and _running_servers[key].get("server") is not None
        entry = {
            "key": key,
            "name": info["name"],
            "description": info["description"],
            "enabled": info.get("enabled", True),
            "running": running,
            "port": info.get("default_port", 0),
            "auto_start": info.get("auto_start", False),
            "type": info.get("type", "local"),
        }
        # hub 类型：附带连接的 MCP 数量
        if info.get("type") == "hub":
            entry["connected_count"] = len(_modelscope_connections)
            entry["total_tools"] = sum(
                len(c.tools) for c in _modelscope_connections.values()
            )
        result.append(entry)

    # 已连接的魔搭 MCP 服务（作为独立条目展示）
    for name, conn in _modelscope_connections.items():
        result.append({
            "key": f"ms_{name}",
            "name": conn.label,
            "description": f"魔搭 MCP: {conn.sse_url}",
            "enabled": True,
            "running": conn.is_connected,
            "port": 0,
            "auto_start": False,
            "type": "modelscope_remote",
            "ms_name": name,
            "tool_count": len(conn.tools),
        })
    return result


def get_mcp_info(key: str) -> Optional[Dict[str, Any]]:
    """获取单个 MCP 服务器详情"""
    # 先查注册表
    if key in MCP_REGISTRY:
        info = dict(MCP_REGISTRY[key])
        running = key in _running_servers and _running_servers[key].get("server") is not None
        info["key"] = key
        info["running"] = running
        if info.get("type") == "hub":
            info["connected_services"] = [
                {"name": n, "label": c.label, "connected": c.is_connected, "tools": len(c.tools)}
                for n, c in _modelscope_connections.items()
            ]
            info["token_configured"] = bool(_modelscope_token)
        return info

    # 查魔搭连接（key 格式: ms_{name}）
    if key.startswith("ms_"):
        name = key[3:]
        if name in _modelscope_connections:
            conn = _modelscope_connections[name]
            return {
                "key": key,
                "name": conn.label,
                "description": f"魔搭 MCP: {conn.sse_url}",
                "running": conn.is_connected,
                "type": "modelscope_remote",
                "ms_name": name,
                "sse_url": conn.sse_url,
                "tools": conn.tools,
            }

    return None


def start_mcp_server(name: str) -> dict:
    """启动 MCP 服务器"""
    if name not in MCP_REGISTRY:
        return {"ok": False, "error": f"未知 MCP: {name}"}

    if name in _running_servers and _running_servers[name].get("server"):
        return {"ok": False, "error": f"MCP '{name}' 已在运行中"}

    info = MCP_REGISTRY[name]
    try:
        # 动态导入并实例化
        module = __import__(info["module"], fromlist=[info["server_class"]])
        server_class = getattr(module, info["server_class"])
        port = info.get("default_port", 9100)
        server = server_class(port=port)

        # 在独立线程中启动
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        _running_servers[name] = {
            "server": server,
            "thread": thread,
            "port": port,
        }
        return {"ok": True, "name": name, "port": port, "status": "started"}
    except Exception as e:
        return {"ok": False, "error": f"启动 MCP '{name}' 失败: {e}"}


def stop_mcp_server(name: str) -> dict:
    """停止 MCP 服务器"""
    if name not in _running_servers:
        return {"ok": False, "error": f"MCP '{name}' 未在运行"}

    try:
        server = _running_servers[name].get("server")
        if server and hasattr(server, "stop"):
            server.stop()
        del _running_servers[name]
        return {"ok": True, "name": name, "status": "stopped"}
    except Exception as e:
        return {"ok": False, "error": f"停止 MCP '{name}' 失败: {e}"}


def set_mcp_enabled(name: str, enabled: bool) -> dict:
    """启用/禁用 MCP 服务器"""
    if name not in MCP_REGISTRY:
        return {"ok": False, "error": f"未知 MCP: {name}"}
    MCP_REGISTRY[name]["enabled"] = enabled
    if not enabled and name in _running_servers:
        stop_mcp_server(name)
    return {"ok": True, "name": name, "enabled": enabled}


def set_mcp_auto_start(name: str, auto_start: bool) -> dict:
    """设置 MCP 是否自动启动"""
    if name not in MCP_REGISTRY:
        return {"ok": False, "error": f"未知 MCP: {name}"}
    MCP_REGISTRY[name]["auto_start"] = auto_start
    return {"ok": True, "name": name, "auto_start": auto_start}


# ================================================================
# 魔搭 MCP 广场连接器管理
# ================================================================


# MCP 连接持久化文件
_MCP_CONNECTIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "PiDog", "backend", "mcp_connections.json",
)


def _load_persisted_connections():
    """从文件加载持久化的 MCP 连接"""
    if not os.path.exists(_MCP_CONNECTIONS_FILE):
        return []
    try:
        with open(_MCP_CONNECTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_persisted_connections():
    """保存 MCP 连接到文件（含工具列表，用于启动后注册到 LLM）"""
    entries = []
    for name, conn in _modelscope_connections.items():
        entries.append({
            "name": name,
            "label": conn.label,
            "sse_url": conn.sse_url,
            "tools": conn.tools if hasattr(conn, 'tools') and conn.tools else [],
        })
    try:
        os.makedirs(os.path.dirname(_MCP_CONNECTIONS_FILE), exist_ok=True)
        with open(_MCP_CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import logging
        logging.getLogger("mcp").warning("保存 MCP 连接失败: %s", e)


def _init_modelscope_from_config():
    """从 AppState / confing.json 初始化 Token，并恢复已持久化的连接"""
    global _modelscope_token
    # 从 AppState 读取已加载的 token
    try:
        from config import AppState
        if AppState.modelscope_token:
            _modelscope_token = AppState.modelscope_token
    except Exception:
        pass

    # 恢复已持久化的 MCP 连接
    persisted = _load_persisted_connections()
    for entry in persisted:
        name = entry.get("name", "")
        label = entry.get("label", "")
        sse_url = entry.get("sse_url", "")
        saved_tools = entry.get("tools", [])
        if name and sse_url and name not in _modelscope_connections:
            # 创建连接对象但不实际发起网络连接（启动时只注册，不连接）
            from MCPS.modelscope.connector import ModelScopeMCPConnection
            conn = ModelScopeMCPConnection(name, label, sse_url)
            conn._connected = False  # 标记为离线
            # 从持久化恢复工具列表，让 LLM 能看到工具
            conn._tools = saved_tools if isinstance(saved_tools, list) else []
            _modelscope_connections[name] = conn


def set_modelscope_token(token: str):
    """设置魔搭 API Token（持久化到 confing.json）"""
    global _modelscope_token
    _modelscope_token = token

    # 持久化到 confing.json
    try:
        from config import PROJECT_ROOT, AppState
        AppState.modelscope_token = token
        config_path = os.path.join(PROJECT_ROOT, "confing.json")
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ms = data.setdefault("modelscope_config", {})
        ms["token"] = token
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import logging
        logging.getLogger("mcp").warning("持久化 Token 失败: %s", e)

    return {"ok": True, "configured": bool(token)}


def get_modelscope_token() -> str:
    """获取魔搭 API Token"""
    return _modelscope_token


# 模块加载时自动初始化
_init_modelscope_from_config()


def connect_modelscope_mcp(name: str, label: str, sse_url: str) -> dict:
    """连接到魔搭 MCP 服务"""
    from MCPS.modelscope.connector import ModelScopeMCPConnection

    if name in _modelscope_connections:
        if _modelscope_connections[name].is_connected:
            return {"ok": False, "error": f"MCP '{name}' 已连接"}

    conn = ModelScopeMCPConnection(name, label, sse_url, _modelscope_token)

    # 异步连接（在独立线程的事件循环中执行）
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_until_complete, args=(conn.connect(),), daemon=True)
        thread.start()
        thread.join(timeout=15)

        if conn.is_connected:
            _modelscope_connections[name] = conn
            return {
                "ok": True,
                "name": name,
                "label": label,
                "tools": len(conn.tools),
                "tool_list": conn.tools,
            }
        else:
            return {"ok": False, "error": "连接超时或失败"}
    except Exception as e:
        return {"ok": False, "error": f"连接失败: {e}"}
    finally:
        # 无论成功失败，都持久化连接记录（失败时记录一个离线连接）
        if name not in _modelscope_connections and sse_url:
            from MCPS.modelscope.connector import ModelScopeMCPConnection
            _modelscope_connections[name] = ModelScopeMCPConnection(name, label, sse_url)
        _save_persisted_connections()


def disconnect_modelscope_mcp(name: str) -> dict:
    """断开魔搭 MCP 服务"""
    if name not in _modelscope_connections:
        return {"ok": False, "error": f"MCP '{name}' 未连接"}

    conn = _modelscope_connections.pop(name)
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_until_complete, args=(conn.disconnect(),), daemon=True)
        thread.start()
        thread.join(timeout=10)
        return {"ok": True, "name": name, "status": "disconnected"}
    except Exception as e:
        return {"ok": False, "error": f"断开失败: {e}"}
    finally:
        _save_persisted_connections()


def disconnect_all_modelscope():
    """断开所有魔搭 MCP 连接"""
    for name in list(_modelscope_connections.keys()):
        disconnect_modelscope_mcp(name)


def call_modelscope_tool(ms_name: str, tool_name: str, arguments: dict = None) -> dict:
    """调用魔搭 MCP 工具"""
    conn = _modelscope_connections.get(ms_name)
    if not conn:
        return {"status": "error", "error": f"MCP '{ms_name}' 未连接"}

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=loop.run_until_complete,
            args=(conn.call_tool(tool_name, arguments or {}),),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        return {"status": "success", "result": "工具调用已发送"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_connected_mcp_tool_schemas() -> List[Dict[str, Any]]:
    """
    获取所有已连接 MCP 服务的工具 Schema（OpenAI Function Calling 格式）。

    每个工具的名称格式: mcp__{service_name}__{tool_name}
    LLM 调用时将按此格式路由到对应的 MCP 连接。

    Returns:
        [{"type": "function", "function": {"name": "mcp__fetch__fetch_url", ...}}, ...]
    """
    schemas = []
    for name, conn in _modelscope_connections.items():
        # 包含离线但有缓存的工具（持久化加载的连接）
        tools = conn.tools if hasattr(conn, 'tools') and conn.tools else []

        if tools:
            for tool in tools:
                tool_name = tool.get("name", "")
                tool_desc = tool.get("description", "")
                input_schema = tool.get("inputSchema", {})

                schemas.append({
                    "type": "function",
                    "function": {
                        "name": f"mcp__{name}__{tool_name}",
                        "description": f"[MCP {conn.label}] {tool_desc}",
                        "parameters": input_schema if input_schema
                        else {"type": "object", "properties": {}},
                    },
                })
        else:
            # 无缓存工具时，注册一个通用 describe 工具，让 LLM 至少知道该服务存在
            schemas.append({
                "type": "function",
                "function": {
                    "name": f"mcp__{name}__describe",
                    "description": f"[MCP {conn.label}] 获取 {conn.label} 的可用工具列表和功能介绍",
                    "parameters": {"type": "object", "properties": {}},
                },
            })
    return schemas


def call_mcp_tool(mcp_full_name: str, arguments: dict) -> dict:
    """
    路由 MCP 工具调用到对应的连接

    Args:
        mcp_full_name: "mcp__{service_name}__{tool_name}" 格式
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    # 解析名称
    parts = mcp_full_name.split("__", 2)
    if len(parts) != 3:
        return {"status": "error", "error": f"无效的 MCP 工具名: {mcp_full_name}"}

    _, service_name, tool_name = parts
    conn = _modelscope_connections.get(service_name)
    if not conn:
        return {"status": "error", "error": f"MCP 服务 '{service_name}' 未连接"}

    # 自动重连：如果连接离线但有 SSE URL，尝试重新建立连接
    if not conn.is_connected and conn.sse_url:
        import logging
        logging.getLogger("mcp").info("MCP %s 离线，尝试自动重连...", service_name)
        try:
            from MCPS import connect_modelscope_mcp
            result = connect_modelscope_mcp(service_name, conn.label, conn.sse_url)
            if result.get("ok"):
                # 重新获取连接对象
                conn = _modelscope_connections.get(service_name)
            else:
                return {"status": "error", "error": f"MCP 服务 '{service_name}' 重连失败: {result.get('error', '')}"}
        except Exception as e:
            return {"status": "error", "error": f"MCP 服务 '{service_name}' 重连异常: {e}"}

    if not conn or not conn.is_connected:
        return {"status": "error", "error": f"MCP 服务 '{service_name}' 无法连接"}

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=loop.run_until_complete,
            args=(conn.call_tool(tool_name, arguments),),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=30)
        return {"status": "success", "result": f"MCP 工具 {tool_name} 已调用"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_modelscope_connections() -> List[Dict]:
    """列出所有已连接的魔搭 MCP 服务"""
    result = []
    for name, conn in _modelscope_connections.items():
        result.append({
            "name": name,
            "label": conn.label,
            "sse_url": conn.sse_url,
            "connected": conn.is_connected,
            "tools": conn.tools,
            "tool_count": len(conn.tools),
        })
    return result
