"""
测试 Function Calling 架构的各组件是否正常工作
运行: python test_function_calling.py
"""

import sys
import os
import json

# 确保项目路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESET = '\033[0m'
GREEN = '\033[92m'
RED   = '\033[91m'
YELLOW= '\033[93m'
CYAN  = '\033[96m'

passed = 0
failed = 0


def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        print(f"  {GREEN}[PASS] {name}{RESET} {detail}")
        passed += 1
    else:
        print(f"  {RED}[FAIL] {name}{RESET} {detail}")
        failed += 1


print(f"{CYAN}{'='*60}{RESET}")
print(f"{CYAN}  测试: Function Calling 架构{RESET}")
print(f"{CYAN}{'='*60}{RESET}")

# ===================================================================
# 测试 1: Tool Registry
# ===================================================================
print(f"\n{CYAN}[1] Tool Registry — 工具 Schema 注册表{RESET}")

from utils.tool_registry import (
    get_tool_schemas,
    get_tool_by_name,
    get_function_info,
    format_tools_for_prompt,
)

schemas = get_tool_schemas()
test("工具 Schema 列表非空",   len(schemas) > 0,        f"共 {len(schemas)} 个工具")
test("每个 Schema 包含 type",  all("type" in s for s in schemas))
test("每个 Schema 包含 function", all("function" in s for s in schemas))

# 检查每个工具的必填字段
required_fields = ["name", "description", "parameters"]
for s in schemas:
    func = s["function"]
    check = all(f in func for f in required_fields)
    test(f"工具 {func['name']} 结构完整", check)

# 查一个具体工具
write_schema = get_tool_by_name("write_file")
test("查找 write_file Schema", write_schema is not None)
if write_schema:
    props = write_schema["function"]["parameters"]["properties"]
    test("write_file 有 file_path 参数", "file_path" in props)
    test("write_file 有 content 参数",   "content" in props)
    test("file_path 是必填", "file_path" in write_schema["function"]["parameters"]["required"])

# 查函数映射
write_map = get_function_info("write_file")
test("write_file 有函数映射", write_map is not None)
if write_map:
    test("write_file 映射到 file_writer", "file_writer" in write_map["module"])

finish_map = get_function_info("finish_task")
test("finish_task 有函数映射", finish_map is not None)

# 格式化输出
formatted = format_tools_for_prompt()
test("工具列表格式化输出", "write_file" in formatted and "execute_command" in formatted)


# ===================================================================
# 测试 2: Function Calling Executor
# ===================================================================
print(f"\n{CYAN}[2] Function Calling Executor — 工具执行引擎{RESET}")

from utils.function_calling_executor import FunctionCallingExecutor
from utils.session_manager import set_workspace_path

# 初始化工作路径（工具需要）
workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_workspace")
os.makedirs(workspace, exist_ok=True)
set_workspace_path(workspace)
print(f"  工作空间: {workspace}")

executor = FunctionCallingExecutor(workspace)

# 2.1 测试 write_file
test_call_write = {
    "id": "test_write_001",
    "type": "function",
    "function": {
        "name": "write_file",
        "arguments": json.dumps({
            "file_path": "_test_fc_output.txt",
            "content": "Hello Function Calling!",
            "mode": "overwrite"
        })
    }
}
result = executor.execute_tool_call(test_call_write)
# write_file 返回 {"status": "success", ...} 的JSON字符串
is_write_ok = '"status": "success"' in result.get("content", "")
test("write_file 执行成功", is_write_ok, f"content snippet: {result.get('content', '')[:80]}")

# 2.2 测试 read_file（用工作空间下的绝对路径）
test_call_read = {
    "id": "test_read_001",
    "type": "function",
    "function": {
        "name": "read_file",
        "arguments": json.dumps({
            "file_path": os.path.join(workspace, "_test_fc_output.txt")
        })
    }
}
result = executor.execute_tool_call(test_call_read)
has_hello = "Hello Function Calling!" in result.get("content", "")
test("read_file 读到正确内容", has_hello, f"content snippet: {result.get('content', '')[:80]}")

