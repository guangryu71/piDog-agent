"""
工具注册表 —— 集中管理所有可用工具的 JSON Schema 声明

架构设计（v3.0）：
  SKILL_REGISTRY: 按技能分组的工具注册表，每项 = {tools: {tool_name: {schema, module, function}}}
  scan_skills():    扫描 skills/ 文件夹获取技能描述（取代 skills_locator.json）
  两阶段选择:       扫描 skills/ 文件夹 → 选技能 → 从注册表取对应工具 Schema

添加新技能只需两步：
  1. 在 skills/ 下创建文件夹，放入 README.md（技能描述）
  2. 在 SKILL_REGISTRY 中添加对应工具定义（schema + module + function）
"""

from typing import Dict, List, Any, Optional
import os

# ================================================================
# 第一部分：技能工具注册表（按 skill 文件夹名分组，模块化）
# skill 名 = skills/ 下的文件夹名，保证前后端一致
# ================================================================

SKILL_REGISTRY: Dict[str, Dict] = {

    # ── 文件操作 ──
    "files_controler": {
        "tools": {
            "write_file": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "description": "写入/创建文件。支持相对路径或绝对路径，使用 mode='append' 追加内容不覆盖。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "文件路径，支持相对路径（相对于工作空间）或绝对路径"},
                                "content":    {"type": "string", "description": "要写入的文件内容"},
                                "mode":       {"type": "string", "enum": ["overwrite", "append"], "description": "写入模式：overwrite=覆盖, append=追加", "default": "overwrite"},
                                "encoding":   {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
                            },
                            "required": ["file_path", "content"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_writer",
                "function": "write_file",
            },
            "read_file": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "读取整个文件内容。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "文件路径，支持相对路径或绝对路径"},
                                "encoding":   {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
                            },
                            "required": ["file_path"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_reader",
                "function": "read_file_full",
            },
            "read_file_lines": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "read_file_lines",
                        "description": "读取文件指定行范围（1-based）。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path":   {"type": "string", "description": "文件路径"},
                                "start_line":  {"type": "integer", "description": "起始行号（1-based，含）"},
                                "end_line":    {"type": "integer", "description": "结束行号（1-based，含），可选，默认读到文件末尾"},
                                "encoding":    {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
                            },
                            "required": ["file_path", "start_line"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_reader",
                "function": "read_file_lines",
            },
            "replace_content": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "replace_content",
                        "description": "在文件中查找并替换文本，所有匹配的 old_text 都会被替换。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "文件路径"},
                                "old_text":   {"type": "string", "description": "要查找的原始文本（精确匹配）"},
                                "new_text":   {"type": "string", "description": "替换后的新文本"},
                                "encoding":   {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
                            },
                            "required": ["file_path", "old_text", "new_text"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_writer",
                "function": "replace_content",
            },
            "list_directory": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "list_directory",
                        "description": "列出目录内容，返回文件/目录名称列表。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path":        {"type": "string", "description": "目录路径，支持相对或绝对路径"},
                                "recursive":   {"type": "boolean", "description": "是否递归列出子目录", "default": False},
                                "show_hidden": {"type": "boolean", "description": "是否显示隐藏文件", "default": False},
                            },
                            "required": ["path"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_reader",
                "function": "list_directory",
            },
            "get_file_info": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "get_file_info",
                        "description": "获取文件元数据：大小、修改时间、类型。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "文件路径"},
                            },
                            "required": ["file_path"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_reader",
                "function": "get_file_info",
            },
            "delete_file_lines": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "delete_file_lines",
                        "description": "删除文件中的行。使用 start_line/end_line 指定范围或 match_pattern 正则匹配。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path":     {"type": "string", "description": "文件路径"},
                                "start_line":    {"type": "integer", "description": "起始行号（1-based，含）"},
                                "end_line":      {"type": "integer", "description": "结束行号（1-based，含），可选"},
                                "match_pattern": {"type": "string", "description": "删除匹配的行（正则表达式），与行号二选一"},
                                "encoding":      {"type": "string", "description": "文件编码，默认 utf-8", "default": "utf-8"},
                            },
                            "required": ["file_path"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_writer",
                "function": "delete_lines",
                "_original_name": "delete_lines",
            },
            "create_directory": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "create_directory",
                        "description": "创建新目录（自动创建父目录）。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path":     {"type": "string", "description": "目录路径"},
                                "parents":  {"type": "boolean", "description": "是否创建父目录", "default": True},
                            },
                            "required": ["path"]
                        }
                    }
                },
                "module": "utils.files_controler.tools.file_writer",
                "function": "create_directory",
            },
        }
    },

    # ── 命令行执行 ──
    "shell_controler": {
        "tools": {
            "execute_command": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "execute_command",
                        "description": "执行 shell/PowerShell 命令并返回输出。用于运行脚本、安装依赖（pip/npm）、git 操作、系统信息查询等。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command":  {"type": "string", "description": "要执行的命令"},
                                "cwd":      {"type": "string", "description": "工作目录，可选"},
                                "timeout":  {"type": "integer", "description": "超时秒数，默认 60", "default": 60},
                            },
                            "required": ["command"]
                        }
                    }
                },
                "module": "utils.shell_controler.tools.command_executor",
                "function": "execute_command",
            },
            "validate_python_syntax": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "validate_python_syntax",
                        "description": "验证 Python 语法（不执行），返回错误信息（如有）。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Python 代码字符串"},
                            },
                            "required": ["code"]
                        }
                    }
                },
                "module": "utils.shell_controler.tools.command_executor",
                "function": "validate_python_syntax",
            },
            "validate_multiple_python_files": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "validate_multiple_python_files",
                        "description": "同时验证多个 Python 文件的语法。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Python 文件路径列表"},
                            },
                            "required": ["file_paths"]
                        }
                    }
                },
                "module": "utils.shell_controler.tools.command_executor",
                "function": "validate_multiple_python_files",
            },
        }
    },

    # ── 图片处理 ──
    "skill_img_handler": {
        "tools": {
            "process_image": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "process_image",
                        "description": "处理图片：recognize(识别), generate(文生图), img2img(图生图), edit(编辑), ocr(文字提取), convert(格式转换), resize(调整尺寸), remove_bg(去背景), enhance(增强), analyze(质量分析)。指定 operation 和相应参数执行对应操作。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "operation": {
                                    "type": "string",
                                    "enum": ["recognize", "generate", "img2img", "edit", "ocr", "convert", "resize", "remove_bg", "enhance", "analyze"],
                                    "description": "操作类型: recognize=识别图片, generate=文生图, img2img=图生图, edit=编辑图片, ocr=文字提取, convert=格式转换, resize=调整尺寸, remove_bg=去背景, enhance=增强, analyze=质量分析"
                                },
                                "image_path":     {"type": "string",   "description": "图片路径（用于recognize/edit/ocr/convert/resize/remove_bg/enhance/analyze/img2img）"},
                                "text_prompt":     {"type": "string",   "description": "文生图/图生图的提示词，如'一只可爱的小猫'"},
                                "size":            {"type": "string",   "description": "生成图片尺寸: 1024*1024(正方形), 720*1280(竖屏), 1280*720(横屏)", "default": "1024*1024"},
                                "style":           {"type": "string",   "description": "生成风格: realistic(写实), artistic(艺术), anime(动漫), 3d_cartoon(3D卡通)", "default": "realistic"},
                                "prompt":          {"type": "string",   "description": "用于recognize/img2img的提示词，如'描述图片中的物体'"},
                            },
                            "required": ["operation"]
                        }
                    }
                },
                "module": "utils.img_handler.image_handler",
                "function": "process",
            },
        }
    },

    # ── 浏览器自动化（v4.0: 原生 Playwright，不再依赖 QwenPaw 服务）──
    "skill_web_controler": {
        "tools": {
            "browser_use": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "browser_use",
                        "description": "控制浏览器（Playwright）。默认无头模式，action=start 加 headed=True 显示窗口。流程：start→open(url)→snapshot(获取元素引用)→click/type(用ref操作元素)→screenshot。支持：start, stop, open, navigate, snapshot, click, type, screenshot, eval, close, tabs, press_key, wait_for, pdf 等操作。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string", "enum": ["start","stop","open","navigate","navigate_back","snapshot","click","type","screenshot","eval","evaluate","close","tabs","press_key","wait_for","pdf","console_messages","network_requests"], "description": "操作类型"},
                                "url": {"type": "string", "description": "目标 URL（open/navigate 时必需）"},
                                "page_id": {"type": "string", "description": "页面标识符，默认 'default'", "default": "default"},
                                "selector": {"type": "string", "description": "CSS 选择器（click/type 时可选，与 ref 二选一）"},
                                "text": {"type": "string", "description": "输入文本（type 时必需）"},
                                "code": {"type": "string", "description": "JS 代码（eval 时必需）"},
                                "path": {"type": "string", "description": "输出文件路径（screenshot/pdf）"},
                                "wait": {"type": "integer", "description": "click 后等待毫秒数"},
                                "full_page": {"type": "boolean", "description": "是否全页截图"},
                                "filename": {"type": "string", "description": "快照/截图文件名"},
                                "ref": {"type": "string", "description": "元素引用（来自 snapshot，与 selector 二选一）"},
                                "key": {"type": "string", "description": "按键名（press_key 时必需，如 'Enter', 'Escape'）"},
                                "submit": {"type": "boolean", "description": "type 后是否按 Enter"},
                                "slowly": {"type": "boolean", "description": "是否逐字符输入"},
                                "double_click": {"type": "boolean", "description": "是否双击"},
                                "button": {"type": "string", "enum": ["left","right","middle"], "description": "鼠标按钮"},
                                "screenshot_type": {"type": "string", "enum": ["png","jpeg"], "description": "截图格式"},
                                "snapshot_filename": {"type": "string", "description": "快照保存路径"},
                                "tab_action": {"type": "string", "enum": ["list","new","close","select"], "description": "标签操作"},
                                "index": {"type": "integer", "description": "标签索引（tabs select/close 时）"},
                                "wait_time": {"type": "number", "description": "等待秒数（wait_for）"},
                                "text_gone": {"type": "string", "description": "等待此文本消失（wait_for）"},
                                "headed": {"type": "boolean", "description": "是否显示浏览器窗口（start 时有效）"},
                                "browser_args": {"type": "string", "description": "额外浏览器启动参数"},
                                "executable_path": {"type": "string", "description": "自定义浏览器路径"},
                                "level": {"type": "string", "enum": ["info","warning","error"], "description": "控制台日志级别"},
                                "include_static": {"type": "boolean", "description": "是否包含静态资源请求（network_requests）"},
                            },
                            "required": ["action"]
                        }
                    }
                },
                "module": "utils.web_controler.browser_engine",
                "function": "browser_use",
            },
        }
    },

    # ── Blender 3D 建模 ──
    "skill_blender_controler": {
        "tools": {
            "blender_operation": {
                "schema": {
                    "type": "function",
                    "function": {
                        "name": "blender_operation",
                        "description": "通过 MCP 执行 Blender Python(bpy) 代码进行 3D 建模：创建几何体、材质、灯光、渲染。需要 Blender 运行且 MCP 插件已开启（localhost:9876）。连接失败请勿重试。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "code":    {"type": "string",  "description": "Blender Python 代码(bpy)，如 'import bpy; bpy.ops.mesh.primitive_cube_add()'"},
                                "host":    {"type": "string",  "description": "MCP 服务器地址，默认 localhost", "default": "localhost"},
                                "port":    {"type": "integer", "description": "MCP 服务器端口，默认 9876", "default": 9876},
                                "timeout": {"type": "integer", "description": "超时秒数，默认 30", "default": 30},
                            },
                            "required": ["code"]
                        }
                    }
                },
                "module": "utils.blender_controler",
                "function": "execute_blender_operation",
            },
        }
    },
}


