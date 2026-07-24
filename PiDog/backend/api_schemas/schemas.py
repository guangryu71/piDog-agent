"""
Pydantic 数据模型 —— API 请求/响应
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ==================== 对话 ====================

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，不传则新建")
    stream: bool = Field(False, description="是否流式返回")
    file_id: Optional[str] = Field(None, description="上传文件的ID（通过 /api/chat/upload 获得），兼容单文件")
    file_ids: Optional[List[str]] = Field(None, description="多个上传文件 ID 列表，同时上传图片和文件时使用")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_calls: List[str] = Field(default_factory=list, description="本轮调用的工具名称列表")


# ==================== 模型 ====================

class ModelSwitchRequest(BaseModel):
    provider: str = Field(..., description="提供商 key: deepseek / siliconflow / bailian")
    model: Optional[str] = Field(None, description="模型名称，不传则用该提供商默认模型")
    api_key: Optional[str] = Field(None, description="自定义 API Key")


class ProviderInfo(BaseModel):
    key: str
    name: str
    base_url: str
    models: List[str]
    default_model: str
    has_key: bool  # 是否已配置 key


class ModelStatus(BaseModel):
    current_provider: str
    current_model: str
    capabilities: dict = Field(default_factory=dict)
    has_global_key: bool = False
    has_ocr_key: bool = False
    providers: List[ProviderInfo]


class OcrApiKeyRequest(BaseModel):
    api_key: str = Field(..., description="DeepSeek-OCR API Key")


# ==================== 工具 ====================

class ToolInfo(BaseModel):
    name: str
    description: str
    module: str
    function_name: str


# ==================== Skill ====================

class SkillInfo(BaseModel):
    key: str
    description: str
    enabled: bool
    path: str


class SkillUpdate(BaseModel):
    description: Optional[str] = None
    enabled: Optional[bool] = None


class SkillCreate(BaseModel):
    key: str = Field(..., description="Skill 标识符")
    description: str = Field(..., description="Skill 描述")


# ==================== Token ====================

class TokenUsage(BaseModel):
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: str


class TokenStats(BaseModel):
    total_prompt: int = 0
    total_completion: int = 0
    total_all: int = 0
    calls: int = 0
    by_provider: Dict[str, int] = Field(default_factory=dict)
    by_model: Dict[str, int] = Field(default_factory=dict)
    recent: List[TokenUsage] = Field(default_factory=list)


# ==================== 审批 ====================

# ==================== 自定义任务 ====================

class TaskSchema(BaseModel):
    """任务数据模型（持久化结构）"""
    id: str = Field(..., description="任务唯一ID")
    title: str = Field(..., description="任务标题（仅展示用，不参与对话）")
    agent_prompt: str = Field(..., description="Agent 提示词定义")
    init_message: str = Field("", description="初始对话内容")
    selected_skills: List[str] = Field(default_factory=list, description="选中的技能名列表，空=全选")
    selected_mcp: List[str] = Field(default_factory=list, description="选中的 MCP 名列表，空=全选")
    selected_tools: List[str] = Field(default_factory=list, description="选中的工具名列表，空=全选")
    selected_files: List[str] = Field(default_factory=list, description="关联文件路径列表")
    created_at: str = Field("", description="创建时间")
    updated_at: str = Field("", description="更新时间")


class TaskCreate(BaseModel):
    """创建任务请求"""
    title: str = Field(..., description="任务标题")
    agent_prompt: str = Field(..., description="Agent 提示词")
    init_message: str = Field("", description="初始对话内容")
    selected_skills: List[str] = Field(default_factory=list)
    selected_mcp: List[str] = Field(default_factory=list)
    selected_tools: List[str] = Field(default_factory=list)
    selected_files: List[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    """更新任务请求"""
    title: Optional[str] = None
    agent_prompt: Optional[str] = None
    init_message: Optional[str] = None
    selected_skills: Optional[List[str]] = None
    selected_mcp: Optional[List[str]] = None
    selected_tools: Optional[List[str]] = None
    selected_files: Optional[List[str]] = None


class TaskRunRequest(BaseModel):
    """运行任务请求"""
    task_id: str = Field(..., description="要运行的任务ID")


class TaskRunResponse(BaseModel):
    """运行任务响应"""
    session_id: str = Field(..., description="新建的会话ID")
    task_id: str = Field(..., description="任务ID")


# ==================== 审批 ====================

class ApprovalRequest(BaseModel):
    task_id: str = Field(..., description="审批任务ID")
    approved: bool = Field(..., description="true=批准, false=拒绝")


# ==================== MCP ====================

class MCPInfo(BaseModel):
    key: str
    name: str
    description: str
    enabled: bool
    running: bool
    port: int
    auto_start: bool
    type: str = "local"
    connected_count: Optional[int] = Field(None, description="hub 类型已连接数")
    total_tools: Optional[int] = Field(None, description="hub 类型总工具数")
    ms_name: Optional[str] = Field(None, description="魔搭连接标识")
    tool_count: Optional[int] = Field(None, description="魔搭连接工具数")


class MCPSwitchRequest(BaseModel):
    key: str = Field(..., description="MCP 标识符")
    action: str = Field(..., description="操作: start/stop/enable/disable/auto_start")
    value: Optional[bool] = Field(None, description="enable/auto_start 时的布尔值")
