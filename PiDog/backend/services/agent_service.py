"""
Agent 对话服务 —— 封装 agent_v2 的 Function Calling 循环
支持会话管理、流式输出、token 追踪
"""

import sys
import os
import json
import uuid
import time
import asyncio
from typing import Dict, List, Optional, AsyncGenerator
from collections import defaultdict

# 确保项目根在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from models.llm.llm_chat import LLMChat
from utils.tool_registry import get_tool_schemas
from utils.function_calling_executor import FunctionCallingExecutor

from config import AppState, PROJECT_ROOT, WORKING_DIRECTORY
from services.token_service import record_usage

# ---- 常量 ----
MAX_CONSECUTIVE_FAILURES = 3
TOOL_RESULT_MAX_CHARS = 1000
MAX_SAME_TOOL_CONSECUTIVE = 2  # 同一工具连续调用次数上限（超过则注入提示）
SESSION_DIR = os.path.join(PROJECT_ROOT, "PiDog", "backend", "sessions")

# Blender 等"发后即忘"类工具：调用后只收到发送确认，无法获取执行结果
# 这类工具容易被 LLM 反复调用，需特殊提示
FIRE_AND_FORGET_TOOLS = {"blender_operation"}

# ---- 会话内存缓存 ----
_sessions: Dict[str, Dict] = {}  # session_id → {"messages": [...], "created_at": ...}

# ---- 审批队列（浏览器操作等需用户确认） ----
_approval_queue: Dict[str, asyncio.Event] = {}     # task_id → Event (后端等待)
_approval_results: Dict[str, bool] = {}             # task_id → True(批准)/False(拒绝)
APPROVAL_TIMEOUT = 120  # 等待用户审批的超时秒数


def _get_or_create_session(session_id: str = None) -> str:
    """获取已有会话或创建新会话"""
    if session_id and session_id in _sessions:
        return session_id

    sid = session_id or str(uuid.uuid4())[:8]
    if sid not in _sessions:
        _sessions[sid] = {
            "messages": _load_session_from_file(sid),
            "created_at": time.time(),
        }
    return sid


# ==================== 审批系统 ====================

def request_approval(task_id: str, tool_name: str, args: dict) -> bool:
    """
    同步审批（供 chat_sync 使用）—— 自动批准，无交互前端
    """
    return True  # 同步模式下默认批准


async def request_approval_async(task_id: str, tool_name: str, args: dict) -> bool:
    """
    异步审批（供 chat_stream 使用）—— 等待前端用户确认
    返回 True=批准, False=拒绝/超时
    """
    event = asyncio.Event()
    _approval_queue[task_id] = event
    _approval_results[task_id] = False  # 默认拒绝

    try:
        # 等待前端响应或超时
        await asyncio.wait_for(event.wait(), timeout=APPROVAL_TIMEOUT)
        return _approval_results.get(task_id, False)
    except asyncio.TimeoutError:
        return False
    finally:
        _approval_queue.pop(task_id, None)
        _approval_results.pop(task_id, None)


def submit_approval(task_id: str, approved: bool) -> bool:
    """前端提交审批结果"""
    if task_id in _approval_queue:
        _approval_results[task_id] = approved
        _approval_queue[task_id].set()
        return True
    return False


# 需要用户确认的工具列表
TOOLS_REQUIRING_APPROVAL = {"execute_command"}