# ================================================================
# finish_task — 任务结束/用户回复工具（必要，始终附带）
# module/function 为 None，由 FunctionCallingExecutor 特殊处理
# ================================================================

_FINISH_TASK = {
    "schema": {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "任务完成时或需要回复用户时调用。'summary' = 面向系统的技术执行摘要，'reply' = 面向用户的友好自然语言回复。两个字段都必须提供。即使是简单问候如'你好'，也要通过 finish_task 回复。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "技术执行摘要（面向系统记录，描述完成了什么操作）"},
                    "reply":   {"type": "string", "description": "面向用户的自然语言回复（直接展示给用户，必须友好、清晰、有帮助）"},
                },
                "required": ["summary", "reply"]
            }
        }
    },
    "module": None,
    "function": None,
}


# ================================================================
# 第二部分：自动构建数据结构（从 SKILL_REGISTRY + _FINISH_TASK）
# ================================================================

def _build_function_map() -> Dict[str, Dict[str, str]]:
    """从 SKILL_REGISTRY + _FINISH_TASK 自动构建 TOOL_FUNCTION_MAP"""
    result = {}
    for skill_def in SKILL_REGISTRY.values():
        for tool_name, tool_def in skill_def["tools"].items():
            entry = {
                "module": tool_def["module"],
                "function": tool_def["function"],
            }
            if "_original_name" in tool_def:
                entry["_original_name"] = tool_def["_original_name"]
            result[tool_name] = entry
    result["finish_task"] = {"module": _FINISH_TASK["module"], "function": _FINISH_TASK["function"]}
    return result


