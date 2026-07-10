"""
Browser MCP 服务器 —— 基于 Playwright 的浏览器自动化

注册工具：
  - browser_open: 打开网页
  - browser_snapshot: 获取页面快照（含元素引用）
  - browser_click: 点击元素
  - browser_type: 输入文本
  - browser_screenshot: 截图
  - browser_eval: 执行 JavaScript
  - browser_close: 关闭页面/浏览器

启动：python -m MCPS.browser.mcp_server [--port 9100]
"""

import sys
import os

# 确保项目根目录在 path 中
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from MCPS.base_server import BaseMCPServer
from utils.web_controler.browser_engine import browser_use


class BrowserMCPServer(BaseMCPServer):
    """浏览器自动化 MCP 服务器"""

    def __init__(self, port: int = 9100):
        super().__init__(name="browser", port=port)

    def _register_tools(self):
        self.register_tool(
            name="browser_open",
            description="打开网页",
            handler=lambda params: browser_use("open", url=params.get("url", "")),
        )
        self.register_tool(
            name="browser_snapshot",
            description="获取页面快照（含交互元素引用 ref）",
            handler=lambda params: browser_use("snapshot"),
        )
        self.register_tool(
            name="browser_click",
            description="点击页面元素（通过 ref 或 CSS selector）",
            handler=lambda params: browser_use(
                "click",
                ref=params.get("ref"),
                selector=params.get("selector"),
            ),
        )
        self.register_tool(
            name="browser_type",
            description="在输入框中输入文本",
            handler=lambda params: browser_use(
                "type",
                ref=params.get("ref"),
                text=params.get("text", ""),
                submit=params.get("submit", False),
                slowly=params.get("slowly", False),
            ),
        )
        self.register_tool(
            name="browser_screenshot",
            description="截图保存",
            handler=lambda params: browser_use(
                "screenshot",
                path=params.get("path"),
                full_page=params.get("full_page", False),
            ),
        )
        self.register_tool(
            name="browser_eval",
            description="在页面中执行 JavaScript",
            handler=lambda params: browser_use("eval", code=params.get("code", "")),
        )
        self.register_tool(
            name="browser_close",
            description="关闭浏览器",
            handler=lambda params: browser_use("close"),
        )


# ---- CLI 入口 ----
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Browser MCP Server")
    parser.add_argument("--port", type=int, default=9100, help="监听端口")
    args = parser.parse_args()

    server = BrowserMCPServer(port=args.port)
    print(f"启动 Browser MCP 服务器 (端口 {args.port})...")
    server.run()
