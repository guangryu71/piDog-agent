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
    file_id: Optional[str] = Field(None, description="上传文件的ID（通过 /api/chat/upload 获得）")


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
    providers: List[ProviderInfo]


# ==================== 图片模型 ====================

class ImageGenProviderInfo(BaseModel):
    key: str
    name: str
    base_url: str
    models: List[str]
    default_model: str
    has_key: bool


class ImageUndProviderInfo(BaseModel):
    key: str
    name: str
    base_url: str
    models: List[str]
    default_model: str
    has_key: bool


class ImageModelStatus(BaseModel):
    current_provider: str
    current_model: str
    providers: List[ImageGenProviderInfo]


class ImageModelSwitchRequest(BaseModel):
    category: str = Field(..., description="图片模型类别: img_gen=生成, img_und=理解")
    provider: str = Field(..., description="提供商 key")
    model: Optional[str] = Field(None, description="模型名称")
    api_key: Optional[str] = Field(None, description="自定义 API Key")


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