def _load_session_from_file(session_id: str) -> List[Dict]:
    """从文件加载会话"""
    path = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_session_to_file(session_id: str, messages: List[Dict]):
    """保存会话到文件"""
    os.makedirs(SESSION_DIR, exist_ok=True)
    path = os.path.join(SESSION_DIR, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def _build_system_prompt() -> str:
    """构建精简 system prompt —— 推理约束模式"""
    wd = WORKING_DIRECTORY or os.path.join(PROJECT_ROOT, "workplace")
    return (
        f"# SmartAgent V2 — Inference-Constrained Mode\n"
        f"WD={wd}\n"
        f"Provider: {AppState.current_provider}  Model: {AppState.get_effective_model()}\n"
        f"## ⚠️ Mandatory Tool Calling\n"
        f"You MUST call a tool in EVERY response. NEVER output plain text.\n"
        f"To reply to user, call finish_task with reply='...'. Even 'OK' → finish_task(reply='OK',summary='ok').\n"
        f"## Rules\n"
        f"1. Scaffold dirs first, then write files top-down. All paths: {wd}/...\n"
        f"2. Each file must be complete — no stubs.\n"
        f"3. Tool fails ≥3x → finish_task with error.\n"
        f"4. Done → finish_task(summary='what + how to run', reply='friendly response to user').\n"
        f"5. For image generation, use output_path={wd}/filename.png\n"
        f"6. When referencing generated files (images, etc), use /files/filename in reply — NOT the full local path.\n"
        f"7. **NEVER retry the same tool with the same/similar args.** If a tool returned success, the operation is done — move on.\n"
        f"8. One blender_operation call = entire model creation. Put ALL code in a SINGLE code block.\n"
    )


def _is_failure(result_content: str) -> bool:
    """判断工具结果是否为失败"""
    cl = result_content.lower()
    if '"status": "success"' in cl or '"status":"success"' in cl:
        return False
    markers = ['"status": "error"', '"status": "failed"', '"status": "timeout"',
               'connection refused', 'could not connect', '未找到工具', '导入模块失败']
    return any(m in cl for m in markers)


# ==================== 非流式对话 ====================

def chat_sync(session_id: str, user_message: str, max_iterations: int = 15) -> dict:
    """
    同步对话 —— 完整执行工具链后返回结果
    """
    sid = _get_or_create_session(session_id)
    messages = _sessions[sid]["messages"]

    llm = LLMChat(
        api_key=AppState.get_api_key(),
        base_url=AppState.get_base_url(),
        model=AppState.get_effective_model(),
        max_tokens=3000,
        temperature=0.7,
    )
    executor = FunctionCallingExecutor(WORKING_DIRECTORY or os.path.join(PROJECT_ROOT, "workplace"))
    tools = get_tool_schemas()
    system_prompt = _build_system_prompt()

    messages.append({"role": "user", "content": user_message})

    iteration = 0
    task_finished = False
    _final_reply = ""
    failure_counts: Dict[str, int] = defaultdict(int)
    tool_names_called: List[str] = []
    # 同工具连续调用追踪（防止同一工具被反复调用）
    _last_tool: str = ""
    _same_tool_count: int = 0

    while iteration < max_iterations and not task_finished:
        iteration += 1

        # 熔断
        tripped = [n for n, c in failure_counts.items() if c >= MAX_CONSECUTIVE_FAILURES]
        for t in tripped:
            messages.append({
                "role": "system",
                "content": f"CRITICAL: {t} failed {failure_counts[t]}x. Call finish_task."
            })
            failure_counts.pop(t, None)

        try:
            response = llm.chat_with_tools(
                messages=messages, tools=tools,
                system_prompt=system_prompt, tool_choice="required",
            )
        except Exception as e:
            _save_session_to_file(sid, messages)
            return {"session_id": sid, "reply": f"LLM error: {e}", "tool_calls": tool_names_called}

        # 记录 token
        if hasattr(response, "usage") and response.usage:
            record_usage(
                provider=AppState.current_provider,
                model=AppState.get_effective_model(),
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )

        tool_calls, text_content = FunctionCallingExecutor.extract_tool_calls(response)

        if tool_calls:
            assistant_msg = {"role": "assistant", "content": None, "tool_calls": tool_calls}
            messages.append(assistant_msg)

            results = executor.execute_tool_calls(tool_calls)

            for i, r in enumerate(results):
                func_name = tool_calls[i]["function"]["name"] if i < len(tool_calls) else "?"
                tool_names_called.append(func_name)

                # 同工具连续调用检测（发后即忘类工具特别容易出问题）
                if func_name == _last_tool:
                    _same_tool_count += 1
                else:
                    _last_tool = func_name
                    _same_tool_count = 1

                if _same_tool_count > MAX_SAME_TOOL_CONSECUTIVE:
                    extra = (
                        f"\n\n[SYSTEM HINT] You have called '{func_name}' {_same_tool_count} times in a row. "
                        f"If the operation already succeeded, call finish_task NOW. "
                        f"Do NOT call the same tool again unless you have genuinely NEW operations to perform."
                    ) if func_name not in FIRE_AND_FORGET_TOOLS else (
                        f"\n\n[SYSTEM HINT] You have called '{func_name}' {_same_tool_count} times. "
                        f"This is a fire-and-forget tool — once called, the code is sent and executed. "
                        f"There is no need to retry. If the result shows success, call finish_task immediately."
                    )
                    messages.append({
                        "role": "system",
                        "content": extra.strip(),
                    })

                content = r.get("content", "")
                if len(content) > TOOL_RESULT_MAX_CHARS:
                    content = content[:TOOL_RESULT_MAX_CHARS] + "\n...(truncated)"

                if _is_failure(content):
                    failure_counts[func_name] = failure_counts.get(func_name, 0) + 1
                else:
                    failure_counts.pop(func_name, None)  # 只清除当前工具的失败计数

                if func_name == "finish_task" or r.get("_finish"):
                    task_finished = True
                    # 提取 reply 作为最终用户回复
                    try:
                        tc = tool_calls[i] if i < len(tool_calls) else {}
                        finish_args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                        _final_reply = finish_args.get("reply", finish_args.get("summary", ""))
                    except Exception:
                        _final_reply = ""

                messages.append({"role": "tool", "tool_call_id": r["tool_call_id"], "content": content})

        elif text_content:
            messages.append({"role": "assistant", "content": text_content})
            _save_session_to_file(sid, messages)
            return {"session_id": sid, "reply": text_content, "tool_calls": tool_names_called}
        else:
            break

    _save_session_to_file(sid, messages)

    if task_finished:
        return {"session_id": sid, "reply": _final_reply or "Done.", "tool_calls": tool_names_called}

    return {"session_id": sid, "reply": f"Max iterations ({max_iterations}) reached.", "tool_calls": tool_names_called}


# ==================== 流式对话（SSE） ====================

async def chat_stream(session_id: str, user_message: str, max_iterations: int = 15) -> AsyncGenerator[str, None]:
    """
    流式对话 —— 每步工具调用都实时推送事件
    """
    sid = _get_or_create_session(session_id)
    messages = _sessions[sid]["messages"]

    llm = LLMChat(
        api_key=AppState.get_api_key(),
        base_url=AppState.get_base_url(),
        model=AppState.get_effective_model(),
        max_tokens=3000,
        temperature=0.7,
    )
    executor = FunctionCallingExecutor(WORKING_DIRECTORY or os.path.join(PROJECT_ROOT, "workplace"))
    tools = get_tool_schemas()
    system_prompt = _build_system_prompt()

    messages.append({"role": "user", "content": user_message})
    yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

    iteration = 0
    task_finished = False
    _final_reply = ""
    failure_counts: Dict[str, int] = defaultdict(int)
    # 同工具连续调用追踪
    _last_tool: str = ""
    _same_tool_count: int = 0

    while iteration < max_iterations and not task_finished:
        iteration += 1

        tripped = [n for n, c in failure_counts.items() if c >= MAX_CONSECUTIVE_FAILURES]
        for t in tripped:
            messages.append({
                "role": "system",
                "content": f"CRITICAL: {t} failed {failure_counts[t]}x. Call finish_task."
            })
            failure_counts.pop(t, None)

        # LLM 调用是阻塞的，放线程池
        response = await asyncio.to_thread(
            llm.chat_with_tools,
            messages=messages, tools=tools,
            system_prompt=system_prompt, tool_choice="required",
        )

        if hasattr(response, "usage") and response.usage:
            record_usage(
                provider=AppState.current_provider,
                model=AppState.get_effective_model(),
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )

        tool_calls, text_content = FunctionCallingExecutor.extract_tool_calls(response)

        if tool_calls:
            assistant_msg = {"role": "assistant", "content": None, "tool_calls": tool_calls}
            messages.append(assistant_msg)

            # ---- 审批检查：危险工具需用户确认后才执行 ----
            results = []
            for i, tc in enumerate(tool_calls):
                func_name = tc["function"]["name"]
                func_args = json.loads(tc.get("function", {}).get("arguments", "{}"))

                if func_name in TOOLS_REQUIRING_APPROVAL:
                    task_id = f"{sid}-{iteration}-{i}"
                    yield f"data: {json.dumps({'type': 'approval_required', 'tool': func_name, 'task_id': task_id, 'iteration': iteration, 'args': func_args})}\n\n"

                    approved = await request_approval_async(task_id, func_name, func_args)
                    if approved:
                        yield f"data: {json.dumps({'type': 'approval_result', 'task_id': task_id, 'approved': True, 'tool': func_name})}\n\n"
                        # 只执行当前这一个工具
                        single_result = executor.execute_tool_calls([tc])
                        results.extend(single_result)
                    else:
                        yield f"data: {json.dumps({'type': 'approval_result', 'task_id': task_id, 'approved': False, 'tool': func_name})}\n\n"
                        # 生成"已拒绝"的模拟结果
                        results.append({
                            "tool_call_id": tc.get("id", f"call_{i}"),
                            "content": f"[USER REJECTED] 用户拒绝了 {func_name} 操作。请换一种方式完成任务，或调用 finish_task 结束。",
                            "_finish": False,
                        })
                else:
                    results.extend(executor.execute_tool_calls([tc]))

            for i, r in enumerate(results):
                func_name = tool_calls[i]["function"]["name"] if i < len(tool_calls) else "?"

                # 同工具连续调用检测
                if func_name == _last_tool:
                    _same_tool_count += 1
                else:
                    _last_tool = func_name
                    _same_tool_count = 1

                if _same_tool_count > MAX_SAME_TOOL_CONSECUTIVE:
                    hint = (
                        f"[SYSTEM HINT] '{func_name}' called {_same_tool_count}x in a row. "
                        f"It is fire-and-forget — code was sent and executed. No retry needed. "
                        f"Call finish_task now."
                    ) if func_name in FIRE_AND_FORGET_TOOLS else (
                        f"[SYSTEM HINT] You called '{func_name}' {_same_tool_count}x consecutively. "
                        f"If the operation already succeeded, call finish_task NOW. "
                        f"Do NOT call the same tool again without genuinely NEW operations."
                    )
                    messages.append({"role": "system", "content": hint})

                content = r.get("content", "")
                if len(content) > TOOL_RESULT_MAX_CHARS:
                    content = content[:TOOL_RESULT_MAX_CHARS] + "\n...(truncated)"

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': func_name, 'iteration': iteration})}\n\n"

                if _is_failure(content):
                    failure_counts[func_name] = failure_counts.get(func_name, 0) + 1
                    yield f"data: {json.dumps({'type': 'tool_error', 'tool': func_name, 'error': content[:200]})}\n\n"
                else:
                    failure_counts.pop(func_name, None)  # 只清除当前工具的失败计数

                if func_name == "finish_task" or r.get("_finish"):
                    task_finished = True
                    # 提取 reply 作为最终用户回复
                    try:
                        tc = tool_calls[i] if i < len(tool_calls) else {}
                        finish_args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                        _final_reply = finish_args.get("reply", finish_args.get("summary", ""))
                    except Exception:
                        _final_reply = ""
                    yield f"data: {json.dumps({'type': 'finish', 'summary': content[:500]})}\n\n"

                messages.append({"role": "tool", "tool_call_id": r["tool_call_id"], "content": content})

        elif text_content:
            messages.append({"role": "assistant", "content": text_content})
            yield f"data: {json.dumps({'type': 'reply', 'content': text_content})}\n\n"
            break
        else:
            break

    _save_session_to_file(sid, messages)
    yield "data: [DONE]\n\n"


# ==================== 会话管理 ====================

def list_sessions() -> List[Dict]:
    """列出所有会话"""
    sessions = []
    if os.path.isdir(SESSION_DIR):
        for fname in os.listdir(SESSION_DIR):
            if fname.endswith(".json"):
                sid = fname[:-5]
                path = os.path.join(SESSION_DIR, fname)
                try:
                    mtime = os.path.getmtime(path)
                    with open(path, "r", encoding="utf-8") as f:
                        msgs = json.load(f)
                    last_msg = msgs[-1].get("content", "")[:80] if msgs else ""
                    sessions.append({
                        "session_id": sid,
                        "messages_count": len(msgs),
                        "last_active": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)),
                        "preview": last_msg,
                    })
                except Exception:
                    pass
    sessions.sort(key=lambda s: s["last_active"], reverse=True)
    return sessions