def _build_all_schemas() -> List[Dict]:
    """从 SKILL_REGISTRY + _FINISH_TASK 自动构建 TOOL_SCHEMAS"""
    result = []
    for skill_def in SKILL_REGISTRY.values():
        for tool_def in skill_def["tools"].values():
            result.append(tool_def["schema"])
    result.append(_FINISH_TASK["schema"])
    return result


def _build_skill_to_tools() -> Dict[str, List[str]]:
    """从 SKILL_REGISTRY 自动构建 SKILL_TO_TOOLS"""
    return {name: list(skill["tools"].keys()) for name, skill in SKILL_REGISTRY.items()}


# 自动构建，保证注册表和映射表永远一致
TOOL_FUNCTION_MAP: Dict[str, Dict[str, str]] = _build_function_map()
TOOL_SCHEMAS: List[Dict]                       = _build_all_schemas()
SKILL_TO_TOOLS: Dict[str, List[str]]           = _build_skill_to_tools()


# ================================================================
# 第四部分：技能扫描（取代 skills_locator.json）
# 扫描 skills/ 文件夹，读取 README.md → 得到 {skill_name: description}
# ================================================================

# 项目根路径：本文件在 utils/，项目根在上一级
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(_PROJECT_ROOT, "skills")

# 默认禁用的技能列表文件
_DISABLED_FILE = os.path.join(_PROJECT_ROOT, "PiDog", "backend", "disabled_skills.json")


