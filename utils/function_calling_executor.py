"""
Function Calling 执行器 —— 根据大模型返回的 tool_calls 精确执行对应方法

流程：
  大模型输出 tool_calls（结构化 JSON，不需要正则解析）
       ↓
  按 tool_name 查找 TOOL_FUNCTION_MAP
       ↓
  按 Schema 校验参数
       ↓
  调用对应函数 → 返回结果 → 反馈给大模型

替代了原来的 parse_json_string + execute_operations 组合。
"""

import json
import os
import importlib
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from utils.tool_registry import (
    get_function_info,
    get_tool_by_name,
    TOOL_FUNCTION_MAP,
)


class FunctionCallingExecutor:
    """
    Function Calling 执行器

    核心职责：
    1. 接收大模型返回的 tool_calls（OpenAI 标准格式）
    2. 按注册表定位对应函数
    3. 执行并返回结果
    """

    def __init__(self, workspace_path: str = None):
        self.workspace_path = workspace_path or "."
        self._module_cache: Dict[str, Any] = {}  # 缓存已导入的模块

        # 同步设置 session_manager 的全局工作空间（shell/命令工具依赖此全局变量）
        if self.workspace_path and self.workspace_path != ".":
            try:
                from utils.session_manager import set_workspace_path
                set_workspace_path(self.workspace_path)
            except Exception:
                pass
            try:
                from utils.web_controler.browser_engine import set_workspace_dir
                set_workspace_dir(self.workspace_path)
            except Exception:
                pass

    @staticmethod
    def extract_tool_calls(response) -> Tuple[List[Dict], Optional[str]]:
        """
        从 LLM 的 chat completion response 中提取 tool_calls 和文本内容

        Args:
            response: OpenAI chat completion response 对象

        Returns:
            (tool_calls: List[Dict], text_content: Optional[str])
            - tool_calls: 提取的工具调用列表（含 id, type, function 字段）
            - text_content: 如果模型返回了纯文本而非工具调用，返回文本内容；否则为 None
        """
        if response is None or not response.choices:
            return [], None

        choice = response.choices[0]
        message = choice.message

        # -- 优先提取 tool_calls --
        raw_calls = getattr(message, "tool_calls", None) or []
        if raw_calls:
            tool_calls = []
            for tc in raw_calls:
                tool_calls.append({
                    "id": getattr(tc, "id", ""),
                    "type": "function",
                    "function": {
                        "name": getattr(tc.function, "name", "") if hasattr(tc, "function") else "",
                        "arguments": getattr(tc.function, "arguments", "{}") if hasattr(tc, "function") else "{}",
                    },
                })
            return tool_calls, None

        # -- 无 tool_calls 时提取文本 --
        text = getattr(message, "content", None)
        if text and text.strip():
            if hasattr(choice, "finish_reason") and choice.finish_reason == "tool_calls":
                return [], None
            return [], text.strip()

        return [], None

    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个 tool_call

        Args:
            tool_call: OpenAI 格式的 tool_call，结构为:
                {
                    "id": "call_xxx",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"file_path": "...", "content": "..."}'
                    }
                }

        Returns:
            {"tool_call_id": "call_xxx", "role": "tool", "content": "执行结果"}
        """
        tool_call_id = tool_call.get("id", "")
        func_info = tool_call.get("function", {})
        func_name = func_info.get("name", "")

        # 解析参数（arguments 是 JSON 字符串）
        try:
            arguments = json.loads(func_info.get("arguments", "{}"))
        except json.JSONDecodeError as e:
            return self._error_result(tool_call_id, f"参数 JSON 解析失败: {e}")

        # 查找函数映射
        func_map = get_function_info(func_name)
        if not func_map:
            return self._error_result(tool_call_id, f"未找到工具: {func_name}")

        # ---- 自动注入工作目录 ----
        # 对图片生成等操作，如果未指定 output_path，自动使用工作目录
        if func_name == "process_image" and self.workspace_path:
            if "output_path" not in arguments or not arguments["output_path"]:
                import time
                ext_map = {"generate": "png", "convert": "jpg", "edit": "png"}
                operation = arguments.get("operation", "generate")
                ext = ext_map.get(operation, "png")
                default_name = f"generated_{int(time.time())}.{ext}"
                arguments["output_path"] = os.path.join(self.workspace_path, default_name)

        # 特殊处理：finish_task
        if func_name == "finish_task":
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "content": f"任务已完成: {arguments.get('summary', '')}",
                "_finish": True,
            }

        # ---- MCP 动态工具路由 ----
        if func_name.startswith("mcp__"):
            try:
                from MCPS import call_mcp_tool
                result = call_mcp_tool(func_name, arguments)
                content = json.dumps(result, ensure_ascii=False)
                return {
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "content": content,
                }
            except Exception as e:
                return self._error_result(tool_call_id, f"MCP 调用失败: {e}")

        # 获取模块和函数
        module_path = func_map["module"]
        function_name = func_map["function"]

        try:
            func = self._get_function(module_path, function_name)
        except Exception as e:
            return self._error_result(tool_call_id, f"加载函数失败 [{module_path}.{function_name}]: {e}")

        # 执行函数
        try:
            result = func(**arguments)
        except TypeError as e:
            return self._error_result(
                tool_call_id,
                f"参数不匹配: {e}\n期望参数: {self._get_param_names(func)}\n传入参数: {list(arguments.keys())}"
            )
        except Exception as e:
            return self._error_result(tool_call_id, f"执行异常: {e}")

        # 格式化结果
        return self._format_result(tool_call_id, result, func_name)

    def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量执行 tool_calls，按顺序执行（保持依赖关系）

        Returns:
            tool_results 列表，每个元素可直接作为 tool message 追加到对话
        """
        results = []
        for tc in tool_calls:
            result = self.execute_tool_call(tc)
            results.append(result)

            # 如果遇到 finish_task，停止后续执行
            if result.get("_finish"):
                break

        return results

    @staticmethod
    def tool_results_to_messages(tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将执行结果转换为可追加到对话的消息列表
        """
        messages = []
        for result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": result["content"],
            })
        return messages

    # ---- 内部方法 ----

    def _get_function(self, module_path: str, function_name: str):
        """获取函数对象，使用缓存"""
        cache_key = f"{module_path}.{function_name}"
        if cache_key in self._module_cache:
            return self._module_cache[cache_key]

        module = importlib.import_module(module_path)
        func = getattr(module, function_name)
        self._module_cache[cache_key] = func
        return func

    def _error_result(self, tool_call_id: str, error: str) -> Dict[str, Any]:
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": f"❌ 错误: {error}",
        }

    def _format_result(self, tool_call_id: str, result: Any, func_name: str) -> Dict[str, Any]:
        """格式化函数执行结果"""
        if isinstance(result, dict) and "status" in result:
            # 已经是格式化结果
            content = json.dumps(result, ensure_ascii=False, indent=2)
        elif result is None:
            content = f"[{func_name}] 执行成功"
        else:
            content = str(result)

        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": content,
        }

    @staticmethod
    def _get_param_names(func) -> List[str]:
        """获取函数参数名列表（用于错误提示）"""
        import inspect
        try:
            sig = inspect.signature(func)
            return [p.name for p in sig.parameters.values()]
        except Exception:
            return ["<无法获取>"]


# ============================================================================
# 便捷函数
# ============================================================================

def execute_tool_calls_simple(
    tool_calls: List[Dict],
    workspace_path: str = None
) -> List[Dict[str, Any]]:
    """便捷函数：批量执行 tool_calls"""
    executor = FunctionCallingExecutor(workspace_path)
    return executor.execute_tool_calls(tool_calls)


if __name__ == "__main__":
    # 测试
    executor = FunctionCallingExecutor()
    test_call = {
        "id": "test_001",
        "type": "function",
        "function": {
            "name": "write_file",
            "arguments": '{"file_path": "test.txt", "content": "Hello Function Calling!"}'
        }
    }
    result = executor.execute_tool_call(test_call)
    print(json.dumps(result, indent=2, ensure_ascii=False))
