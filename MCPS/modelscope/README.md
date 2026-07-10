# 魔搭 MCP 广场连接器

通过 SSE 协议连接魔搭社区 9,200+ 托管 MCP 服务，自动发现工具并暴露给 Agent。

## 快速开始

### 1. 获取 SSE URL

1. 访问 [魔搭 MCP 广场](https://www.modelscope.cn/mcp?hosted=1)
2. 筛选 **Hosted** 类型的 MCP 服务
3. 点击服务 → 「连接」→ 复制 SSE URL

### 2. 连接 MCP 服务

通过前端 MCP 管理页面：
1. 进入 MCP 页面
2. 在「魔搭 MCP 广场」卡片中点击「添加连接」
3. 填入名称和 SSE URL
4. 连接成功后自动显示可用工具

### 3. 代码示例

```python
from MCPS.modelscope import ModelScopeConnector

connector = ModelScopeConnector()

# 连接魔搭 MCP 服务
result = connector.connect("fetch", "Fetch 网页抓取", 
    "https://mcp.api-inference.modelscope.net/xxx/sse")
print(result)

# 列出工具
tools = connector.list_tools("fetch")
for t in tools:
    print(f"  {t['name']}: {t['description']}")

# 调用工具
result = connector.call_tool("fetch", "fetch_url", 
    {"url": "https://example.com"})
print(result)

# 断开连接
connector.disconnect("fetch")
```

## 支持的传输协议

| 协议 | 支持 | 说明 |
|------|------|------|
| **SSE** (Server-Sent Events) | ✅ | 魔搭托管 MCP 标准协议 |
| **stdio** | ⚠️ | 本地部署模式（开发中） |

## 数据流

```
Agent → MCP 管理器 → ModelScopeConnector
                         ↓
                  SSE Client (mcp Python SDK)
                         ↓
              魔搭 MCP 广场托管服务
                         ↓
                  实际工具执行
```
