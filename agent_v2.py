"""
Agent V2 —— 基于原生 Function Calling 的新架构

核心改进（对比原 agent.py）：
  原架构:  Thinker(选Skill) → Workflower(生成裸JSON) → regex解析JSON → 动态import执行
  新架构:  大模型 + tools参数(Function Calling) → 结构化 tool_calls → Schema校验 → 注册表执行

用法：
  python agent_v2.py                    # 交互式
  python agent_v2.py "帮我创建项目"      # 单次任务
"""

import json
import os
import sys
import atexit
from typing import Dict, Any, List, Optional
from collections import defaultdict

from models.llm.llm_chat import LLMChat
from utils.tool_registry import get_tool_schemas
from utils.function_calling_executor import FunctionCallingExecutor

# ---- 颜色 ----
RESET = '\033[0m'
BOLD  = '\033[1m'
RED   = '\033[91m'
GREEN = '\033[92m'
YELLOW= '\033[93m'
BLUE  = '\033[94m'
CYAN  = '\033[96m'

# ---- 全局配置 ----
QWEN_CONFIG: Dict[str, Any] = {}
WORKING_DIRECTORY: str = ""
SKILLS_DIRECTORY: str = ""
SKILLS_LOCATOR_PATH: str = ""

# ---- 防死循环：同一工具连续失败阈值 ----
MAX_CONSECUTIVE_FAILURES = 3

# ---- 跨轮次记忆 ----
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(PROJECT_DIR, "history")
HISTORY_FILE = os.path.join(HISTORY_DIR, "conversation.json")
MAX_HISTORY_MESSAGES = 50   # 最多保留最近50条消息


def load_config(config_path: str = "confing.json"):
    global QWEN_CONFIG, WORKING_DIRECTORY, SKILLS_DIRECTORY, SKILLS_LOCATOR_PATH

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    QWEN_CONFIG.update(config_data.get("qwen_config", {}))
    WORKING_DIRECTORY = config_data.get("working_directory", "")
    SKILLS_DIRECTORY = config_data.get("skills_directory", "skills")

    if WORKING_DIRECTORY and not os.path.isabs(WORKING_DIRECTORY):
        WORKING_DIRECTORY = os.path.abspath(WORKING_DIRECTORY)
    if WORKING_DIRECTORY:
        os.makedirs(WORKING_DIRECTORY, exist_ok=True)

    print(f"{GREEN}[OK] Config loaded{RESET}")


def _load_system_prompt() -> str:
    """构建精简 System Prompt —— 去掉冗余的工具 markdown，工具由 tools 参数原生传递"""
    api_key = QWEN_CONFIG.get("api_key", "")
    api_key_hint = api_key[:8] + "..." if len(api_key) > 8 else "NOT SET"

    return (
        f"# SmartAgent V2 — Inference-Constrained Mode\n"
        f"WD={WORKING_DIRECTORY}  "
        f"API: key={api_key_hint} base={QWEN_CONFIG.get('base_url', '')} model={QWEN_CONFIG.get('model', 'qwen-max')}\n"
        f"\n"
        f"## ⚠️ Mandatory Tool Calling Rule\n"
        f"You MUST call a tool in EVERY response — this is a hard constraint enforced at inference time.\n"
        f"You CANNOT output plain text. If you want to reply to the user, call finish_task with reply=...\n"
        f"Even for simple acknowledgements like 'OK' or 'Hello', use finish_task(reply='OK', summary='ok').\n"
        f"\n"
        f"## Workflow\n"
        f"1. Scaffold dirs with create_directory (e.g. {WORKING_DIRECTORY}/project, .../project/models, ...)\n"
        f"2. Write files top-down: models→routes→app.py. Each file MUST be complete, no stubs.\n"
        f"3. Verify: list_directory + validate_python_syntax for each .py\n"
        f"4. Done → finish_task(summary='what was built + how to run', reply='friendly response to user')\n"
        f"\n"
        f"## Rules\n"
        f"- Absolute paths only: {WORKING_DIRECTORY}/...\n"
        f"- One tool per call. Never write placeholder code.\n"
        f"- Tool fails ≥3x consecutively → finish_task with error, do NOT retry.\n"
        f"- ALWAYS output tool_calls — NEVER plain text. This is enforced by the inference engine.\n"
    )


