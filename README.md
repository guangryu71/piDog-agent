# SmartAgent V2 —— 通用电脑智能体

一个由大模型驱动的通用电脑智能体。用户用自然语言下达指令后，Agent 自主理解意图、制定计划并调用工具，在你的电脑上完成真实操作——文件编辑、命令执行、图像处理、浏览器自动化、3D 建模以及远程 MCP 服务调用。

Agent 运行在**原生 Function Calling** 循环之上（取代早期"正则解析裸 JSON"的方案），配套 FastAPI 后端、Web 界面、会话记忆、Token 成本统计与任务编排能力。

---

## 核心特性

- **原生 Function Calling** —— 工具的 JSON Schema 通过 `tools` 参数直接传给模型，模型输出结构化 `tool_calls`，经参数校验后由注册表分发执行，无需脆弱的正则解析。
- **技能化工具注册表** —— 工具按技能声明，启动时自动扫描构建映射，新增技能只需建目录 + 注册一条定义。
- **两阶段工具选择** —— 先让模型选出所需**技能**，再只注入这些技能的工具 Schema，显著降低 Token 消耗。
- **SSE 流式对话** —— 工具名与参数逐 token 推送，前端渐进渲染工具调用卡片，任务支持中途取消。
- **MCP 集成** —— 内置本地 MCP 服务器（Playwright、Blender），并可通过 SSE 接入魔搭 MCP 广场 9200+ 托管服务，支持工具自动发现、离线缓存与失败自动重连。
- **多提供商 / 多模态** —— 统一封装 DeepSeek、硅基流动、阿里百炼，运行时可热切换；覆盖文本、视觉、文生图、OCR。
- **安全与稳定** —— 危险工具（`execute_command`、`delete_file`）需人工审批；连续失败熔断与同工具重试拦截防止模型空转死循环。
- **成本可核算** —— 每次 API 调用的 Token 消耗均记录在案，按提供商 / 模型 / 时间维度统计。

---

## 架构

```
用户输入
    │
    ▼
大模型（携带 `tools` Schema） ──►  结构化 tool_calls
    ▲                                 │
    │                                 ▼
    └── 工具结果 ◄── Schema 参数校验 ──► 注册表分发 ──► 工具执行
                                                       │
                                          直至调用 `finish_task` 结束
```


| 层       | 技术                                                |
| -------- | --------------------------------------------------- |
| 后端     | Python + FastAPI（REST + SSE）                      |
| 推理     | OpenAI 兼容 SDK，原生 Function Calling              |
| 前端     | 原生 HTML / CSS / JavaScript                        |
| 工具     | 技能注册表 + JSON Schema 声明                       |
| MCP      | 本地服务器（Playwright / Blender）+ 魔搭广场（SSE） |
| 外部能力 | Playwright、Blender(bpy)、图像处理、OCR             |

---

## 目录结构

```
smart_agent_new/
├── agent_v2.py                  # CLI 版 Agent 循环（Function Calling）
├── confing.json                 # 主配置（模型、路径、Token）
├── models/llm/llm_chat.py       # LLM 封装（对话 / 工具 / 流式 / 记忆）
├── utils/
│   ├── tool_registry.py         # 技能注册表 + 工具 Schema
│   ├── function_calling_executor.py  # 将 tool_calls 分发到具体实现
│   └── ...                      # 文件 / 命令 / 浏览器 / Blender 控制器
├── skills/                      # 技能实现（一技能一目录）
├── agents/                      # 提示词 Agent（thinker、workflower 等）
├── MCPS/                        # MCP 服务器 + 魔搭广场连接器
│   ├── base_server.py           # JSON-RPC 2.0 over HTTP 基类
│   ├── browser/                 # Playwright MCP 服务器
│   ├── blender/                 # Blender (bpy) MCP 服务器
│   └── modelscope/              # 魔搭广场 SSE 连接器
└── PiDog/
    ├── backend/
    │   ├── app.py               # FastAPI 入口
    │   ├── config.py            # 提供商预设 + 运行时状态
    │   ├── routers/             # chat / model / tool / skill / token / mcp / task / workflower
    │   └── services/            # 各路由的业务逻辑
    ├── frontend/                # Web 界面（index.html、css、js）
    └── workflower/              # 已保存的工作流资产
```

---

## 安装

1. **克隆仓库**

   ```bash
   git clone <repo-url>
   cd smart_agent_new
   ```
2. **安装依赖**

   ```bash
   pip install -r PiDog/backend/requirements.txt
   ```

   核心依赖：

   ```
   fastapi>=0.104.0
   uvicorn[standard]>=0.24.0
   openai>=1.6.0
   pydantic>=2.5.0
   sse-starlette>=1.8.0
   python-multipart>=0.0.6
   ```
