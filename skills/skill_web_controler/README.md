# 浏览器自动化控制（QwenPaw 服务代理）

## 🎯 角色定义

本技能是 **QwenPaw 浏览器服务的代理层**，提供统一的工具接口 `execute_browser_command`。

**实现位置**: `skills/skill_web_controler/tools/qwenpaw_client.py`

### 核心定位

- **代理转发**：将用户的自然语言指令转发给外部的 QwenPaw 服务
- **QwenPaw 执行**：所有浏览器操作由 QwenPaw 服务完成并返回结果
- **整合架构**：所有功能已整合到单一文件 `qwenpaw_client.py`，简化维护

---

## 🔧 可用工具

### execute_browser_command

**功能**: 将自然语言指令转发给 QwenPaw 服务执行

**实现文件**: `skills/skill_web_controler/tools/qwenpaw_client.py`

**参数**:
- `command` (必填): 用户的自然语言指令，描述完整的浏览器操作流程
- `session_id` (可选): 会话ID，默认 "default"

**返回值**: `{"status": "success" | "error" | "pending_approval", "message": "...", "data": {...}}`

**工作原理**:
1. Agent 接收用户的浏览器操作需求
2. 通过 `execute_browser_command` 将指令发送给 QwenPaw
3. QwenPaw 解析指令并执行所有浏览器操作
4. 返回执行结果给 Agent（通常是文本内容）

**重要提示**:
- `command` 参数应该包含**完整的操作序列**，鼓励创造性表达
- QwenPaw 会智能解析指令并自动执行所有必要的步骤

---

## 📋 使用示例

```python
from skills.skill_web_controler.tools import execute_browser_command

# 访问网页并获取内容
result = execute_browser_command('访问权威网站，获取页面主要内容和关键信息')
print(result['message'])
```

---

## ⚙️ 技术实现

### 架构说明

```
Smart Agent → execute_browser_command → QwenPaw API → 浏览器操作 → 返回结果
```

### 整合架构（v2.0）

所有功能已整合到单一文件中：

- **qwenpaw_client.py**: 整合版本，包含：
  - `ConsoleLogger` - 彩色控制台日志输出
  - `QwenPawClient` - QwenPaw 客户端，管理服务连接和通信
  - `run()` - 统一入口函数（对外暴露为 `execute_browser_command`）
  - `PendingApproval` - 待审批异常类

### 配置要求

QwenPaw 服务必须配置大模型 Provider 才能工作：
- 推荐：通义千问（DashScope API Key）
- 其他：OpenAI、DeepSeek 等

详细配置方法请参考 QwenPaw 官方文档。

---

## 🚀 创意实验与突破

### 鼓励的创新实践
- **复杂数据提取**：从网页中提取结构化数据，进行分析和可视化
- **多步骤工作流**：结合多个网站的数据，创建综合报告
- **自动化监控**：定期检查网站内容变化，生成变化报告
- **智能搜索**：使用自然语言描述进行精准搜索，过滤无关结果
- **内容聚合**：从多个来源收集相关内容，创建个性化摘要

### 探索边界
- 尝试非传统的浏览器操作方式
- 实验性数据处理方法
- 创新的信息提取策略
- 突破传统搜索界限的查询方式

### 学习与改进
- 从每次搜索中学习更有效的查询策略
- 记录成功的数据提取模式
- 不断改进内容分析技术
- 探索新的信息聚合方式