def _load_skill_context() -> str:
    """加载 Skill 知识库 — 仅保留首句，工具细节由 Function Calling Schema 提供"""
    if not SKILLS_LOCATOR_PATH or not os.path.exists(SKILLS_LOCATOR_PATH):
        return ""

    try:
        with open(SKILLS_LOCATOR_PATH, "r", encoding="utf-8") as f:
            skills_data = json.load(f)

        items = []
        for key, value in skills_data.items():
            if key in ('version', 'description', 'statistics'):
                continue
            if isinstance(value, dict) and 'description' in value:
                desc = value['description']
                # 只取第一句（到第一个句号/适用场景/典型请求为止）
                for cut in ('。', '适用场景', '典型请求'):
                    idx = desc.find(cut)
                    if idx > 0:
                        desc = desc[:idx]
                        break
                items.append(f"- {key}: {desc[:120]}")
        return "## Skills\n" + "\n".join(items) if items else ""
    except Exception:
        return ""


def _is_failure(result_content: str) -> bool:
    """判断工具执行结果是否为失败。
    关键：如果明确包含 "status": "success" 则不是失败，即使响应中有 'error' 字样。
    """
    content_lower = result_content.lower()

    # 先检查是否明确成功 —— 有 success 状态就不算失败
    if '"status": "success"' in content_lower or '"status":"success"' in content_lower:
        return False

    # 失败标记
    failure_markers = [
        '"status": "error"',
        '"status": "failed"',
        '"status": "timeout"',
        'connection refused',
        '未找到工具',
        '导入模块失败',
        'blender not running',
        'could not connect',
    ]
    return any(marker in content_lower for marker in failure_markers)


def _format_tool_print(func_name: str, args: Dict[str, Any]) -> str:
    """格式化工具调用日志"""
    if func_name == "write_file":
        fp = args.get("file_path", "?")
        return f"[WRITE] {fp}"
    elif func_name == "execute_command":
        cmd = args.get("command", "?")
        return f"[CMD] {cmd[:60]}"
    elif func_name == "process_image":
        op = args.get("operation", "?")
        prompt = args.get("text_prompt", args.get("image_path", ""))
        return f"[IMAGE] {op}: {str(prompt)[:50]}"
    elif func_name == "browser_automation":
        task = args.get("task", "?")
        return f"[BROWSER] {task[:60]}"
    elif func_name == "blender_operation":
        code = args.get("code", "?")
        return f"[BLENDER] {code[:60]}"
    elif func_name == "finish_task":
        return "[FINISH]"
    else:
        return f"[{func_name}]"


# ============================================================
#  跨轮次记忆：加载 / 保存
# ============================================================

def _load_conversation() -> List[Dict]:
    """从文件加载上一轮的完整对话历史"""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"{YELLOW}[WARN] Failed to load history: {e}{RESET}")
        return []


def _save_conversation(messages: List[Dict]):
    """保存对话历史到文件，超出上限时只保留最近的"""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        if len(messages) > MAX_HISTORY_MESSAGES:
            print(f"{YELLOW}[MEM] Trimming history from {len(messages)} to {MAX_HISTORY_MESSAGES} messages{RESET}")
            messages = messages[-MAX_HISTORY_MESSAGES:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{YELLOW}[WARN] Failed to save history: {e}{RESET}")


def _compact_history(messages: List[Dict], llm: LLMChat) -> List[Dict]:
    """
    压缩对话历史：用 LLM 生成摘要替代详细消息链。

    策略：
      1. 提取 user/assistant 关键文本（跳过冗长的 tool 结果）
      2. 调 LLM 生成 300 token 内摘要
      3. 返回 [摘要 system 消息] + [最近 6 条消息保留上下文]
    """
    if len(messages) < 10:
        return messages  # 太少不压缩

    # 构建摘要输入：只取 user + assistant 文本，略过工具结果
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

    if not lines:
        return messages

    try:
        summary = llm.chat_no_memory(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the conversation below. Include:\n"
                        "1) What was built/accomplished (files, dirs, tasks)\n"
                        "2) Key decisions made\n"
                        "3) Current state and anything pending\n"
                        "Under 300 tokens. Use bullet points."
                    ),
                },
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.3,
            max_tokens=400,
        )

        compressed = [
            {
                "role": "system",
                "content": f"[HISTORY COMPACTED]\n{summary}",
            }
        ]

        # 保留最近 6 条消息维持即刻上下文
        keep = messages[-6:] if len(messages) > 6 else messages
        compressed.extend(keep)

        print(f"{CYAN}[COMPACT] {len(messages)} → {len(compressed)} msg (+{len(summary)} chars){RESET}")
        return compressed

    except Exception as e:
        print(f"{RED}[COMPACT] Failed: {e}{RESET}")
        return messages


