# Blender MCP 服务器

通过 bpy Python 代码控制 Blender 进行 3D 建模，通过 JSON-RPC 2.0 协议提供服务。

## 启动方式

```bash
# 默认端口 9101
python -m MCPS.blender.mcp_server

# 指定端口
python -m MCPS.blender.mcp_server --port 9101
```

## 注册的工具

| 工具名 | 功能 |
|--------|------|
| `blender_execute` | 执行 bpy 代码进行 3D 建模 |
| `blender_scene_info` | 获取当前场景信息 |
| `blender_clear_scene` | 清空场景 |

## 使用示例

```python
import requests
rpc = "http://127.0.0.1:9101"

# 创建一个立方体
requests.post(rpc, json={
    "method": "blender_execute",
    "params": {"code": "import bpy; bpy.ops.mesh.primitive_cube_add()"}
}).json()

# 获取场景信息
requests.post(rpc, json={"method": "blender_scene_info"}).json()
```

## 前置条件

- Blender 已安装并运行
- Blender MCP 插件已开启（默认 localhost:9876）
