"""
QwenPaw 任务执行客户端

支持审批确认功能 — 当 Agent 需要执行敏感操作时，会暂停等待用户确认。

一行调用:
    from qwenpaw_client import run
    result = run("帮我整理桌面文件，按类型分类")
    print(result)
"""

import io
import json
import sys
import time
import urllib.request
import urllib.error
from typing import Optional, Callable
import subprocess
import socket

GREEN = '\033[92m'     # 绿色
RESET = '\033[0m'      # 重置所有样式


# Windows GBK 终端兼容
if sys.stdout.encoding and sys.stdout.encoding.upper() in ("GBK", "GB2312", "CP936"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# SSE 事件类型说明（基于真实抓包分析）
# ---------------------------------------------------------------------------
# object=response  → 会话状态: created → in_progress → completed / failed
# object=message   → 一条消息:
#   type=message       → 普通助手回复
#   type=plugin_call   → 工具调用开始
#   type=plugin_call_output → 工具调用结果返回
# object=content   → 消息内容块
#   type=text          → 文本（delta 流式，delta=true 时还有后续）
#   type=data          → 工具调用参数/结果（call_id, name, arguments/output）
#
# 审批事件: 当 message 的 metadata.message_type == "tool_guard_approval"
#   关键字段: metadata.approval_request_id (审批 UUID)
#            metadata.tool_name
#            metadata.findings_summary
#            metadata.tool_params
#            metadata.severity


class PendingApproval:
    """等待用户确认的安全审批请求"""

    def __init__(self, request_id: str, metadata: dict):
        self.request_id = request_id
        self.tool_name = metadata.get("tool_name", "未知工具")
        self.severity = metadata.get("severity", "UNKNOWN")
        self.findings_summary = metadata.get("findings_summary", "")
        self.findings_count = metadata.get("findings_count", 0)
        self.tool_params = metadata.get("tool_params", {})
        self.session_id = metadata.get("session_id", "")
        self.agent_id = metadata.get("agent_id", "")

    @property
    def command(self) -> str:
        """如果是 execute_shell_command，提取 command 参数"""
        return self.tool_params.get("command", "")

    def __repr__(self) -> str:
        parts = [
            f"[安全审批] 工具: {self.tool_name}",
            f"  严重性: {self.severity}",
        ]
        if self.findings_summary:
            parts.append(f"  风险: {self.findings_summary[:200]}")
        if self.command:
            parts.append(f"  命令: {self.command[:200]}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------


class QwenPawClient:
    """QwenPaw REST API 客户端

    特性:
    - 任务自动执行
    - SSE 流式文本接收
    - 安全审批确认（工具保护）
    - 多轮会话
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8088",
        agent_id: str = "default",
        auth_token: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/api/console/chat"
        self.version_url = f"{self.base_url}/api/version"
        self.approve_url = f"{self.base_url}/api/approval/approve"
        self.deny_url = f"{self.base_url}/api/approval/deny"
        self.approval_list_url = f"{self.base_url}/api/approval/list"
        self.agent_id = agent_id
        self.auth_token = auth_token

    def _build_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Agent-Id": self.agent_id,
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    # -----------------------------------------------------------
    # 核心：执行任务
    # -----------------------------------------------------------

    # ---- 颜色常量（日志输出用） ----
    _CYAN = '\033[96m'
    _YELLOW = '\033[93m'
    _RED = '\033[91m'
    _BOLD = '\033[1m'
    _DIM = '\033[2m'

    def _log(self, msg: str, color: str = "", tag: str = "") -> None:
        """带样式的日志输出，用 stderr 避免干扰 stdout 返回值"""
        if not self._verbose:
            return
        ts = time.strftime("%H:%M:%S")
        tag_part = f" {tag}" if tag else ""
        reset = '\033[0m'
        print(f"{self._DIM}{ts}{reset} {color}{msg}{reset}{tag_part}", file=sys.stderr, flush=True)

    def _log_state(self, status: str, elapsed: float) -> None:
        """输出会话状态变更"""
        icon = {"created": "🟢", "in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(status, "⚪")
        self._log(f"{icon} 会话状态: {self._BOLD}{status}{self._RESET}", color=self._CYAN, tag=f"({elapsed:.1f}s)")

    _RESET = '\033[0m'

    def run(
        self,
        task: str,
        session_id: Optional[str] = None,
        user_id: str = "api-user",
        timeout: int = 600,
        verbose: bool = False,
        on_approval: Optional[Callable[[PendingApproval], str]] = None,
    ) -> str:
        """
        执行任务，自动处理审批确认。

        参数:
            task:       用户需求，如 "帮我删除桌面的 tmp 文件"
            session_id: 会话ID，留空自动生成
            user_id:    用户标识
            timeout:    超时秒数（默认600秒）
            verbose:    是否打印动态日志（推荐开启，默认 False 保持静默兼容）
            on_approval: 审批回调函数。
                         接收 PendingApproval，返回 "approve" 或 "deny"。
                         默认：打印审批信息并让用户输入 y/n。

        返回:
            Agent 最终回复的文本
        """
        self._verbose = verbose
        _t_start = time.perf_counter()

        if session_id is None:
            session_id = f"task-{int(time.time())}"

        self._log(f"🚀 开始任务: {self._BOLD}{task[:120]}{'…' if len(task) > 120 else ''}{self._RESET}", color=self._CYAN)
        self._log(f"📋 session_id={session_id}  timeout={timeout}s  agent={self.agent_id}", color=self._DIM)

        payload = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": task}],
                }
            ],
            "session_id": session_id,
            "user_id": user_id,
            "channel": "console",
        }

        req = urllib.request.Request(
            self.chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(),
            method="POST",
        )

        assistant_texts: list[str] = []
        current_delta: list[str] = []
        final_status = ""
        root_session_id = session_id
        tool_call_active = False
        event_count = 0

        try:
            self._log(f"🌐 连接 {self.chat_url} …", color=self._DIM)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                self._log(f"📡 SSE 连接建立成功", color=GREEN)
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue

                    event = json.loads(line[6:])
                    obj = event.get("object", "")
                    status = event.get("status", "")
                    etype = event.get("type", "")
                    event_count += 1

                    # ---- 追踪 session_id ----
                    if event.get("session_id"):
                        root_session_id = event["session_id"]

                    # ---- 追踪最终状态 ----
                    if obj == "response":
                        final_status = status

                    # ---- 状态变更日志 ----
                    if obj == "response":
                        elapsed = time.perf_counter() - _t_start
                        self._log_state(status, elapsed)

                    # ---- 提取文本 delta 并实时输出 ----
                    if obj == "content" and etype == "text":
                        text_chunk = event.get("text", "")
                        delta = event.get("delta")
                        if text_chunk:
                            current_delta.append(text_chunk)
                            # 流式实时打印文本
                            if self._verbose and text_chunk:
                                print(f"{GREEN}{text_chunk}{self._RESET}", file=sys.stderr, end="", flush=True)
                        if delta is None or delta is False or status == "completed":
                            if current_delta:
                                full = "".join(current_delta)
                                assistant_texts.append(full)
                                current_delta = []
                            if self._verbose:
                                print(file=sys.stderr, flush=True)  # 换行

                    # ---- 工具调用日志 ----
                    if obj == "content" and etype == "data":
                        name = event.get("name", "")
                        args_raw = event.get("arguments", "")
                        if name:
                            try:
                                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                                cmd_snippet = ""
                                if isinstance(args, dict):
                                    cmd = args.get("command", args.get("url", args.get("path", "")))
                                    if cmd:
                                        cmd_snippet = f"  {str(cmd)[:150]}"
                                self._log(f"🔧 调用工具: {self._BOLD}{name}{self._RESET}{cmd_snippet}", color=self._YELLOW)
                                tool_call_active = True
                            except json.JSONDecodeError:
                                self._log(f"🔧 调用工具: {name}", color=self._YELLOW)

                    # ---- 工具结果日志 ----
                    if obj == "content" and etype == "data" and event.get("output"):
                        output = event["output"]
                        snippet = str(output)[:120].replace("\n", " ")
                        self._log(f"📎 工具结果: {snippet}{'…' if len(str(output)) > 120 else ''}", color=self._DIM)

                    # ---- 检测安全审批事件 ----
                    if (
                        obj == "message"
                        and (event.get("metadata") or {}).get("message_type") == "tool_guard_approval"
                    ):
                        meta = event["metadata"]
                        request_id = meta.get("approval_request_id", "")

                        if request_id:
                            approval = PendingApproval(request_id, meta)
                            self._log(f"🔒 安全审批: {approval.tool_name} (严重性: {approval.severity})", color=self._RED)
                            decision = self._handle_approval(approval, on_approval)

                            if decision == "approve":
                                self._send_approve(request_id, root_session_id)
                                self._log(f"✅ 审批已批准", color=GREEN, tag=f"({request_id[:8]})")
                            else:
                                self._send_deny(request_id, root_session_id, "用户拒绝")
                                self._log(f"❌ 审批已拒绝", color=self._RED, tag=f"({request_id[:8]})")
                        else:
                            self._log(f"⚠️ 收到审批事件但缺少 request_id", color=self._YELLOW)

                    # ---- 错误 ----
                    if event.get("error"):
                        err_msg = event["error"].get("message", "未知错误")
                        self._log(f"💥 Agent 错误: {err_msg}", color=self._RED)
                        raise RuntimeError(f"Agent 执行出错: {err_msg}")

                    # ---- 完成 ----
                    if obj == "response" and status == "completed":
                        break

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            self._log(f"💥 HTTP {e.code}: {body}", color=self._RED)
            raise RuntimeError(f"HTTP {e.code}: {body}") from e

        elapsed = time.perf_counter() - _t_start
        if final_status == "failed":
            self._log(f"❌ 任务失败，耗时 {elapsed:.1f}s", color=self._RED)
            raise RuntimeError("任务执行失败，请检查 Agent 日志")

        result = "\n".join(assistant_texts).strip()
        char_count = len(result)
        self._log(f"✅ 任务完成 | 耗时 {elapsed:.1f}s | SSE事件 {event_count} 条 | 回复 {char_count} 字符", color=GREEN)
        return result

    # -----------------------------------------------------------
    # 审批处理
    # -----------------------------------------------------------

    def _handle_approval(
        self,
        approval: PendingApproval,
        callback: Optional[Callable[[PendingApproval], str]] = None,
    ) -> str:
        """处理审批请求，返回 'approve' 或 'deny'"""
        if callback:
            return callback(approval)

        # 默认：打印到控制台让用户输入
        print("\n" + "=" * 55)
        print("  🔒 安全审批请求")
        print("=" * 55)
        print(f"  工具: {approval.tool_name}")
        print(f"  严重性: {approval.severity}")
        if approval.findings_summary:
            print(f"  风险: {approval.findings_summary[:300]}")
        if approval.command:
            print(f"  命令: {approval.command[:300]}")
        print("-" * 55)

        while True:
            choice = input("  批准? (y=批准 / n=拒绝): ").strip().lower()
            if choice in ("y", "yes", "approve"):
                return "approve"
            elif choice in ("n", "no", "deny"):
                return "deny"
            print("  请输入 y 或 n")

    def _send_approve(self, request_id: str, session_id: str) -> dict:
        """调用审批 API 批准"""
        payload = {"request_id": request_id, "session_id": session_id}
        return self._call_approval_api(self.approve_url, payload)

    def _send_deny(self, request_id: str, session_id: str, reason: str = "") -> dict:
        """调用审批 API 拒绝"""
        payload = {
            "request_id": request_id,
            "session_id": session_id,
            "reason": reason,
        }
        return self._call_approval_api(self.deny_url, payload)

    def _call_approval_api(self, url: str, payload: dict) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**self._build_headers(), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"审批 API 失败 (HTTP {e.code}): {body}") from e

    def list_pending_approvals(self, session_id: Optional[str] = None) -> list:
        """列出待审批的请求"""
        params = f"?session_id={session_id}" if session_id else ""
        req = urllib.request.Request(
            f"{self.approval_list_url}{params}",
            headers=self._build_headers(),
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("pending_approvals", [])

    # -----------------------------------------------------------
    # 多轮对话
    # -----------------------------------------------------------

    def chat(
        self,
        message: str,
        session_id: str,
        on_approval: Optional[Callable[[PendingApproval], str]] = None,
    ) -> str:
        """多轮对话，使用 session_id 保持上下文"""
        return self.run(
            message,
            session_id=session_id,
            on_approval=on_approval,
        )

    # -----------------------------------------------------------
    # 工具方法
    # -----------------------------------------------------------

    def health_check(self) -> bool:
        """检查 QwenPaw 服务是否在线"""
        try:
            req = urllib.request.Request(self.version_url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False


# ============================================================
# 快捷函数
# ============================================================

_client_instance: Optional[QwenPawClient] = None


def run(task: str, **kwargs) -> str:
    """
    一行调用::

        from qwenpaw_client import run
        result = run("帮我搜索今天的科技新闻")
        print(result)

    可选参数:
        base_url       - QwenPaw 服务地址，默认 http://localhost:8088
        agent_id       - Agent ID，默认 default
        auth_token     - 认证令牌（远程访问时需要）
        session_id     - 会话 ID
        user_id        - 用户标识
        timeout        - 超时秒数
        verbose        - 是否打印调试信息
        on_approval    - 审批回调函数，传入 PendingApproval，返回 "approve"/"deny"
    """
    global _client_instance
    _log_start_tag = f"[▶ execute_browser_command] 任务: {task[:80]}{'…' if len(task) > 80 else ''}"
    print(f"{_log_start_tag}", file=sys.stderr, flush=True)

    if _client_instance is None or any(
        k in kwargs for k in ("base_url", "agent_id", "auth_token")
    ):
        _client_instance = QwenPawClient(
            base_url=kwargs.pop("base_url", "http://localhost:8088"),
            agent_id=kwargs.pop("agent_id", "default"),
            auth_token=kwargs.pop("auth_token", ""),
        )

    try:
        result = _client_instance.run(task, **kwargs)
        print(f"[✅ execute_browser_command 成功] 返回 {len(result)} 字符", file=sys.stderr, flush=True)
        return result
    except Exception as e:
        print(f"[❌ execute_browser_command 失败] {e}", file=sys.stderr, flush=True)
        raise


def check_port(port, host='127.0.0.1'):
    """检查端口是否开放"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def run_main():
    client = QwenPawClient()

    if not client.health_check():
        print("[FAIL] QwenPaw 服务未启动！请先运行: qwenpaw app")
        print("启动Qwenpaw...")
        
        # Popen不会等待进程结束，直接返回
        process = subprocess.Popen(
            ['qwenpaw', 'app'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待服务启动（轮询检查）
        print("等待服务启动...")
        for i in range(30):  # 最多等待30秒
            time.sleep(1)
            if client.health_check():
                print(f"{GREEN}[OK] QwenPaw 服务已启动!{RESET}")
                break
        else:
            print("[FAIL] QwenPaw 服务启动失败")
            
    # ---- 示例 1: 自动批准 ----
    # print("=== 示例 1: 始终自动批准 ===")
    # result = client.run(
    #     "查看桌面有哪些文件",
    #     on_approval=lambda req: "approve",
    # )
    # print(f"结果: {result}\n")

    # ---- 示例 2: 交互式审批（运行后等用户输入） ----
    print(f"{GREEN}[OK] QwenPaw 服务已启动!{RESET}")

    print("如果触发了安全审批，会在下面显示信息让你选择 y/n\n")

    result = client.run("去b站搜索python教程，显示浏览器页面")
    print(f"结果: {result}\n")   


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    run_main()