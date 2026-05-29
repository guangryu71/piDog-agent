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
from utils.tool_registry import (
    get_tool_schemas, build_skill_selection_prompt, get_tools_for_skills,
)
from utils.function_calling_executor import FunctionCallingExecutor

from config import AppState, PROJECT_ROOT, WORKING_DIRECTORY
from services.token_service import record_usage

# ---- 常量 ----
MAX_CONSECUTIVE_FAILURES = 3
TOOL_RESULT_MAX_CHARS = 4000  # 浏览器/搜索类工具返回数据量大，1000 会导致截断后 LLM 误判信息不完整而重试
MAX_SAME_TOOL_CONSECUTIVE = 2  # 同一工具连续调用次数上限（超过则注入提示）
AUTO_COMPACT_THRESHOLD = 40    # 消息数超过此值自动压缩
AUTO_COMPACT_KEEP = 8          # 压缩后保留最近 N 条消息
SESSION_DIR = os.path.join(PROJECT_ROOT, "PiDog", "backend", "sessions")

# Blender 等"发后即忘"类工具：调用后只收到发送确认，无法获取执行结果
# 这类工具容易被 LLM 反复调用，需特殊提示
FIRE_AND_FORGET_TOOLS = {"blender_operation"}

# ---- 两阶段工具选择 ----

def _select_tools(user_message: str) -> list:
    """
    第一阶段：扫描 skills/ 文件夹的 README.md，让 LLM 选择需要的技能。
    第二阶段：根据选中技能，从 SKILL_REGISTRY 返回对应的工具 Schema。

    Args:
        user_message: 用户消息

    Returns:
        选中的工具 Schema 列表（只包含需要技能的工具 + finish_task）
    """
    prompt = build_skill_selection_prompt(user_message)

    if not prompt:
        # skills/ 文件夹为空或不存在 → 退回全量工具
        return get_tool_schemas()

    try:
        llm = LLMChat(
            api_key=AppState.get_api_key(),
            base_url=AppState.get_base_url(),
            model=AppState.get_effective_model(),
            max_tokens=200,
            temperature=0.3,
        )
        # 第一轮：选技能（不用 Function Calling，纯文本）
        response = llm.chat_no_memory(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )

        # 解析 LLM 返回的 JSON
        import re
        match = re.search(r'\{[^{}]*"selected_skills"[^{}]*\}', response, re.DOTALL)
        if match:
            result = json.loads(match.group())
            skills = result.get("selected_skills", [])
            if skills:
                tools = get_tools_for_skills(skills)
                import logging
                logging.getLogger("agent").info(f"[SKILL SELECT] {skills} → {len(tools)} tools")
                return tools
    except Exception as e:
        import logging
        logging.getLogger("agent").warning(f"[SKILL SELECT] Failed: {e}, falling back to all tools")

    # 退回全量工具
    return get_tool_schemas()

# ---- 会话内存缓存 ----
_sessions: Dict[str, Dict] = {}  # session_id → {"messages": [...], "created_at": ...}

# ---- 审批队列（浏览器操作等需用户确认） ----
_approval_queue: Dict[str, asyncio.Event] = {}     # task_id → Event (后端等待)
_approval_results: Dict[str, bool] = {}             # task_id → True(批准)/False(拒绝)
APPROVAL_TIMEOUT = 120  # 等待用户审批的超时秒数

# ---- 取消机制 ----
_cancel_events: Dict[str, asyncio.Event] = {}       # session_id → Cancel Event


def cancel_session(session_id: str) -> bool:
    """取消指定会话的运行中任务"""
    if session_id in _cancel_events:
        _cancel_events[session_id].set()
        return True
    return False


# ---- 文件上传支持 ----
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 支持多模态的模型前缀
MULTIMODAL_MODELS = {"qwen-vl", "qvq", "gpt-4o", "gpt-4-vision", "claude-3", "gemini"}

# 图片后缀
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}

# 文本类后缀 — 直接预读内容注入消息（不走工具调用）
TEXT_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html", ".htm",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".csv", ".tsv",
    ".md", ".txt", ".log", ".cfg", ".ini", ".conf", ".env",
    ".sh", ".bash", ".bat", ".ps1", ".cmd",
    ".sql", ".r", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go",
    ".rs", ".swift", ".kt", ".scala", ".rb", ".php", ".pl", ".lua",
    ".dockerfile", ".makefile", ".cmake",
}

