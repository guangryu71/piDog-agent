"""
对话路由 —— Agent 聊天接口（同步 + 流式）+ 取消 + 文件上传 + 清理记忆
"""

import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
from api_schemas.schemas import ChatRequest, ChatResponse, ApprovalRequest
from services import agent_service

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# 上传文件存放目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    """同步对话 —— 完整执行后返回"""
    result = agent_service.chat_sync(
        session_id=req.session_id,
        user_message=req.message,
        file_id=req.file_id,
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
            file_id=req.file_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cancel/{session_id}")
def cancel_chat(session_id: str):
    """取消正在运行的对话任务"""
    ok = agent_service.cancel_session(session_id)
    return {"ok": ok, "session_id": session_id}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件，返回 file_id 供对话引用"""
    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    safe_name = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "ok": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "type": file.content_type or "application/octet-stream",
    }


@router.get("/sessions")
def list_sessions():
    """列出所有会话"""
    return agent_service.list_sessions()


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """获取会话详情（包含完整消息）"""
    return agent_service.get_session_messages(session_id)


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


@router.post("/clean")
def clean_all_memory():
    """清理所有记忆：会话文件 + 上传文件 + 内存缓存 + 历史文件"""
    return agent_service.clean_all_memory()
