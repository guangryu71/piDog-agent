"""
MCP 服务器基类 —— JSON-RPC 2.0 over HTTP

提供统一的服务器启动/停止、工具注册、JSON-RPC 请求处理框架。
各具体 MCP 服务器（browser/blender）继承此类并注册自己的工具。
"""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Callable, Optional

_log = logging.getLogger("mcp_base")


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP -> JSON-RPC 请求处理器"""

    # 类级引用，由 server 实例设置
    server_instance: Optional['BaseMCPServer'] = None

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(-32700, "Parse error")
            return

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if not self.server_instance:
            self._send_error(-32000, "Server not initialized", req_id)
            return

        try:
            result = self.server_instance.handle_request(method, params)
            self._send_response(result, req_id)
        except Exception as e:
            _log.error("RPC error: %s", e)
            self._send_error(-32603, str(e), req_id)

    def do_GET(self):
        """健康检查"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        status = {
            "ok": True,
            "server": self.server_instance.server_name if self.server_instance else "unknown",
            "running": True,
        }
        self.wfile.write(json.dumps(status, ensure_ascii=False).encode())

    def _send_response(self, result: Any, req_id: Any = None):
        resp = {"jsonrpc": "2.0", "result": result, "id": req_id}
        body = json.dumps(resp, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str, req_id: Any = None):
        resp = {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id}
        body = json.dumps(resp, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        _log.debug("HTTP: %s", format % args)


class BaseMCPServer:
    """
    MCP 服务器基类

    子类重写 _register_tools() 来注册工具。
    启动后通过 HTTP JSON-RPC 2.0 协议提供服务。
    """

    def __init__(self, name: str = "mcp", port: int = 9100, host: str = "127.0.0.1"):
        self.server_name = name
        self.port = port
        self.host = host
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

        # 注册内置方法
        self._register_builtin_tools()
        # 子类注册自己的工具
        self._register_tools()

    # ---- 子类重写 ----

    def _register_tools(self):
        """子类在此注册工具"""
        pass

    def _register_builtin_tools(self):
        """注册内置工具（所有 MCP 共有）"""
        self.register_tool(
            name="ping",
            description="健康检查",
            handler=lambda params: {"pong": True, "server": self.server_name},
        )
        self.register_tool(
            name="list_tools",
            description="列出所有可用工具",
            handler=lambda params: {
                "tools": [
                    {"name": n, "description": t.get("description", "")}
                    for n, t in self._tools.items()
                ]
            },
        )

    # ---- 工具管理 ----

    def register_tool(self, name: str, description: str, handler: Callable, schema: dict = None):
        """注册一个工具"""
        self._tools[name] = {
            "name": name,
            "description": description,
            "handler": handler,
            "schema": schema or {},
        }

    # ---- 请求处理 ----

    def handle_request(self, method: str, params: dict) -> Any:
        """处理 JSON-RPC 请求"""
        if method not in self._tools:
            raise ValueError(f"Unknown method: {method}. Available: {list(self._tools.keys())}")

        handler = self._tools[method]["handler"]
        return handler(params)

    # ---- 生命周期 ----

    def run(self):
        """启动 HTTP 服务器（阻塞，应在独立线程中调用）"""
        MCPRequestHandler.server_instance = self

        self._httpd = HTTPServer((self.host, self.port), MCPRequestHandler)
        _log.info("[MCP] %s 服务器启动 at http://%s:%s", self.server_name, self.host, self.port)
        print(f"[MCP] {self.server_name} 服务器启动 → http://{self.host}:{self.port}")

        try:
            self._httpd.serve_forever()
        except Exception as e:
            _log.info("[MCP] %s 服务器停止: %s", self.server_name, e)

    def stop(self):
        """停止服务器"""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
            _log.info("[MCP] %s 服务器已停止", self.server_name)

    @property
    def is_running(self) -> bool:
        return self._httpd is not None
