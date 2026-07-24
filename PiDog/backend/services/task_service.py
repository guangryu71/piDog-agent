"""
自定义任务服务 —— CRUD + 持久化存储 + 任务执行
任务文件存储在 PiDog/backend/tasks/
"""

import os
import json
import uuid
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

from config import PROJECT_ROOT
from api_schemas.schemas import TaskSchema, TaskCreate, TaskUpdate

# ── 任务存储目录 ──
TASKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tasks")
os.makedirs(TASKS_DIR, exist_ok=True)

# ── 任务运行结果存储 ──
RESULTS_DIR = os.path.join(TASKS_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── 任务 → 会话 映射（运行时内存态，任务执行时创建） ──
# task_session_map[session_id] = {"task_id": str, "selected_skills": [...], "selected_tools": [...], "selected_mcp": [...]}
task_session_map: Dict[str, dict] = {}


def _task_file_path(task_id: str) -> str:
    """获取任务文件路径"""
    return os.path.join(TASKS_DIR, f"{task_id}.json")


def _load_tasks() -> List[TaskSchema]:
    """加载所有任务"""
    tasks = []
    if not os.path.isdir(TASKS_DIR):
        return tasks
    for fname in sorted(os.listdir(TASKS_DIR), reverse=True):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(TASKS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                tasks.append(TaskSchema(**data))
            except Exception:
                continue
    return tasks


def _save_task(task: TaskSchema):
    """保存单个任务到文件"""
    with open(_task_file_path(task.id), "w", encoding="utf-8") as f:
        json.dump(task.model_dump(), f, ensure_ascii=False, indent=2)


def _delete_task_file(task_id: str):
    """删除任务文件"""
    path = _task_file_path(task_id)
    if os.path.exists(path):
        os.remove(path)


# ==================== CRUD ====================


def list_tasks() -> List[dict]:
    """列出所有任务"""
    return [t.model_dump() for t in _load_tasks()]


def get_task(task_id: str) -> Optional[dict]:
    """获取单个任务"""
    tasks = _load_tasks()
    for t in tasks:
        if t.id == task_id:
            return t.model_dump()
    return None


def create_task(req: TaskCreate) -> dict:
    """创建新任务"""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    task = TaskSchema(
        id=str(uuid.uuid4())[:8],
        title=req.title,
        agent_prompt=req.agent_prompt,
        init_message=req.init_message or "",
        selected_skills=req.selected_skills or [],
        selected_mcp=req.selected_mcp or [],
        selected_tools=req.selected_tools or [],
        selected_files=req.selected_files or [],
        created_at=now,
        updated_at=now,
    )
    _save_task(task)
    return task.model_dump()


def update_task(task_id: str, req: TaskUpdate) -> Optional[dict]:
    """更新任务"""
    tasks = _load_tasks()
    for t in tasks:
        if t.id == task_id:
            if req.title is not None:
                t.title = req.title
            if req.agent_prompt is not None:
                t.agent_prompt = req.agent_prompt
            if req.init_message is not None:
                t.init_message = req.init_message
            if req.selected_skills is not None:
                t.selected_skills = req.selected_skills
            if req.selected_mcp is not None:
                t.selected_mcp = req.selected_mcp
            if req.selected_tools is not None:
                t.selected_tools = req.selected_tools
            if req.selected_files is not None:
                t.selected_files = req.selected_files
            t.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
            _save_task(t)
            return t.model_dump()
    return None


def delete_task(task_id: str) -> bool:
    """删除任务"""
    _delete_task_file(task_id)
    # 清理可能残留的会话映射
    for sid in list(task_session_map.keys()):
        if task_session_map[sid].get("task_id") == task_id:
            del task_session_map[sid]
    return True


# ==================== 任务执行 ====================


def run_task(task_id: str) -> Optional[dict]:
    """
    执行任务：创建新 session，将任务参数注入 session 上下文
    返回 {session_id, task_id}
    """
    tasks = _load_tasks()
    task = None
    for t in tasks:
        if t.id == task_id:
            task = t
            break

    if not task:
        return None

    # 生成新 session_id
    session_id = str(uuid.uuid4())[:8]

    # 存储任务 → session 映射（供 agent_service 读取）
    task_session_map[session_id] = {
        "task_id": task.id,
        "agent_prompt": task.agent_prompt,
        "init_message": task.init_message,
        "selected_skills": task.selected_skills,
        "selected_tools": task.selected_tools,
        "selected_mcp": task.selected_mcp,
        "selected_files": task.selected_files,
    }

    return {
        "session_id": session_id,
        "task_id": task.id,
    }


# ==================== 运行结果持久化 ====================


def save_run_result(task_id: str, session_id: str, result_text: str) -> dict:
    """保存任务运行结果"""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    result = {
        "task_id": task_id,
        "session_id": session_id,
        "result": result_text,
        "timestamp": now,
    }
    result_file = os.path.join(RESULTS_DIR, f"{task_id}_{session_id}.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def get_run_results(task_id: str) -> List[dict]:
    """获取任务的所有历史运行结果（按时间倒序，最新在前）"""
    if not os.path.isdir(RESULTS_DIR):
        return []
    results = []
    prefix = f"{task_id}_"
    for fname in os.listdir(RESULTS_DIR):
        if fname.startswith(prefix) and fname.endswith(".json"):
            try:
                with open(os.path.join(RESULTS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
            except Exception:
                continue
    # 按 timestamp 字段倒序（最新在前）
    results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return results


def get_task_session(session_id: str) -> Optional[dict]:
    """获取 session 对应的任务上下文"""
    return task_session_map.get(session_id)


def clear_task_session(session_id: str):
    """清理任务会话映射"""
    task_session_map.pop(session_id, None)
