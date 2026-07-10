"""
MCPS/modelscope — 魔搭 MCP 广场连接器

通过 SSE 协议连接到魔搭社区托管的 MCP 服务，自动发现工具并暴露给 Agent。
通过 OpenAPI 搜索/浏览魔搭 MCP 广场的 9,200+ 个托管 MCP 服务。

使用流程：
  1. 在魔搭获取 SSE URL（https://www.modelscope.cn/mcp）
  2. 调用 connect() 建立 SSE 连接
  3. 自动发现该 MCP 服务的所有工具
  4. 通过 call_tool() 调用工具
  5. disconnect() 断开连接

搜索 MCP 服务：
  from MCPS.modelscope.api_client import search_mcp
  result = search_mcp(search="fetch", category="web-scraping")

依赖：pip install mcp
"""

from .connector import ModelScopeConnector, ModelScopeMCPConnection
from .api_client import ModelScopeAPIClient, search_mcp, list_categories, get_api_client, deploy_mcp, undeploy_mcp

__all__ = [
    "ModelScopeConnector", "ModelScopeMCPConnection",
    "ModelScopeAPIClient", "search_mcp", "list_categories", "get_api_client",
    "deploy_mcp", "undeploy_mcp",
]
