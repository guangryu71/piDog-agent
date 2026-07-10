"""
魔搭 OpenAPI 客户端 —— 调用魔搭官方 API 搜索/浏览 MCP 服务

魔搭 MCP 广场已开放 OpenAPI，支持：
  - 搜索 MCP 服务（按名称、作者）
  - 按分类/标签筛选
  - 筛选 Hosted（托管）类型
  - 获取服务详情（含 SSE URL）

API 文档：https://modelscope.cn/docs/openapi
OpenAPI 规范：https://modelscope.cn/.well-known/openapi.json
"""

import json
import logging
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

_log = logging.getLogger("modelscope_api")

# 魔搭 OpenAPI 基础地址
MODELSCOPE_API_BASE = "https://modelscope.cn/openapi/v1"

# 热门 MCP 默认分类（用作热门标签）
HOT_CATEGORIES = [
    "browser-automation",
    "web-scraping",
    "search",
    "developer-tools",
    "image-generation",
    "data-analysis",
    "communication",
    "maps-geography",
]


class ModelScopeAPIClient:
    """
    魔搭 OpenAPI 客户端

    调用魔搭官方 API 搜索、浏览、获取 MCP 服务详情。
    需要用户提供魔搭 API Token（从 modelscope.cn 获取）。
    """

    _cache: Dict[str, dict] = {}  # 类级缓存，避免重复请求
    _cache_time: Dict[str, float] = {}

    def __init__(self, token: str = ""):
        self.token = token

    def _cached_request(self, method: str, path: str, body: dict = None, ttl: int = 5) -> dict:
        """带缓存的请求，避免重复调用魔搭 API 被限流"""
        import time
        cache_key = f"{method}:{path}:{json.dumps(body or {}, sort_keys=True)}"
        now = time.time()
        if cache_key in self._cache and now - self._cache_time.get(cache_key, 0) < ttl:
            return self._cache[cache_key]
        result = self._request(method, path, body)
        if result.get("success", True):  # 成功结果才缓存
            self._cache[cache_key] = result
            self._cache_time[cache_key] = now
        return result

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PiDog-SmartAgent/2.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, body: dict = None) -> dict:
        """发送 HTTP 请求到魔搭 OpenAPI"""
        url = f"{MODELSCOPE_API_BASE}{path}"
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            # 尝试读取响应体中的详细错误信息
            detail = str(e)
            if hasattr(e, 'read'):
                try:
                    body = e.read().decode()
                    if body:
                        detail = body[:500]
                except Exception:
                    pass
            _log.warning("魔搭 API 请求失败: %s - %s", url, detail)
            return {"success": False, "message": detail, "http_code": getattr(e, 'code', 0)}
        except Exception as e:
            _log.warning("魔搭 API 异常: %s", e)
            return {"success": False, "message": str(e)}

    # ==================== MCP 服务搜索 ====================

    def search_mcp_servers(
        self,
        search: str = "",
        category: str = "",
        is_hosted: bool = True,
        page_number: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        搜索 MCP 服务

        Args:
            search: 搜索关键字（匹配中文名、英文名、作者）
            category: 分类筛选（如 browser-automation, search 等）
            is_hosted: 是否只返回托管服务
            page_number: 页码（page_number * page_size <= 100）
            page_size: 每页数量

        Returns:
            {"success": bool, "data": {"mcp_server_list": [...], "total_count": N}, "message": "..."}
        """
        body = {
            "page_number": page_number,
            "page_size": page_size,
        }
        if search.strip():
            body["search"] = search.strip()
        filter_obj = {}
        if category:
            filter_obj["category"] = category
        if is_hosted is not None:
            filter_obj["is_hosted"] = is_hosted
        if filter_obj:
            body["filter"] = filter_obj

        # 使用缓存版本，TTL 5 秒，避免频繁请求被限流
        return self._cached_request("PUT", "/mcp/servers", body, ttl=5)

    def get_mcp_detail(self, server_id: str, get_operational_url: bool = False) -> dict:
        """
        获取 MCP 服务详情

        Args:
            server_id: MCP 服务 ID（如 "@modelcontextprotocol/fetch"）
            get_operational_url: 是否返回 SSE URL（需要用户已连接该服务）

        Returns:
            MCP 服务详细信息（McpServerDetail）
        """
        path = f"/mcp/servers/{server_id}"
        if get_operational_url:
            path += "?get_operational_url=true"
        return self._request("GET", path)

    def get_operational_servers(self) -> dict:
        """
        获取当前用户已托管的 MCP 服务列表

        Returns:
            用户已连接的 MCP 服务列表
        """
        return self._request("GET", "/mcp/servers/operational")

    # ==================== 部署/连接 MCP ====================

    def deploy_mcp(
        self,
        server_id: str,
        transport_type: str = "streamable_http",
        expiration_minutes: int = -1,
        auth_check: bool = False,
        env_info: dict = None,
    ) -> dict:
        """
        部署/连接 MCP 服务 —— 直接生成 SSE URL，无需前往魔搭网站

        Args:
            server_id: MCP 服务 ID（如 "@modelcontextprotocol/fetch"）
            transport_type: "sse" 或 "streamable_http"
            expiration_minutes: 有效期分钟数，-1 长期有效
            auth_check: 是否需要 Token 鉴权
            env_info: 环境变量（如 API Key 等），从详情接口 env_schema 获取

        Returns:
            {"success": true, "data": {"url": "SSE_URL", "id": "...", "expiration": "...", ...}}
            成功后 SSE URL 在 data.url 中
        """
        body = {
            "transport_type": transport_type,
            "expiration_minutes": expiration_minutes,
            "auth_check": auth_check,
        }
        if env_info:
            body["env_info"] = env_info

        return self._request("POST", f"/mcp/servers/{server_id}/deploy", body)

    def undeploy_mcp(self, server_id: str) -> dict:
        """解除部署/断开 MCP 服务"""
        return self._request("DELETE", f"/mcp/servers/{server_id}/undeploy")

    # ==================== 辅助方法 ====================

    def format_server_list(self, raw: dict) -> dict:
        """
        将 API 原始响应格式化为前端友好格式

        Returns:
            {"success": true/false, "total": N, "servers": [{id, name, description, categories, tags, ...}]}
        """
        if not raw.get("success"):
            return {"success": False, "message": raw.get("message", "请求失败"), "servers": [], "total": 0}

        data = raw.get("data", {})
        servers = data.get("mcp_server_list", [])
        total = data.get("total_count", 0)

        formatted = []
        for s in servers:
            locales = s.get("locales", {})
            zh_locale = locales.get("zh", {}) if locales else {}

            formatted.append({
                "id": s.get("id", ""),
                "name": zh_locale.get("name", s.get("name", "")),
                "raw_name": s.get("name", ""),
                "description": zh_locale.get("description", s.get("description", "")),
                "categories": s.get("categories", []),
                "tags": s.get("tags", []),
                "publisher": s.get("publisher", ""),
                "view_count": s.get("view_count", 0),
                "logo_url": s.get("logo_url", ""),
                "is_hosted": s.get("is_hosted", False),
                "is_verified": s.get("is_verified", False),
                "github_stars": s.get("github_stars", 0),
            })

        return {
            "success": True,
            "total": total,
            "servers": formatted,
        }


# ---- 全局单例 ----
_global_api_client = None


def get_api_client(token: str = "") -> ModelScopeAPIClient:
    """获取魔搭 API 客户端"""
    global _global_api_client
    if _global_api_client is None:
        _global_api_client = ModelScopeAPIClient(token)
    elif token:
        _global_api_client.token = token
    return _global_api_client


def search_mcp(search: str = "", category: str = "", page: int = 1, page_size: int = 20, token: str = "") -> dict:
    """快捷搜索 MCP 服务"""
    client = get_api_client(token)
    raw = client.search_mcp_servers(
        search=search,
        category=category,
        is_hosted=True,
        page_number=page,
        page_size=page_size,
    )
    return client.format_server_list(raw)


def deploy_mcp(server_id: str, token: str = "", env_info: dict = None) -> dict:
    """
    一键部署/连接 MCP 服务 —— 直接生成 SSE URL

    成功后返回 SSE URL，可直接用于连接。无需手动前往魔搭网站。

    Args:
        server_id: MCP 服务 ID（如 "@modelcontextprotocol/fetch"）
        token: 魔搭 API Token
        env_info: 环境变量（如 API Key），可选

    Returns:
        {"success": true, "data": {"url": "SSE_URL", ...}}
    """
    client = get_api_client(token)
    return client.deploy_mcp(server_id, env_info=env_info)


def undeploy_mcp(server_id: str, token: str = "") -> dict:
    """断开 MCP 服务部署"""
    client = get_api_client(token)
    return client.undeploy_mcp(server_id)


def list_categories() -> list:
    """返回可用的 MCP 分类列表（用于前端标签）"""
    return HOT_CATEGORIES
