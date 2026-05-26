"""
工具注册表 —— 集中管理所有可用工具的 JSON Schema 声明
核心理念：每个工具有精确的 Schema 定义，大模型通过 Native Function Calling
输出结构化 tool_call，系统按 Schema 校验后执行，不再依赖正则解析 JSON。

设计参考：QwenPaw 的工具声明机制 —— JSON Schema 作为"API 契约"
"""

from typing import Dict, List, Any, Callable, Optional
import json


# ============================================================================
# 工具 JSON Schema 定义
# 每个工具包含：name, description, parameters (JSON Schema)
# ============================================================================

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    # ======================== 文件操作工具 ========================
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write/create a file. Supports relative/absolute paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径，支持相对路径（相对于工作空间）或绝对路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文件内容"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "description": "写入模式：overwrite=覆盖, append=追加",
                        "default": "overwrite"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read entire file content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径，支持相对路径或绝对路径"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_lines",
            "description": "Read specific line range (1-based).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "起始行号（从1开始），None表示从头开始"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "结束行号，None表示到末尾"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_content",
            "description": "Replace text in file (exact match).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "old_content": {
                        "type": "string",
                        "description": "要替换的旧文本内容"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "新文本内容"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path", "old_content", "new_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List directory contents with optional recursion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "目录路径，默认当前工作空间",
                        "default": "."
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "最大递归深度，默认3",
                        "default": 3
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get file metadata (size, mtime) without reading content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create directory (auto-creates parents). For scaffolding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "要创建的目录路径（绝对路径或相对工作目录的路径）"
                    }
                },
                "required": ["dir_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            # 复用 file_writer 中的 delete_lines，但对外暴露为独立工具
            "name": "delete_file_lines",
            "_original_name": "delete_lines",
            "description": "Delete specific lines or clear entire file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "ifAll": {
                        "type": "boolean",
                        "description": "是否清空整个文件（删除所有行）",
                        "default": False
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "起始行号（从1开始），仅在 ifAll=False 时有效",
                        "default": 1
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "结束行号，None=到文件末尾",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path"]
            }
        }
    },

    # ======================== Shell/命令工具 ========================
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute PowerShell command. For scripts, builds, pip install, git, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 PowerShell 命令"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间（秒），默认30",
                        "default": 30
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "工作目录，命令在此目录下执行"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_python_syntax",
            "description": "Syntax-check a single Python file (no execution).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Python 文件路径"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_multiple_python_files",
            "description": "Syntax-check multiple Python files (no execution).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Python 文件路径列表"
                    }
                },
                "required": ["file_paths"]
            }
        }
    },

    # ======================== Skill 技能工具 ========================
    {
        "type": "function",
        "function": {
            "name": "process_image",
            "description": "Image processing: generate(text→image), recognize, edit, OCR, convert, img2img, analyze. generate needs text_prompt; recognize/edit/ocr need image_path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "操作类型: generate(文生图), recognize(图片识别), edit(编辑), ocr(文字提取), convert(格式转换), img2img(图生图), analyze(分析), list(列出所有操作)",
                        "enum": ["generate", "recognize", "edit", "ocr", "convert", "img2img", "analyze", "list"]
                    },
                    "text_prompt": {
                        "type": "string",
                        "description": "图片描述文本，generate操作必填（英文效果更佳），如 'a cute puppy dog'"
                    },
                    "image_path": {
                        "type": "string",
                        "description": "图片文件路径，recognize/edit/ocr/img2img等操作需要"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出文件路径（可选，默认保存到工作目录下，如 generated_image.png）"
                    },
                    "size": {
                        "type": "string",
                        "description": "生成图片尺寸，如 '1024*1024', '720*1280'",
                        "default": "1024*1024"
                    },
                    "style": {
                        "type": "string",
                        "description": "生成风格: realistic(写实), artistic(艺术), anime(动漫), 3d_cartoon(3D卡通)",
                        "default": "realistic"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "用于recognize/img2img的提示词，如'描述图片中的物体'"
                    }
                },
                "required": ["operation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_automation",
            "description": "Browser automation via QwenPaw. Describe task naturally (e.g. 'search Python on Baidu'). Supports: search, scrape, fill forms, screenshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "要执行的浏览器操作的自然语言描述，如'打开今日头条获取热点新闻'、'在百度搜索Python教程并截图'"
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "blender_operation",
            "description": "Execute Blender Python (bpy) via MCP for 3D modeling: create geometry, materials, lights, render. Requires Blender running with MCP plugin. Don't retry on connection failure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Blender Python代码(bpy)，如 'import bpy; bpy.ops.mesh.primitive_cube_add()'"
                    },
                    "host": {
                        "type": "string",
                        "description": "MCP服务器地址，默认localhost",
                        "default": "localhost"
                    },
                    "port": {
                        "type": "integer",
                        "description": "MCP服务器端口，默认9876",
                        "default": 9876
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认30",
                        "default": 30
                    }
                },
                "required": ["code"]
            }
        }
    },

    # ======================== 任务控制工具 ========================
    {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "Call when task is done OR to reply to user. 'summary' = technical log for system. 'reply' = natural language response shown to user. Always provide both fields. Even for simple greetings like 'hello', call finish_task with a friendly reply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "技术总结：完成了什么操作、结果如何（内部记录，用户看不到）"
                    },
                    "reply": {
                        "type": "string",
                        "description": "面向用户的自然语言回复（直接展示给用户，必须友好、清晰、有帮助）"
                    }
                },
                "required": ["summary", "reply"]
            }
        }
    },
]