# ============================================================

def run_agent_v2(user_input: str = None, max_iterations: int = 15):
    """
    主运行循环 —— Function Calling 版本 + 防死循环

    流程:
      用户输入 → LLM (with tools) → tool_calls → 执行 → 结果反馈 → LLM → ...
      直到 finish_task 被调用，或连续失败触发熔断
    """
    # ---- 初始化 ----
    llm = LLMChat(
        api_key=QWEN_CONFIG.get("api_key", ""),
        base_url=QWEN_CONFIG.get("base_url", ""),
        model=QWEN_CONFIG.get("model", "qwen-max"),
        max_tokens=QWEN_CONFIG.get("max_tokens", 3000),
        temperature=QWEN_CONFIG.get("temperature", 0.7),
    )

    executor = FunctionCallingExecutor(WORKING_DIRECTORY)
    tools = get_tool_schemas()
    system_prompt = _load_system_prompt()
    skill_context = _load_skill_context()
    if skill_context:
        system_prompt += skill_context

    # ---- 加载跨轮次记忆 ----
    messages = _load_conversation()
    if messages:
        print(f"{CYAN}[MEM] Loaded {len(messages)} messages from history{RESET}")
    else:
        print(f"{CYAN}[MEM] No previous history — starting fresh{RESET}")

    # ---- 交互模式 ----
    if user_input is None:
        print(f"\n{CYAN}{'='*60}{RESET}")
        print(f"{CYAN}  SmartAgent V2 - Function Calling Mode{RESET}")
        print(f"{CYAN}  Type 'exit'/'quit' to quit, '/compact' to compress history{RESET}")
        print(f"{CYAN}{'='*60}{RESET}\n")

    while True:
        if user_input is None:
            try:
                user_input = input(f"{GREEN}You: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Goodbye!{RESET}")
                break

            if user_input.lower() in ("exit", "quit", "quit()"):
                print(f"{YELLOW}Goodbye!{RESET}")
                break
            if not user_input:
                continue

        # ---- /compact 命令：压缩历史 ----
        if user_input.strip().lower() == "/compact":
            if len(messages) < 10:
                print(f"{YELLOW}[COMPACT] Only {len(messages)} messages — need at least 10{RESET}")
            else:
                messages = _compact_history(messages, llm)
                _save_conversation(messages)
            user_input = None
            continue

        print(f"{BLUE}Thinking...{RESET}")

        # ---- 对话循环：在历史基础上追加新消息 ----
        messages.append({"role": "user", "content": user_input})
        iteration = 0
        task_finished = False

        # 防死循环：追踪每个工具的连续失败次数
        failure_counts: Dict[str, int] = defaultdict(int)
        last_tool_name: Optional[str] = None

        while iteration < max_iterations and not task_finished:
            iteration += 1

            # ---- 熔断检查：同一工具连续失败 >= MAX_CONSECUTIVE_FAILURES ----
            # 注意：必须用 list() 拷贝，因为循环体内可能修改 failure_counts
            tripped_tools = [
                name for name, count in list(failure_counts.items())
                if count >= MAX_CONSECUTIVE_FAILURES
            ]
            for tool_name in tripped_tools:
                print(f"{RED}[BREAK] Tool '{tool_name}' failed {failure_counts[tool_name]}x consecutively - forcing stop{RESET}")
                messages.append({
                    "role": "system",
                    "content": (
                        f"CRITICAL: The tool '{tool_name}' has failed {failure_counts[tool_name]} times in a row. "
                        f"Do NOT call it again. Call finish_task with an honest summary of what went wrong."
                    )
                })
                # 重置该工具的计数（避免再次触发）
                failure_counts.pop(tool_name, None)

            # 调用 LLM（推理时强制约束：tool_choice="required" 确保模型必须输出 tool_calls）
            try:
                response = llm.chat_with_tools(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                    tool_choice="required",
                )
            except Exception as e:
                print(f"{RED}[ERROR] LLM call failed: {e}{RESET}")
                break

            # 提取 tool_calls
            tool_calls, text_content = FunctionCallingExecutor.extract_tool_calls(response)

            if tool_calls:
                # 有工具调用
                assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_msg)

                # 预估耗时工具列表（需要给用户进度提示）
                _slow_tools = {"browser_automation", "process_image", "blender_operation"}

                # 打印即将执行的操作
                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                    tag = f"{CYAN}[RUN]{RESET}" if func_name in _slow_tools else f"{GREEN}[RUN]{RESET}"
                    print(f"  {tag} {_format_tool_print(func_name, args)}")

                # 执行工具（耗时操作在此）
                import time
                t_start = time.time()
                results = executor.execute_tool_calls(tool_calls)
                t_elapsed = time.time() - t_start

                # 处理结果：检查失败、打印日志
                for i, tc in enumerate(tool_calls):
                    func_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}

                    result_content = results[i].get("content", "") if i < len(results) else ""
                    is_fail = _is_failure(result_content)

                    # 结果日志（带耗时）
                    elapsed_str = f" ({t_elapsed:.1f}s)" if t_elapsed > 2 else ""
                    tag = f"{RED}[FAIL]{RESET}" if is_fail else f"{GREEN}[OK]{RESET}"
                    result_len = len(result_content)
                    size_hint = f" | {result_len} chars" if result_len > 100 else ""
                    print(f"  {tag} {_format_tool_print(func_name, args)}{elapsed_str}{size_hint}")

                    # 失败追踪
                    if func_name == last_tool_name and is_fail:
                        failure_counts[func_name] += 1
                    elif is_fail:
                        failure_counts[func_name] = 1
                    else:
                        # 成功 → 重置所有计数
                        failure_counts.clear()

                    last_tool_name = func_name

                    # finish_task 检测
                    if func_name == "finish_task" or results[i].get("_finish"):
                        task_finished = True
                        try:
                            finish_args = json.loads(tc["function"]["arguments"])
                            reply = finish_args.get("reply", finish_args.get("summary", ""))
                        except Exception:
                            reply = ""
                        if reply:
                            print(f"\n{BOLD}{GREEN}Agent: {reply}{RESET}")
                        results[i]["_finish"] = True

                # 追加工具结果到消息
                for r in results:
                    content = r.get("content", "")
                    # 截断过长内容（避免 token 爆炸）
                    if len(content) > 1000:
                        content = content[:1000] + "\n... (truncated)"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": r["tool_call_id"],
                        "content": content,
                    })

            elif text_content:
                # 纯文本响应（tool_choice="required" 下极少触发，作为兜底）
                messages.append({"role": "assistant", "content": text_content})
                print(f"\n{BOLD}{BLUE}Agent: {text_content}{RESET}")
                break

            else:
                print(f"{YELLOW}[WARN] Empty response from model{RESET}")
                break

        # 循环结束原因
        if iteration >= max_iterations and not task_finished:
            print(f"{YELLOW}[WARN] Max iterations ({max_iterations}) reached{RESET}")
        elif not task_finished and not text_content:
            pass  # 已经打印过原因

        # 始终继续循环（交互模式下等待下一个输入）
        if user_input is not None and len(sys.argv) > 1:
            # 命令行参数模式：单次任务完成后也继续循环
            pass

        # ---- 保存跨轮次记忆 ----
        _save_conversation(messages)

        user_input = None


def _cleanup():
    """退出时清除跨轮次记忆"""
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            print(f"{YELLOW}[CLEANUP] Conversation history cleared: {HISTORY_FILE}{RESET}")
        # 如果 history 目录为空则一并删除
        if os.path.isdir(HISTORY_DIR) and not os.listdir(HISTORY_DIR):
            os.rmdir(HISTORY_DIR)
    except Exception:
        pass


# 注册退出清理
atexit.register(_cleanup)


# ============================================================================
# 主入口
# ============================================================================
if __name__ == "__main__":
    load_config()
    print(f"{CYAN}SmartAgent V2 - Function Calling Mode{RESET}")
    print(f"{CYAN}  Working directory: {WORKING_DIRECTORY}{RESET}")
    print(f"{CYAN}  Type 'exit'/'quit' to quit, or just ask a question{RESET}")
    print()

    if len(sys.argv) > 1 and sys.argv[1] not in ("--interactive", "-i"):
        task = " ".join(sys.argv[1:])
        print(f"{GREEN}Task: {task}{RESET}")
        run_agent_v2(task)
    else:
        run_agent_v2()
