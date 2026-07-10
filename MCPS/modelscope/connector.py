"""
魔搭 MCP 广场连接器

通过 SSE（Server-Sent Events）协议连接到魔搭社区托管的 MCP 服务。
支持多连接管理、工具发现、工具调用。

魔搭 SSE URL 格式：
  https://mcp.api-inference.modelscope.net/{service-id}/sse

使用示例：
  connector = ModelScopeConnector()
  await connector.connect("fetch", "https://mcp.api-inference.modelscope.net/xxx/sse")
  tools = await connector.list_tools("fetch")
  result = await connector.call_tool("fetch", "fetch_url", {"url": "https://example.com"})
  await connector.disconnect("fetch")
"""

import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional

_log = logging.getLogger("modelscope_mcp")


class ModelScopeMCPConnection:
    """
    单个魔搭 MCP 服务的连接封装

    管理一个 SSE 连接的完整生命周期：
    - 建立连接 → 握手初始化 → 工具发现 → 工具调用 → 断开
    """

    def __init__(self, name: str, label: str, sse_url: str, token: str = ""):
        self.name = name                # 唯一标识符
        self.label = label              # 显示名称
        self.sse_url = sse_url          # SSE 端点 URL
        self.token = token              # 魔搭 API Token（可选）
        self._session = None            # MCP ClientSession
        self._streams = None            # SSE 流引用
        self._tools: List[Dict] = []    # 缓存已发现的工具
        self._loop = None               # 所属事件循环
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session is not None

    @property
    def tools(self) -> List[Dict]:
        return self._tools

    async def connect(self):
        """建立 SSE 连接并进行 MCP 握手"""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            _log.info("[MCP] 连接魔搭: %s (%s)", self.label, self.sse_url)

            # sse_client 返回 _AsyncGeneratorContextManager，必须用 __aenter__
            self._stream_cm = sse_client(url=self.sse_url, headers=headers)
            streams = await self._stream_cm.__aenter__()
            read, write = streams

            self._session_cm = ClientSession(read, write)
            self._session = await self._session_cm.__aenter__()
            await self._session.initialize()

            # 自动发现工具
            tools_result = await self._session.list_tools()
            self._tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in tools_result.tools
            ]

            self._connected = True
            _log.info("[MCP] 连接成功: %s → %d 个工具", self.label, len(self._tools))
            return {"ok": True, "name": self.name, "tools": len(self._tools)}

        except Exception as e:
            self._connected = False
            _log.error("[MCP] 连接失败: %s - %s", self.label, e)
            return {"ok": False, "error": str(e)}

    async def list_tools(self) -> List[Dict]:
        """重新发现工具（优先使用缓存）"""
        if not self._connected or not self._session:
            return []
        if self._tools:
            return self._tools
        try:
            tools_result = await self._session.list_tools()
            self._tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in tools_result.tools
            ]
            return self._tools
        except Exception as e:
            _log.warning("[MCP] 工具发现失败: %s", e)
            return self._tools

    async def call_tool(self, tool_name: str, arguments: dict = None) -> Dict:
        """调用 MCP 工具"""
        if not self._connected or not self._session:
            return {"status": "error", "error": "MCP 未连接"}
        try:
            result = await self._session.call_tool(tool_name, arguments or {})
            # 统一返回格式
            if hasattr(result, "content") and result.content:
                texts = []
                for c in result.content:
                    if hasattr(c, "text") and c.text:
                        texts.append(c.text)
                return {"status": "success", "result": "\n".join(texts)}
            return {"status": "success", "result": str(result)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def disconnect(self):
        """断开 MCP 连接"""
        self._connected = False
        try:
            if self._session and hasattr(self, '_session_cm') and self._session_cm:
                await self._session_cm.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if hasattr(self, '_stream_cm') and self._stream_cm:
                await self._stream_cm.__aexit__(None, None, None)
        except Exception:
            pass
        self._session = None
        self._session_cm = None
        self._stream_cm = None
        self._tools = []
        _log.info("[MCP] 已断开: %s", self.label)


class ModelScopeConnector:
    """
    魔搭 MCP 连接器（管理多个 MCP 连接）

    管理所有到魔搭 MCP 广场的 SSE 连接，
    提供统一的连接/断开/工具发现/工具调用接口。
    """

    def __init__(self):
        self._connections: Dict[str, ModelScopeMCPConnection] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """获取或创建事件循环（线程安全）"""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run_async(self, coro):
        """在合适的线程中运行异步协程"""
        loop = self._get_or_create_loop()
        if loop.is_running():
            # 已在事件循环中 → 直接用
            import asyncio as _asyncio
            fut = _asyncio.run_coroutine_threadsafe(coro, loop)
            return fut.result(timeout=30)
        else:
            return loop.run_until_complete(coro)

    # ---- 连接管理 ----

    def connect(self, name: str, label: str, sse_url: str, token: str = "") -> dict:
        """建立到魔搭 MCP 服务的连接"""
        if name in self._connections:
            if self._connections[name].is_connected:
                return {"ok": False, "error": f"MCP '{name}' 已连接"}

        conn = ModelScopeMCPConnection(name, label, sse_url, token)
        result = self._run_async(conn.connect())
        if result.get("ok"):
            self._connections[name] = conn
        return result

    def disconnect(self, name: str) -> dict:
        """断开 MCP 连接"""
        if name not in self._connections:
            return {"ok": False, "error": f"MCP '{name}' 未连接"}
        conn = self._connections.pop(name)
        self._run_async(conn.disconnect())
        return {"ok": True, "name": name, "status": "disconnected"}

    def list_connections(self) -> List[Dict]:
        """列出所有已连接的魔搭 MCP 服务"""
        result = []
        for name, conn in self._connections.items():
            result.append({
                "name": name,
                "label": conn.label,
                "sse_url": conn.sse_url,
                "connected": conn.is_connected,
                "tools": conn.tools,
            })
        return result

    def get_connection(self, name: str) -> Optional[ModelScopeMCPConnection]:
        """获取指定连接"""
        return self._connections.get(name)

    # ---- 工具操作 ----

    def list_tools(self, name: str) -> List[Dict]:
        """列出某个 MCP 服务的工具"""
        conn = self._connections.get(name)
        if not conn or not conn.is_connected:
            return []
        return self._run_async(conn.list_tools())

    def call_tool(self, name: str, tool_name: str, arguments: dict = None) -> dict:
        """调用某个 MCP 服务的工具"""
        conn = self._connections.get(name)
        if not conn:
            return {"status": "error", "error": f"MCP '{name}' 未连接"}
        return self._run_async(conn.call_tool(tool_name, arguments or {}))

    # ---- 批量管理 ----

    def disconnect_all(self):
        """断开所有连接"""
        for name in list(self._connections.keys()):
            self.disconnect(name)

    @property
    def total_connections(self) -> int:
        return len(self._connections)

    @property
    def total_tools(self) -> int:
        return sum(len(c.tools) for c in self._connections.values())


# ---- 全局单例 ----
_global_connector = None


def get_connector() -> ModelScopeConnector:
    """获取全局魔搭 MCP 连接器单例"""
    global _global_connector
    if _global_connector is None:
        _global_connector = ModelScopeConnector()
    return _global_connector