# ============================================================================
# 工具函数注册映射
# tool_name → (module_import_path, function_name)
# 用于在 Schema 校验通过后，精确定位并执行对应函数
# ============================================================================

TOOL_FUNCTION_MAP: Dict[str, Dict[str, str]] = {
    # 文件操作 → file_writer.py / file_reader.py
    "write_file":           {"module": "utils.files_controler.tools.file_writer",  "function": "write_file"},
    "read_file":            {"module": "utils.files_controler.tools.file_reader",  "function": "read_file_full"},
    "read_file_lines":      {"module": "utils.files_controler.tools.file_reader",  "function": "read_file_lines"},
    "replace_content":      {"module": "utils.files_controler.tools.file_writer",  "function": "replace_content"},
    "list_directory":       {"module": "utils.files_controler.tools.file_reader",  "function": "list_directory"},
    "get_file_info":        {"module": "utils.files_controler.tools.file_reader",  "function": "get_file_info"},
    "delete_file_lines":    {"module": "utils.files_controler.tools.file_writer",  "function": "delete_lines"},
    "create_directory":     {"module": "utils.files_controler.tools.file_writer",  "function": "create_directory"},

    # Shell 命令 → command_executor.py
    "execute_command":               {"module": "utils.shell_controler.tools.command_executor", "function": "execute_command"},
    "validate_python_syntax":        {"module": "utils.shell_controler.tools.command_executor", "function": "validate_python_syntax"},
    "validate_multiple_python_files": {"module": "utils.shell_controler.tools.command_executor", "function": "validate_multiple_python_files"},

    # Skill 技能工具（已迁移到 utils/ 统一管理）
    "process_image":       {"module": "utils.img_handler.image_handler",   "function": "process"},
    "browser_automation":  {"module": "utils.web_controler.qwenpaw_client", "function": "run"},
    "blender_operation":   {"module": "utils.blender_controler",            "function": "execute_blender_operation"},

    # 任务控制（内置）
    "finish_task":         {"module": None, "function": None},  # 特殊处理：标记结束
}


# ============================================================================
# 工具注册表 API
# ============================================================================

def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    返回所有工具的 JSON Schema 列表，用于传给大模型的 tools 参数。
    这就是"工具声明"——大模型看到这些 Schema，按 Schema 输出 tool_calls。
    """
    # 过滤掉内部字段（如 _original_name），只保留标准 function calling 字段
    clean_schemas = []
    for tool in TOOL_SCHEMAS:
        func_def = tool["function"].copy()
        # 移除内部标记字段
        func_def.pop("_original_name", None)
        clean_schemas.append({"type": "function", "function": func_def})
    return clean_schemas


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找工具 Schema"""
    for tool in TOOL_SCHEMAS:
        if tool["function"]["name"] == name:
            return tool
    return None


def get_function_info(tool_name: str) -> Optional[Dict[str, str]]:
    """获取工具对应的模块路径和函数名"""
    return TOOL_FUNCTION_MAP.get(tool_name)


def resolve_original_name(tool_name: str) -> str:
    """某些工具对外名称和内部函数名不同（如 delete_file_lines → delete_lines）"""
    tool = get_tool_by_name(tool_name)
    if tool:
        return tool["function"].get("_original_name", tool_name)
    return tool_name


def format_tools_for_prompt() -> str:
    """
    将工具列表格式化为人类可读的 markdown 文本（用于非 function calling 场景的降级方案）
    """
    lines = ["## 可用工具列表\n"]
    for tool in TOOL_SCHEMAS:
        func = tool["function"]
        name = func["name"]
        desc = func["description"]
        params = func.get("parameters", {}).get("properties", {})
        required = func.get("parameters", {}).get("required", [])

        lines.append(f"### {name}")
        lines.append(f"**描述**: {desc}")
        if params:
            lines.append("**参数**:")
            for pname, pinfo in params.items():
                req_mark = " **[必填]**" if pname in required else ""
                ptype = pinfo.get("type", "any")
                pdesc = pinfo.get("description", "")
                lines.append(f"  - `{pname}` ({ptype}){req_mark}: {pdesc}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试：打印所有工具 Schema
    print(json.dumps(get_tool_schemas(), indent=2, ensure_ascii=False))
    print("\n---\n")
    print(format_tools_for_prompt())
