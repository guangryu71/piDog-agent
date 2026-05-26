"""
Skill 路由 —— CRUD 管理
"""

from fastapi import APIRouter
from api_schemas.schemas import SkillUpdate, SkillCreate
from services import skill_service

router = APIRouter(prefix="/api/skills", tags=["Skills"])


@router.get("")
def list_skills():
    """列出所有 skill"""
    return skill_service.list_skills()


@router.put("/{key}")
def update_skill(key: str, req: SkillUpdate):
    """修改 skill 描述或启用/禁用"""
    return skill_service.update_skill(
        key=key,
        description=req.description,
        enabled=req.enabled,
    )


@router.post("")
def add_skill(req: SkillCreate):
    """添加新 skill"""
    return skill_service.add_skill(
        key=req.key,
        description=req.description,
    )


@router.delete("/{key}")
def delete_skill(key: str):
    """删除 skill"""
    return skill_service.delete_skill(key)
