"""
Skill 管理服务 —— 展示 / 修改 / 禁用 / 添加 / 删除
Skill 定义在 skills_locator.json，代码在 skills/ 和 utils/ 下
"""

import json
import os
import sys
import shutil
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from config import PROJECT_ROOT
from api_schemas.schemas import SkillInfo

SKILLS_LOCATOR = os.path.join(PROJECT_ROOT, "skills_locator.json")
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
UTILS_DIR = os.path.join(PROJECT_ROOT, "utils")

# 被禁用的 skill 暂存于此
DISABLED_FILE = os.path.join(PROJECT_ROOT, "PiDog", "backend", "disabled_skills.json")


def _load_locator() -> dict:
    if not os.path.exists(SKILLS_LOCATOR):
        return {"version": "1.0", "description": ""}
    with open(SKILLS_LOCATOR, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_locator(data: dict):
    os.makedirs(os.path.dirname(SKILLS_LOCATOR), exist_ok=True)
    with open(SKILLS_LOCATOR, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_disabled() -> dict:
    if not os.path.exists(DISABLED_FILE):
        return {}
    with open(DISABLED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_disabled(data: dict):
    os.makedirs(os.path.dirname(DISABLED_FILE), exist_ok=True)
    with open(DISABLED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_skills() -> List[SkillInfo]:
    """列出所有 skill（含启用/禁用状态）"""
    locator = _load_locator()
    disabled = _load_disabled()
    skills = []
    for key, value in locator.items():
        if key in ("version", "description", "statistics"):
            continue
        if isinstance(value, dict):
            skills.append(SkillInfo(
                key=key,
                description=value.get("description", "")[:200],
                enabled=key not in disabled,
                path=value.get("readme_path", ""),
            ))
    # 也列出被禁用但已不在 locator 中的
    for key in disabled:
        if key not in locator:
            skills.append(SkillInfo(
                key=key,
                description=disabled[key].get("description", "")[:200],
                enabled=False,
                path="",
            ))
    return skills


def update_skill(key: str, description: str = None, enabled: bool = None) -> dict:
    """修改 skill 描述或启用/禁用"""
    locator = _load_locator()

    if key not in locator:
        return {"ok": False, "error": f"Skill '{key}' not found"}

    if description is not None:
        if isinstance(locator[key], dict):
            locator[key]["description"] = description
        _save_locator(locator)

    if enabled is not None:
        disabled = _load_disabled()
        if enabled:
            disabled.pop(key, None)
        else:
            if key not in disabled:
                disabled[key] = {"description": locator.get(key, {}).get("description", ""), "disabled_at": ""}
        _save_disabled(disabled)

    return {"ok": True, "key": key}


def add_skill(key: str, description: str, path: str = "") -> dict:
    """添加新 skill"""
    locator = _load_locator()
    if key in locator:
        return {"ok": False, "error": f"Skill '{key}' already exists"}

    locator[key] = {
        "readme_path": path or f"skills/{key}/README.md",
        "description": description,
    }
    _save_locator(locator)
    return {"ok": True, "key": key}


def delete_skill(key: str) -> dict:
    """删除 skill（从 locator 移除，可选删除代码目录）"""
    locator = _load_locator()
    if key not in locator:
        return {"ok": False, "error": f"Skill '{key}' not found"}

    info = locator.pop(key)
    _save_locator(locator)

    # 尝试删除对应目录
    readme = info.get("readme_path", "") if isinstance(info, dict) else ""
    if readme:
        # 从 readme_path 推断目录
        skill_dir = os.path.dirname(os.path.join(PROJECT_ROOT, readme))
        if os.path.isdir(skill_dir) and (skill_dir.startswith(SKILLS_DIR) or skill_dir.startswith(UTILS_DIR)):
            try:
                shutil.rmtree(skill_dir)
            except Exception:
                pass

    return {"ok": True, "key": key, "removed_dir": bool(readme)}