# 预读文件最大字符数（避免超长文件撑爆 token）
MAX_PRELOAD_CHARS = 8000


def _build_user_message(text: str, file_id: str = None) -> dict:
    """
    构建用户消息，智能处理上传文件：

    - 文本类文件：直接预读内容注入消息，LLM 无需额外工具调用
    - 图片 + 多模态模型：base64 image_url，模型可"看见"图片
    - 图片 + 纯文本模型：告知路径，提示 Agent 用 process_image 工具处理
    - PDF/Office 等：告知路径 + 建议用对应工具读取
    - 其他二进制：仅告知路径
    """
    if not file_id:
        return {"role": "user", "content": text}

    # 查找上传的文件
    file_path = None
    filename = None
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            file_path = os.path.join(UPLOAD_DIR, fname)
            filename = fname  # 完整文件名（含后缀）
            break

    if not file_path or not os.path.exists(file_path):
        return {"role": "user", "content": text}

    model = (AppState.get_effective_model() or "").lower()
    is_multimodal = any(mm in model for mm in MULTIMODAL_MODELS)
    ext = os.path.splitext(file_path)[1].lower()

    # ── 分支 1：图片 + 多模态模型 → base64 ──
    if ext in IMAGE_EXTS and is_multimodal:
        import base64
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            ".svg": "image/svg+xml", ".ico": "image/x-icon",
        }
        mime = mime_map.get(ext, "image/png")
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            ]
        }

    # ── 分支 2：文本类文件 → 预读内容 ──
    if ext in TEXT_EXTS:
        try:
            # 尝试 utf-8，失败则用 gbk（Windows 常见编码）
            for encoding in ("utf-8", "gbk", "latin-1"):
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # 所有编码都失败，当二进制处理
                return {
                    "role": "user",
                    "content": f"{text}\n\n[用户上传了文件: {filename}，路径: {file_path}，无法解码为文本]"
                }

            # 截断过长内容
            truncated = False
            if len(content) > MAX_PRELOAD_CHARS:
                content = content[:MAX_PRELOAD_CHARS]
                truncated = True

            return {
                "role": "user",
                "content": (
                    f"{text}\n\n"
                    f"--- 用户上传文件: {filename} ---\n"
                    f"文件绝对路径: {file_path}\n"
                    f"内容如下（{'前 ' + str(MAX_PRELOAD_CHARS) + ' 字符，已截断' if truncated else '全文'}）:\n"
                    f"```{ext.lstrip('.')}\n{content}\n```\n"
                    f"{'(文件过长已截断，如需完整内容请用 read_file 工具读取: ' + file_path + ')' if truncated else ''}"
                    f"\n[注意：文件内容已直接提供给你，无需再调用 read_file 工具]"
                )
            }
        except Exception:
            # 读取失败，告知路径
            return {
                "role": "user",
                "content": f"{text}\n\n[用户上传了文件: {filename}，路径: {file_path}，读取失败]"
            }

    # ── 分支 3：图片 + 纯文本模型 → 告知路径，建议用工具 ──
    if ext in IMAGE_EXTS:
        return {
            "role": "user",
            "content": (
                f"{text}\n\n"
                f"[用户上传了图片: {filename}，绝对路径: {file_path}]\n"
                f'当前模型不支持直接查看图片。如需处理此图片（识别内容、生成新图等），请使用 process_image 工具，'
                f'传入 image_path="{file_path}"。'
            )
        }

    # ── 分支 4：PDF / Office / 其他二进制 → 告知路径 + 建议工具 ──
    tool_hints = {
        ".pdf":  "请使用 PDF 技能读取内容（如有）。",
        ".docx": "请使用 DOCX 技能读取内容（如有）。",
        ".doc":  "请使用 DOCX 技能读取内容（如有）。",
        ".xlsx": "请使用 XLSX 技能读取内容（如有）。",
        ".pptx": "请使用 PPTX 技能读取内容（如有）。",
    }
    hint = tool_hints.get(ext, "")

    return {
        "role": "user",
        "content": (
            f"{text}\n\n"
            f"[用户上传了文件: {filename}，绝对路径: {file_path}]"
            + (f"\n{hint}" if hint else "")
        )
    }


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
    """从文件加载会话，自动清理孤立的 tool_calls（两种方向）"""
    path = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except Exception:
            return []

        # ---- 收集所有合法的 tool_call_id ----
        valid_call_ids: set = set()
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    valid_call_ids.add(tc.get("id", ""))

        # ---- 清理 ----
        cleaned = []
        pending_call_ids: set = set()

        for msg in messages:
            role = msg.get("role", "")
            if role == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    pending_call_ids.add(tc.get("id", ""))
                cleaned.append(msg)
            elif role == "tool":
                call_id = msg.get("tool_call_id", "")
                if call_id in valid_call_ids:
                    pending_call_ids.discard(call_id)
                    cleaned.append(msg)
                # else: 孤立的 tool（没有前置 assistant(tool_calls)）→ 丢弃
            else:
                cleaned.append(msg)

        # 移除没有对应 tool 结果的 assistant(tool_calls) 消息
        if pending_call_ids:
            for i in range(len(cleaned) - 1, -1, -1):
                m = cleaned[i]
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    if all(tc.get("id", "") in pending_call_ids for tc in m["tool_calls"]):
                        del cleaned[i]
                    break

        return cleaned
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
        f"9. **IMPORTANT — DISPLAY TOOL RESULTS.** When a tool returns data (news, search results, browser content, images, file content, etc), "
        f"you MUST summarize and PRESENT the results directly in your finish_task reply. "
        f"NEVER say 'due to technical limitations' or 'I cannot display/extract/show the content'. "
        f"The data is already retrieved — just format it nicely and show it to the user. "
        f"This is your core job: fetch data AND present it.\n"
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

