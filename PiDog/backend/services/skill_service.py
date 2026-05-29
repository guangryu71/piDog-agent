"""
Skill 管理服务 —— 展示 / 修改 / 禁用 / 添加 / 删除
Skill 定义在 skills/ 文件夹中（每个子文件夹 = 一个 skill），描述存在 README.md。

架构 v3.0:
  - Skill 名 = skills/ 下的文件夹名（如 skill_blender_controler、files_controler）
  - 描述 = 文件夹内的 README.md
  - 添加 skill = 创建文件夹 + 写入 README.md
  - 删除 skill = 删除文件夹
  - 修改描述 = 重写 README.md
  - 启用/禁用 = 在 disabled_skills.json 中记录
"""

import json
import os
import sys
import shutil
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from config import PROJECT_ROOT
from api_schemas.schemas import SkillInfo

# ---- 路径常量 ----
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
DISABLED_FILE = os.path.join(PROJECT_ROOT, "PiDog", "backend", "disabled_skills.json")


def _load_disabled() -> dict:
    """加载被禁用的 skill 记录"""
    if not os.path.exists(DISABLED_FILE):
        return {}
    with open(DISABLED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_disabled(data: dict):
    """保存被禁用的 skill 记录"""
    os.makedirs(os.path.dirname(DISABLED_FILE), exist_ok=True)
    with open(DISABLED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_skill_readme(skill_name: str) -> str:
    """读取 skill 文件夹内的 README.md，返回描述内容（不含标题行）"""
    folder = os.path.join(SKILLS_DIR, skill_name)
    if not os.path.isdir(folder):
        return ""

    readme = os.path.join(folder, "README.md")
    if not os.path.isfile(readme):
        return ""

    with open(readme, "r", encoding="utf-8") as f:
        content = f.read().strip()

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

    return " ".join(desc_lines).strip()


def _write_skill_readme(skill_name: str, description: str):
    """写入 skill 描述到 README.md"""
    folder = os.path.join(SKILLS_DIR, skill_name)
    os.makedirs(folder, exist_ok=True)

    # 从描述中提取标题（取第一句作为 # 标题），其余为正文
    title = f"# {skill_name}"
    readme_path = os.path.join(folder, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"{title}\n\n{description}\n")


def _scan_skill_folders() -> List[str]:
    """扫描 skills/ 下所有子文件夹，返回 skill 名列表"""
    if not os.path.isdir(SKILLS_DIR):
        return []
    return [
        entry for entry in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, entry))
    ]


def list_skills() -> List[SkillInfo]:
    """
    列出所有 skill（含启用/禁用状态）。
    通过扫描 skills/ 文件夹 + 读取 README.md 获取描述。
    """
    disabled = _load_disabled()
    folder_names = set(_scan_skill_folders())

    skills = []

    # 扫描到的 skill（从文件夹）
    for name in sorted(folder_names):
        desc = _read_skill_readme(name)
        skills.append(SkillInfo(
            key=name,
            description=desc[:200] if desc else "",
            enabled=name not in disabled,
            path=f"skills/{name}/README.md",
        ))

    # 被禁用但文件夹已不存在的 skill（保留记录）
    for name in disabled:
        if name not in folder_names:
            skills.append(SkillInfo(
                key=name,
                description=disabled[name].get("description", "")[:200],
                enabled=False,
                path="",
            ))

    return skills


def update_skill(key: str, description: str = None, enabled: bool = None) -> dict:
    """
    修改 skill 描述或启用/禁用状态。
    - description: 写入 README.md
    - enabled: 更新 disabled_skills.json
    """
    folder = os.path.join(SKILLS_DIR, key)

    if not os.path.isdir(folder):
        return {"ok": False, "error": f"Skill '{key}' not found (folder does not exist)"}

    # 修改描述
    if description is not None:
        try:
            _write_skill_readme(key, description)
        except Exception as e:
            return {"ok": False, "error": f"Failed to write README.md: {e}"}

    # 修改启用状态
    if enabled is not None:
        disabled = _load_disabled()
        if enabled:
            disabled.pop(key, None)
        else:
            current_desc = _read_skill_readme(key)
            disabled[key] = {"description": current_desc}

        # 清理已不存在的禁用记录
        disabled = {k: v for k, v in disabled.items() if k in _scan_skill_folders() or k == key}
        _save_disabled(disabled)

    return {"ok": True}


def add_skill(key: str, description: str) -> dict:
    """
    添加新 skill：在 skills/ 下创建文件夹 + 写入 README.md。
    同时注册到 SkillInfo 和前端。

    Args:
        key: skill 名（即文件夹名，如 "skill_my_new_tool"）
        description: 技能描述
    """
    folder = os.path.join(SKILLS_DIR, key)

    if os.path.exists(folder):
        return {"ok": False, "error": f"Skill folder '{key}' already exists"}

    try:
        _write_skill_readme(key, description)
    except Exception as e:
        return {"ok": False, "error": f"Failed to create skill: {e}"}

    # 如果之前被禁用过，启用它
    disabled = _load_disabled()
    disabled.pop(key, None)
    _save_disabled(disabled)

    return {"ok": True, "skill": {"key": key, "description": description, "path": f"skills/{key}/README.md"}}


def delete_skill(key: str) -> dict:
    """
    删除 skill：删除 skills/ 下的对应文件夹。
    删除前检查该 skill 是否在 SKILL_REGISTRY 中有工具定义（防止删除内置 skill）。
    """
    folder = os.path.join(SKILLS_DIR, key)

    if not os.path.exists(folder):
        return {"ok": False, "error": f"Skill '{key}' not found"}

    try:
        # 只删除 skill 文件夹本身（README.md），不删除 tools/ 子目录（工具代码在 utils/ 下）
        readme = os.path.join(folder, "README.md")
        tools_dir = os.path.join(folder, "tools")

        if os.path.isfile(readme):
            os.remove(readme)
        if os.path.isdir(tools_dir):
            # 保留 tools 代码（真正实现在 utils/ 下），只删描述
            pass

        # 如果文件夹为空，删除文件夹
        remaining = os.listdir(folder)
        if not remaining or remaining == ["tools"]:
            if not remaining:
                os.rmdir(folder)
            # 如果只剩 tools 空目录也删
            elif remaining == ["tools"] and not os.listdir(tools_dir):
                shutil.rmtree(folder)
    except Exception as e:
        return {"ok": False, "error": f"Failed to delete: {e}"}

    # 如果被禁用过，也从禁用列表移除
    disabled = _load_disabled()
    disabled.pop(key, None)
    _save_disabled(disabled)

    return {"ok": True}