def scan_skills(skills_dir: str = None) -> Dict[str, str]:
    """
    扫描 skills/ 文件夹，读取每个子文件夹的 README.md 获取技能描述。

    扫描规则：
      - 遍历 skills/ 下所有子文件夹
      - 如果子文件夹内存在 README.md，读取其内容作为技能描述
      - 技能名 = 子文件夹名（如 skill_blender_controler、files_controler）
      - 描述取 README.md 中 `# 标题` 之后的内容，跳过标题行本身
      - 如果没有 README.md 或内容为空，跳过该文件夹

    Returns:
        {skill_name: description}  例: {"skill_blender_controler": "通过 bpy Python 代码..."}
    """
    if skills_dir is None:
        skills_dir = SKILLS_DIR

    if not os.path.isdir(skills_dir):
        return {}

    skills = {}
    try:
        for entry in os.listdir(skills_dir):
            folder = os.path.join(skills_dir, entry)
            if not os.path.isdir(folder):
                continue
            readme = os.path.join(folder, "README.md")
            if not os.path.isfile(readme):
                continue

            with open(readme, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                continue

            # 提取描述：去掉 # 标题行，取剩余内容
            lines = content.split("\n")
            desc_lines = []
            skip_title = True
            for line in lines:
                stripped = line.strip()
                if skip_title and stripped.startswith("#"):
                    skip_title = False
                    continue
                if stripped:
                    desc_lines.append(stripped)

            description = " ".join(desc_lines).strip()
            if description:
                skills[entry] = description

    except Exception:
        pass

    return skills


# ================================================================
# 第五部分：公共 API
# ================================================================

def get_tool_schemas() -> List[Dict[str, Any]]:
    """返回所有工具的 JSON Schema 列表（用于传给大模型 tools 参数）。
    包含静态注册工具 + 已连接的 MCP 动态工具。"""
    clean_schemas = []
    for tool in TOOL_SCHEMAS:
        func_def = tool["function"].copy()
        func_def.pop("_original_name", None)
        clean_schemas.append({"type": "function", "function": func_def})

    # 添加已连接的 MCP 动态工具
    try:
        from MCPS import get_connected_mcp_tool_schemas
        mcp_schemas = get_connected_mcp_tool_schemas()
        clean_schemas.extend(mcp_schemas)
    except ImportError:
        pass

    return clean_schemas


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按名称查找工具 Schema（含 MCP 工具）"""
    # 先查静态注册表
    for tool in TOOL_SCHEMAS:
        if tool["function"]["name"] == name:
            return tool
    # 再查 MCP 工具（名称以 mcp__ 开头）
    if name.startswith("mcp__"):
        try:
            from MCPS import get_connected_mcp_tool_schemas
            for tool in get_connected_mcp_tool_schemas():
                if tool["function"]["name"] == name:
                    return tool
        except ImportError:
            pass
    return None


def get_function_info(tool_name: str) -> Optional[Dict[str, str]]:
    """获取工具对应的模块路径和函数名（含 MCP 工具）"""
    if tool_name.startswith("mcp__"):
        # MCP 工具不需要 module/function 路径，由 MCPS 路由
        return {"module": "MCPS", "function": "call_mcp_tool"}
    return TOOL_FUNCTION_MAP.get(tool_name)


def resolve_original_name(tool_name: str) -> str:
    """某些工具对外名称和内部函数名不同（如 delete_file_lines → delete_lines）"""
    tool = get_tool_by_name(tool_name)
    if tool:
        return tool["function"].get("_original_name", tool_name)
    return tool_name


def format_tools_for_prompt() -> str:
    """将工具列表格式化为人类可读的 markdown 文本（用于非 function calling 场景的降级方案）"""
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


def get_tools_for_skills(selected_skills: List[str]) -> List[Dict[str, Any]]:
    """
    根据选中的技能名返回对应工具的 Schema。
    始终附带 finish_task（任务结束/回复用户的必要工具）。

    Args:
        selected_skills: 技能名列表，如 ["skill_blender_controler", "files_controler"]
    Returns:
        对应工具的 JSON Schema 列表
    """
    tool_names: set = {"finish_task"}

    for skill in selected_skills:
        if skill in SKILL_TO_TOOLS:
            tool_names.update(SKILL_TO_TOOLS[skill])

    return [t for t in TOOL_SCHEMAS if t["function"]["name"] in tool_names]


def build_skill_selection_prompt(user_message: str, skills_dir: str = None) -> str:
    """
    构建技能选择 prompt：扫描 skills/ 文件夹获取可用技能，让 LLM 选择。
    取代原来读取 skills_locator.json 的方式。

    Args:
        user_message: 用户输入
        skills_dir:   skills 文件夹路径，默认 SKILLS_DIR

    Returns:
        完整的技能选择 prompt（含可用技能列表），若无技能则返回空字符串
    """
    skills = scan_skills(skills_dir)
    if not skills:
        return ""

    skill_items = []
    for name, desc in skills.items():
        skill_items.append(f"- **{name}**: {desc}")

    skills_text = "\n".join(skill_items)

    return (
        f"# 技能选择\n"
        f"根据用户需求，从以下技能列表中选择**必须**的技能。\n"
        f"只选真正需要的技能，按需选择，不要多选。\n\n"
        f"## 可用技能\n{skills_text}\n\n"
        f"## 用户需求\n{user_message}\n\n"
        f"## 输出格式（仅输出 JSON，不要其他内容）\n"
        f'{{"selected_skills": ["skill_name1", "skill_name2"]}}\n'
    )


if __name__ == "__main__":
    import json
    print("=== 扫描技能 ===")
    for name, desc in scan_skills().items():
        print(f"  {name}: {desc[:80]}...")

    print(f"\n=== 总计 {len(get_tool_schemas())} 个工具 ===")
    for t in get_tool_schemas():
        print(f"  {t['function']['name']}")

    print(f"\n=== SKILL_TO_TOOLS ===")
    print(json.dumps(SKILL_TO_TOOLS, indent=2, ensure_ascii=False))