def chat_sync(session_id: str, user_message: str, file_id: str = None, max_iterations: int = 15) -> dict:
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
    tools = _select_tools(user_message)  # 两阶段选择：先选技能再取对应 Schema
    system_prompt = _build_system_prompt()

    messages.append(_build_user_message(user_message, file_id))

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
                system_prompt=system_prompt,  # tool_choice 默认 "auto"（DashScope 兼容 API 不支持 "required"）
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

            try:
                results = executor.execute_tool_calls(tool_calls)
            except Exception as exec_err:
                # 工具执行整体崩溃：为每个 tool_call 生成错误结果，保证消息完整性
                results = []
                for tc in tool_calls:
                    results.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "content": f"[ERROR] 工具执行失败: {exec_err}",
                        "_finish": False,
                    })

            # ---- 防御：确保 results 与 tool_calls 严格对齐 ----
            # 按 tool_call_id 建立索引，防止执行器返回空列表或不匹配
            results_by_id: Dict[str, Dict] = {}
            for r in results:
                results_by_id[r.get("tool_call_id", "")] = r

            aligned_results = []
            for tc in tool_calls:
                call_id = tc.get("id", "")
                if call_id in results_by_id:
                    aligned_results.append(results_by_id[call_id])
                else:
                    # 结果缺失：生成占位错误消息，保证消息完整性
                    aligned_results.append({
                        "tool_call_id": call_id,
                        "role": "tool",
                        "content": f"[ERROR] 工具未返回结果: {tc.get('function', {}).get('name', '?')}",
                        "_finish": False,
                    })

            # 收集同工具连续调用提示（循环结束后再注入，避免卡在 assistant(tool_calls) 和 tool 之间破坏配对）
            _hints_to_inject: List[str] = []

            for i, r in enumerate(aligned_results):
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
                        f"[SYSTEM HINT] You have called '{func_name}' {_same_tool_count} times in a row. "
                        f"If the operation already succeeded, call finish_task NOW. "
                        f"Do NOT call the same tool again unless you have genuinely NEW operations to perform."
                    ) if func_name not in FIRE_AND_FORGET_TOOLS else (
                        f"[SYSTEM HINT] You have called '{func_name}' {_same_tool_count} times. "
                        f"This is a fire-and-forget tool — once called, the code is sent and executed. "
                        f"There is no need to retry. If the result shows success, call finish_task immediately."
                    )
                    _hints_to_inject.append(extra.strip())

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

                    # 如果前序工具（browser_automation 等）返回了丰富内容，附加到 finish_task 回复中
                    prev_detailed = ""
                    for prev_idx in range(len(aligned_results)):
                        prev_func = tool_calls[prev_idx]["function"]["name"] if prev_idx < len(tool_calls) else ""
                        if prev_func in ("browser_automation",) and prev_idx != i:
                            prev_content = aligned_results[prev_idx].get("content", "")
                            if len(prev_content) > 200 and prev_content not in _final_reply:
                                prev_detailed = prev_content.strip()
                    if prev_detailed:
                        _final_reply = prev_detailed + "\n\n---\n" + _final_reply

                messages.append({"role": "tool", "tool_call_id": r["tool_call_id"], "content": content})

            # ---- 在所有 tool 结果之后注入提示（不破坏 assistant→tool 配对） ----
            for hint in _hints_to_inject:
                messages.append({"role": "system", "content": hint})

        elif text_content:
            messages.append({"role": "assistant", "content": text_content})
            _save_session_to_file(sid, messages)
            return {"session_id": sid, "reply": text_content, "tool_calls": tool_names_called}
        else:
            break

    # 自动压缩后再保存
    messages = _auto_compact_if_needed(sid, messages)
    _save_session_to_file(sid, messages)

    if task_finished:
        return {"session_id": sid, "reply": _final_reply or "Done.", "tool_calls": tool_names_called}

    return {"session_id": sid, "reply": f"Max iterations ({max_iterations}) reached.", "tool_calls": tool_names_called}


