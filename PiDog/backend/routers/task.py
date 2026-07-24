"""
自定义任务路由 —— CRUD + 运行 + 结果管理
"""

from fastapi import APIRouter, HTTPException
from api_schemas.schemas import TaskCreate, TaskUpdate
from services import task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("")
def list_tasks():
    """列出所有任务"""
    return task_service.list_tasks()


@router.get("/{task_id}")
def get_task(task_id: str):
    """获取单个任务"""
    task = task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.post("")
def create_task(req: TaskCreate):
    """创建新任务"""
    return task_service.create_task(req)


@router.put("/{task_id}")
def update_task(task_id: str, req: TaskUpdate):
    """更新任务"""
    task = task_service.update_task(task_id, req)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.delete("/{task_id}")
def delete_task(task_id: str):
    """删除任务"""
    task_service.delete_task(task_id)
    return {"ok": True}


@router.post("/{task_id}/run")
def run_task(task_id: str):
    """运行任务：创建新 session 并注入任务参数"""
    result = task_service.run_task(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return result


@router.post("/{task_id}/results")
def save_result(task_id: str, req: dict):
    """保存任务运行结果"""
    result = task_service.save_run_result(
        task_id=task_id,
        session_id=req.get("session_id", ""),
        result_text=req.get("result", ""),
    )
    return result


@router.get("/{task_id}/results")
def get_results(task_id: str):
    """获取任务历史运行结果"""
    return task_service.get_run_results(task_id)
