# Browser MCP 服务器

基于 Playwright 的浏览器自动化控制，通过 JSON-RPC 2.0 协议提供服务。

## 启动方式

```bash
# 默认端口 9100
python -m MCPS.browser.mcp_server

# 指定端口
python -m MCPS.browser.mcp_server --port 9100
```

## 注册的工具

| 工具名 | 功能 |
|--------|------|
| `browser_open` | 打开网页 |
| `browser_snapshot` | 获取页面快照（带元素 ref） |
| `browser_click` | 点击元素 |
| `browser_type` | 输入文本 |
| `browser_screenshot` | 截图保存 |
| `browser_eval` | 执行 JavaScript |
| `browser_close` | 关闭浏览器 |

## 使用示例

```python
import requests
rpc = "http://127.0.0.1:9100"

# 打开网页
requests.post(rpc, json={"method": "browser_open", "params": {"url": "https://example.com"}}).json()

# 截图
requests.post(rpc, json={"method": "browser_screenshot", "params": {"path": "./screenshot.png"}}).json()
```