# ==================== 流式对话（SSE） ====================

async def chat_stream(session_id: str, user_message: str, file_id: str = None, max_iterations: int = 15) -> AsyncGenerator[str, None]:
    """
    流式对话 —— 每步工具调用都实时推送事件。支持前端取消。
    """
    sid = _get_or_create_session(session_id)
    messages = _sessions[sid]["messages"]

    # 注册取消事件（覆盖旧事件，防止旧取消信号干扰新任务）
    _cancel_events[sid] = asyncio.Event()

    llm = LLMChat(
        api_key=AppState.get_api_key(),
        base_url=AppState.get_base_url(),
        model=AppState.get_effective_model(),
        max_tokens=3000,
        temperature=0.7,
    )
    executor = FunctionCallingExecutor(WORKING_DIRECTORY or os.path.join(PROJECT_ROOT, "workplace"))
    tools = _select_tools(user_message)  # 两阶段选择：先选技能再取对应 Schema
    system_prompt = _build_system_prompt()

    # 构建用户消息（可能附带文件）
    user_msg = _build_user_message(user_message, file_id)
    messages.append(user_msg)
    yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

    iteration = 0
    task_finished = False
    _final_reply = ""
    failure_counts: Dict[str, int] = defaultdict(int)
    # 同工具连续调用追踪
    _last_tool: str = ""
    _same_tool_count: int = 0

    while iteration < max_iterations and not task_finished:
        # ---- 检查是否被取消 ----
        if _cancel_events.get(sid, asyncio.Event()).is_set():
            yield f"data: {json.dumps({'type': 'cancelled', 'message': 'Task cancelled by user'})}\n\n"
            _save_session_to_file(sid, messages)
            break

        iteration += 1

        tripped = [n for n, c in failure_counts.items() if c >= MAX_CONSECUTIVE_FAILURES]
        for t in tripped:
            messages.append({
                "role": "system",
                "content": f"CRITICAL: {t} failed {failure_counts[t]}x. Call finish_task."
            })
            failure_counts.pop(t, None)

        # LLM 调用是阻塞的，放线程池
        try:
            response = await asyncio.to_thread(
                llm.chat_with_tools,
                messages=messages, tools=tools,
                system_prompt=system_prompt,  # tool_choice 默认 "auto"（DashScope 兼容 API 不支持 "required"）
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'LLM API error: {str(e)}', 'iteration': iteration})}\n\n"
            # 不保存损坏的会话；下次请求会从文件加载最后一次健康状态
            break

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

            # ---- 逐个执行工具调用：每步 yield tool_call 事件，实现前端流式显示 ----
            # 收集连续调用提示（循环结束后再注入，避免卡在 assistant→tool 之间破坏配对）
            _hints_to_inject: List[str] = []
            # 保存本轮工具执行结果，供 finish_task 事件携带原始数据
            _tool_results_map: Dict[str, str] = {}
            for i, tc in enumerate(tool_calls):
                func_name = tc["function"]["name"]
                func_args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                call_id = tc.get("id", f"call_{iteration}_{i}")

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
                    _hints_to_inject.append(hint)

                # ---- 审批检查 ----
                if func_name in TOOLS_REQUIRING_APPROVAL:
                    task_id = f"{sid}-{iteration}-{i}"
                    yield f"data: {json.dumps({'type': 'approval_required', 'tool': func_name, 'task_id': task_id, 'iteration': iteration, 'args': func_args})}\n\n"

                    approved = await request_approval_async(task_id, func_name, func_args)
                    if approved:
                        yield f"data: {json.dumps({'type': 'approval_result', 'task_id': task_id, 'approved': True, 'tool': func_name})}\n\n"
                        try:
                            r = executor.execute_tool_call(tc)
                        except Exception as exec_err:
                            r = {
                                "tool_call_id": call_id,
                                "role": "tool",
                                "content": f"[ERROR] 工具执行失败: {exec_err}",
                                "_finish": False,
                            }
                    else:
                        yield f"data: {json.dumps({'type': 'approval_result', 'task_id': task_id, 'approved': False, 'tool': func_name})}\n\n"
                        r = {
                            "tool_call_id": call_id,
                            "role": "tool",
                            "content": f"[USER REJECTED] 用户拒绝了 {func_name} 操作。请换一种方式完成任务，或调用 finish_task 结束。",
                            "_finish": False,
                        }
                else:
                    try:
                        r = executor.execute_tool_call(tc)
                    except Exception as exec_err:
                        r = {
                            "tool_call_id": call_id,
                            "role": "tool",
                            "content": f"[ERROR] 工具执行失败: {exec_err}",
                            "_finish": False,
                        }

                content = r.get("content", "")
                if len(content) > TOOL_RESULT_MAX_CHARS:
                    content = content[:TOOL_RESULT_MAX_CHARS] + "\n...(truncated)"

                # 保存工具结果（browser_automation 等），供 finish_task 事件携带
                _tool_results_map[func_name] = content

                # ---- 按顺序 yield：先 tool_call 事件（带 flush），再结果 ----
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': func_name, 'iteration': iteration, 'step': f'{i+1}/{len(tool_calls)}'})}\n\n"
                await asyncio.sleep(0)  # flush so each event reaches frontend individually

                if _is_failure(content):
                    failure_counts[func_name] = failure_counts.get(func_name, 0) + 1
                    yield f"data: {json.dumps({'type': 'tool_error', 'tool': func_name, 'error': content[:200]})}\n\n"
                else:
                    failure_counts.pop(func_name, None)

                if func_name == "finish_task" or r.get("_finish"):
                    task_finished = True
                    try:
                        _final_reply = func_args.get("reply", func_args.get("summary", ""))
                    except Exception:
                        _final_reply = ""

                    # 把前序工具（browser_automation 等）的原始结果附加到 finish 事件
                    _prev_tool_data = ""
                    for _tn in ("browser_automation", "web_search", "get_page_content"):
                        if _tn in _tool_results_map:
                            _pd = _tool_results_map[_tn]
                            if len(_pd) > 100:
                                _prev_tool_data = _pd.strip()
                                break
                    yield f"data: {json.dumps({'type': 'finish', 'summary': content[:500], 'reply': _final_reply, 'tool_data': _prev_tool_data})}\n\n"

                messages.append({"role": "tool", "tool_call_id": r.get("tool_call_id", call_id), "content": content})

            # ---- 在所有 tool 结果之后注入提示（不破坏 assistant→tool 配对） ----
            for hint in _hints_to_inject:
                messages.append({"role": "system", "content": hint})

        elif text_content:
            messages.append({"role": "assistant", "content": text_content})
            yield f"data: {json.dumps({'type': 'reply', 'content': text_content})}\n\n"
            break
        else:
            break

    # 自动压缩后再保存
    messages = _auto_compact_if_needed(sid, messages)
    _save_session_to_file(sid, messages)
    yield "data: [DONE]\n\n"

    # 清理取消事件
    _cancel_events.pop(sid, None)


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