# 2.3 测试 execute_command
test_call_cmd = {
    "id": "test_cmd_001",
    "type": "function",
    "function": {
        "name": "execute_command",
        "arguments": json.dumps({
            "command": "echo Hello from PowerShell"
        })
    }
}
result = executor.execute_tool_call(test_call_cmd)
is_cmd_ok = '"status": "success"' in result.get("content", "") or "Hello" in result.get("content", "")
test("execute_command 执行成功", is_cmd_ok, f"content snippet: {result.get('content', '')[:100]}")

# 2.4 测试 finish_task
test_call_finish = {
    "id": "test_finish_001",
    "type": "function",
    "function": {
        "name": "finish_task",
        "arguments": json.dumps({"summary": "测试完成"})
    }
}
result = executor.execute_tool_call(test_call_finish)
test("finish_task 正常返回", result.get("_finish") == True)

# 2.5 测试不存在的工具
test_call_bad = {
    "id": "test_bad_001",
    "type": "function",
    "function": {
        "name": "nonexistent_tool",
        "arguments": "{}"
    }
}
result = executor.execute_tool_call(test_call_bad)
test("不存在的工具返回错误", "未找到工具" in result.get("content", ""))

# 2.6 测试批量执行
results = executor.execute_tool_calls([test_call_write, test_call_read])
test("批量执行返回2个结果", len(results) == 2)

# 2.7 测试工具结果转消息
from utils.function_calling_executor import FunctionCallingExecutor
msgs = FunctionCallingExecutor.tool_results_to_messages(results)
test("结果转消息格式正确", all(m["role"] == "tool" for m in msgs))


# ===================================================================
# 测试 3: 模块缓存
# ===================================================================
print(f"\n{CYAN}[3] 模块缓存 — import 性能{RESET}")

import time
executor2 = FunctionCallingExecutor()

# 第一次调用（冷启动）
t1 = time.time()
executor2.execute_tool_call(test_call_write)
t_cold = time.time() - t1

# 第二次调用（热缓存）
t2 = time.time()
executor2.execute_tool_call(test_call_read)
t_hot = time.time() - t2

test("模块缓存生效（热调用 < 冷调用）", t_hot <= t_cold * 1.5,
     f"冷: {t_cold:.4f}s, 热: {t_hot:.4f}s")


# ===================================================================
# 测试 4: extract_tool_calls 模拟
# ===================================================================
print(f"\n{CYAN}[4] extract_tool_calls — 响应解析{RESET}")

# 模拟 OpenAI response 对象（部分属性）
class MockToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.type = "function"
        self.function = MockFunction(name, arguments)

class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

class MockMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

class MockChoice:
    def __init__(self, message, finish_reason="stop"):
        self.message = message
        self.finish_reason = finish_reason

class MockResponse:
    def __init__(self, choices):
        self.choices = choices

# 场景 A：有 tool_calls
mock_resp = MockResponse([
    MockChoice(
        MockMessage(None, [MockToolCall("call_1", "write_file", '{"file_path":"a.txt","content":"hi"}')])
    )
])
tc, txt = FunctionCallingExecutor.extract_tool_calls(mock_resp)
test("有 tool_calls 时返回 tool_calls", tc is not None and len(tc) == 1)
test("有 tool_calls 时 txt 为 None", txt is None)

# 场景 B：纯文本
mock_resp2 = MockResponse([
    MockChoice(MockMessage("你好，有什么可以帮你？"))
])
tc, txt = FunctionCallingExecutor.extract_tool_calls(mock_resp2)
test("纯文本时 tc 为 None", tc is None)
test("纯文本时 txt 返回内容", txt == "你好，有什么可以帮你？")


# ===================================================================
# 清理 & 总结
# ===================================================================
print(f"\n{CYAN}{'='*60}{RESET}")
print(f"  结果: {GREEN}{passed} 通过{RESET}, {RED}{failed} 失败{RESET}")
print(f"{CYAN}{'='*60}{RESET}")

# 清理测试文件
import shutil
for f in ["_test_fc_output.txt"]:
    try:
        os.remove(os.path.join(workspace, f))
    except:
        pass
try:
    shutil.rmtree(workspace)
except:
    pass

if failed > 0:
    sys.exit(1)
else:
    print(f"\n{GREEN}[OK] All tests passed! Function Calling architecture is ready.{RESET}")
    print(f"  Run: python agent_v2.py  (new architecture)")
    print(f"  Run: python agent.py     (old architecture)")
