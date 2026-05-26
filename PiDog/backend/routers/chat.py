"""
对话路由 —— Agent 聊天接口（同步 + 流式）
"""

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from api_schemas.schemas import ChatRequest, ChatResponse, ApprovalRequest
from services import agent_service

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    """同步对话 —— 完整执行后返回"""
    result = agent_service.chat_sync(
        session_id=req.session_id,
        user_message=req.message,
    )
    return ChatResponse(
        session_id=result["session_id"],
        reply=result["reply"],
        tool_calls=result.get("tool_calls", []),
    )


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """流式对话 —— SSE 实时推送每步工具调用"""
    return StreamingResponse(
        agent_service.chat_stream(
            session_id=req.session_id,
            user_message=req.message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
def list_sessions():
    """列出所有会话"""
    return agent_service.list_sessions()


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """删除会话"""
    ok = agent_service.delete_session(session_id)
    return {"ok": ok}


@router.post("/sessions/{session_id}/compact")
def compact_session(session_id: str):
    """压缩会话历史"""
    return agent_service.compact_session(session_id)


@router.post("/approve")
def approve(req: ApprovalRequest):
    """用户审批浏览器操作：批准或拒绝"""
    ok = agent_service.submit_approval(req.task_id, req.approved)
    return {"ok": ok, "task_id": req.task_id, "approved": req.approved}