3. **可选依赖**（仅对应技能需要）

   ```bash
   pip install playwright && playwright install   # 浏览器自动化
   pip install mcp                                # 魔搭 MCP 广场连接器
   ```

   Blender 技能需本机安装 Blender 并开启 MCP 插件（默认 `localhost:9876`）。

---

## 配置

编辑项目根目录的 `confing.json`：

```jsonc
{
  "skills_directory": "skills",
  "working_directory": "path/to/workspace",   // 所有工具输出默认落在此目录
  "model_config": {
    "provider": "deepseek",                   // deepseek | siliconflow | bailian
    "model": "deepseek-v4-flash",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-..."
  },
  "modelscope_config": { "token": "ms-..." }, // 魔搭 MCP 广场
  "ocr_config":        { "api_key": "sk-..." } // DeepSeek-OCR
}
```

`working_directory` 是 Agent 创建与编辑文件的沙箱目录，同时通过 `/files` 静态服务暴露，便于前端展示生成的图片。

---

## 使用

### 启动后端

```bash
cd PiDog/backend
uvicorn app:app --host 0.0.0.0 --port 8765 --reload
```


| 地址                           | 说明                       |
| ------------------------------ | -------------------------- |
| `http://localhost:8765/ui`     | Web 界面                   |
| `http://localhost:8765/docs`   | 交互式 API 文档（Swagger） |
| `http://localhost:8765/health` | 健康检查                   |

Windows 下也可直接使用 `PiDog/backend/start.bat`（使用前请先修改其中的路径）。

### 命令行模式

```bash
python agent_v2.py                          # 交互式
python agent_v2.py "帮我搭建一个 Flask 项目"   # 单次任务
```

### 示例指令

```
帮我总结这个表格，并画出图表
在工作目录里搭一个 Flask 待办应用并跑起来
打开 example.com 截图，告诉我头条是什么
生成一张赛博朋克风格的城市图片
用 Blender 建一个低多边形椅子
```

---

## 技能与工具


| 技能                      | 工具                                                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `files_controler`         | `write_file`、`read_file`、`read_file_lines`、`replace_content`、`list_directory`、`get_file_info`、`delete_file_lines`、`create_directory` |
| `shell_controler`         | `execute_command`、`validate_python_syntax`、`validate_multiple_python_files`                                                               |
| `file_controler`          | `delete_file`（需人工审批）                                                                                                                 |
| `skill_img_handler`       | `process_image` —— `recognize`、`generate`、`img2img`、`edit`、`ocr`、`convert`、`resize`、`remove_bg`、`enhance`、`analyze`              |
| `skill_web_controler`     | `browser_use` —— start、open、snapshot、click、type、screenshot、eval、pdf、tabs 等                                                       |
| `skill_blender_controler` | `blender_operation` —— 执行 bpy 代码进行 3D 建模                                                                                          |
| *（内置）*                | `finish_task` —— 结束任务并返回面向用户的回复                                                                                             |

**新增技能：** 创建 `skills/<技能名>/README.md`（描述会被自动扫描），并在 `utils/tool_registry.py` 的 `SKILL_REGISTRY` 中添加 `schema / module / function` 定义即可。

---

## MCP 支持

- **本地 MCP 服务器** —— `browser` 与 `blender` 以 JSON-RPC 2.0 over HTTP 形式提供，支持启动 / 停止 / 启用 / 禁用，由注册表统一管理。
- **魔搭 MCP 广场** —— 通过 SSE 连接托管 MCP 服务，连接后自动发现工具并以 `mcp__<服务>__<工具>` 格式注入 LLM；调用时路由到对应连接，支持离线缓存与自动重连。

---

## API 一览


| 路由                                        | 说明                     |
| ------------------------------------------- | ------------------------ |
| `POST /api/chat` · `POST /api/chat/stream` | 同步 / 流式对话          |
| `POST /api/chat/cancel/{session_id}`        | 取消运行中的任务         |
| `POST /api/chat/upload`                     | 上传文件供下一条消息使用 |
| `GET/DELETE /api/chat/sessions`             | 列出 / 删除会话          |
| `POST /api/chat/sessions/{id}/compact`      | 压缩会话历史             |
| `POST /api/model/switch`                    | 热切换提供商 / 模型      |
| `GET /api/tools` · `GET /api/skills`       | 查看工具与技能           |
| `GET /api/tokens/stats`                     | Token 消耗统计           |
| `GET /api/mcp` · `POST /api/mcp/operate`   | 管理 MCP 服务器          |
| `GET/POST /api/tasks`                       | 任务 CRUD 与执行         |
| `GET/POST /api/workflower`                  | 工作流资产持久化         |

完整接口见 `/docs`。

---

## 许可证

本项目用于学习与个人用途。第三方组件（Playwright、Blender、魔搭及各家模型 API）遵循其各自的开源许可与服务条款。