def delete_session(session_id: str) -> bool:
    """删除会话"""
    path = os.path.join(SESSION_DIR, f"{session_id}.json")
    _sessions.pop(session_id, None)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def compact_session(session_id: str, llm: LLMChat = None) -> dict:
    """压缩会话"""
    sid = _get_or_create_session(session_id)
    messages = _sessions[sid]["messages"]

    if len(messages) < 10:
        return {"ok": False, "error": f"Only {len(messages)} messages — need at least 10"}

    if llm is None:
        llm = LLMChat(
            api_key=AppState.get_api_key(),
            base_url=AppState.get_base_url(),
            model=AppState.get_effective_model(),
            max_tokens=500, temperature=0.3,
        )

    lines = []
    for m in messages:
        role = m.get("role", "")
        if role == "user":
            lines.append(f"User: {m.get('content', '')[:200]}")
        elif role == "assistant":
            tcs = m.get("tool_calls")
            if tcs:
                names = [tc.get("function", {}).get("name", "?") for tc in tcs]
                lines.append(f"Assistant: called {', '.join(names)}")
            elif m.get("content"):
                lines.append(f"Assistant: {m['content'][:200]}")

    try:
        summary = llm.chat_no_memory(
            messages=[
                {"role": "system", "content": "Summarize this conversation: what was built, key decisions, current state. Under 300 tokens. Bullet points."},
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.3, max_tokens=400,
        )
        compressed = [{"role": "system", "content": f"[COMPACTED]\n{summary}"}]
        keep = messages[-6:] if len(messages) > 6 else messages
        compressed.extend(keep)
        _sessions[sid]["messages"] = compressed
        _save_session_to_file(sid, compressed)
        return {"ok": True, "before": len(messages), "after": len(compressed), "summary": summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}
