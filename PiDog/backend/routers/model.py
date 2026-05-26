"""
模型路由 —— 提供商列表 / 切换
"""

from fastapi import APIRouter
from api_schemas.schemas import ModelSwitchRequest
from services import model_service

router = APIRouter(prefix="/api/model", tags=["Model"])


@router.get("")
def get_model_status():
    """获取当前模型状态和所有提供商"""
    return model_service.get_model_status()


@router.post("/switch")
def switch_model(req: ModelSwitchRequest):
    """切换模型"""
    return model_service.switch_model(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
    )