def _auto_compact_if_needed(sid: str, messages: List[Dict]) -> List[Dict]:
    """自动压缩：消息数超过阈值时静默压缩，返回压缩后的消息列表"""
    if len(messages) <= AUTO_COMPACT_THRESHOLD:
        return messages

    try:
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

        summary = llm.chat_no_memory(
            messages=[
                {"role": "system", "content": "Summarize this conversation: what was built, key decisions, current state. Under 300 tokens. Bullet points."},
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.3, max_tokens=400,
        )

        compressed = [{"role": "system", "content": f"[AUTO-COMPACTED]\n{summary}"}]
        keep_start = max(0, len(messages) - AUTO_COMPACT_KEEP)

        # ---- 保护 tool_call/tool_result 配对 ----
        # 从 keep_start 向前扫描，确保不把 tool 结果和其 assistant(tool_calls) 拆开
        # 否则 DashScope API 会报错: "messages with role 'tool' must be a response
        # to a preceeding message with 'tool_calls'"
        while keep_start > 0:
            m = messages[keep_start]
            if m.get("role") == "assistant" and m.get("tool_calls"):
                keep_start -= 1
                break
            keep_start -= 1

        keep = messages[keep_start:]
        compressed.extend(keep)

        # 更新内存缓存和文件
        _sessions[sid]["messages"] = compressed
        _save_session_to_file(sid, compressed)
        return compressed
    except Exception:
        return messages  # 压缩失败不丢数据，原样返回


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
        keep_start = max(0, len(messages) - AUTO_COMPACT_KEEP)

        # ---- 保护 tool_call/tool_result 配对（同 auto-compact） ----
        while keep_start > 0:
            m = messages[keep_start]
            if m.get("role") == "assistant" and m.get("tool_calls"):
                keep_start -= 1
                break
            keep_start -= 1

        keep = messages[keep_start:]
        compressed.extend(keep)
        _sessions[sid]["messages"] = compressed
        _save_session_to_file(sid, compressed)
        return {"ok": True, "before": len(messages), "after": len(compressed), "summary": summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def clean_all_memory() -> dict:
    """清理所有记忆：会话文件 + 上传文件 + 内存缓存 + 历史文件"""
    deleted_files = 0
    errors = []

    # 1. 清理会话文件
    session_dir = SESSION_DIR
    if os.path.isdir(session_dir):
        for fname in os.listdir(session_dir):
            fpath = os.path.join(session_dir, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    deleted_files += 1
            except Exception as e:
                errors.append(f"sessions/{fname}: {e}")

    # 2. 清理上传文件
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            fpath = os.path.join(upload_dir, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    deleted_files += 1
            except Exception as e:
                errors.append(f"uploads/{fname}: {e}")

    # 3. 清理内存缓存
    _sessions.clear()
    # 同时清理取消事件
    _cancel_events.clear()

    # 4. 清理历史文件
    try:
        from config import PROJECT_ROOT
        history_path = os.path.join(PROJECT_ROOT, "history", "history.md")
        if os.path.exists(history_path):
            os.remove(history_path)
            deleted_files += 1
        # 也清空历史目录下其他文件
        history_dir = os.path.dirname(history_path)
        if os.path.isdir(history_dir):
            for fname in os.listdir(history_dir):
                fpath = os.path.join(history_dir, fname)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                        deleted_files += 1
                except Exception as e:
                    errors.append(f"history/{fname}: {e}")
    except Exception as e:
        errors.append(f"history: {e}")

    return {
        "ok": True,
        "deleted_files": deleted_files,
        "cleared_sessions": "memory cache cleared",
        "errors": errors if errors else None,
    }
    """列出所有会话，每条包含 id、消息数、最后活跃时间、最后用户问题预览"""
    result = []
    for sid, sess in _sessions.items():
        msgs = sess.get("messages", [])
        # 找到最后一条 user 消息作为预览
        user_preview = ""
        for m in reversed(msgs):
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    # 多模态消息：取 text 部分
                    for c in content:
                        if c.get("type") == "text":
                            content = c["text"]
                            break
                    else:
                        content = ""
                user_preview = content[:120]
                break
        result.append({
            "session_id": sid,
            "message_count": len(msgs),
            "last_active": sess.get("created_at", 0),
            "preview": user_preview,
        })
    # 按最后活跃时间倒序
    result.sort(key=lambda x: x["last_active"], reverse=True)
    return result


def delete_session(session_id: str) -> bool:
    """删除会话"""
    if session_id in _sessions:
        del _sessions[session_id]
    # 删除文件
    path = os.path.join(SESSION_DIR, f"{session_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
