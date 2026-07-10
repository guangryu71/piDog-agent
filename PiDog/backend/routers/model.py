"""
模型路由 —— 逻辑模型 + 图片生成模型 + 图片理解模型
"""

from fastapi import APIRouter
from api_schemas.schemas import ModelSwitchRequest, ImageModelSwitchRequest
from services import model_service

router = APIRouter(prefix="/api/model", tags=["Model"])


# ==================== 逻辑模型 ====================


@router.get("")
def get_model_status():
    """获取当前逻辑模型状态和所有提供商"""
    return model_service.get_model_status()


@router.post("/switch")
def switch_model(req: ModelSwitchRequest):
    """切换逻辑模型"""
    return model_service.switch_model(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
    )


# ==================== 图片生成模型 ====================


@router.get("/img-gen")
def get_img_gen_status():
    """获取图片生成模型状态"""
    return model_service.get_img_gen_status()


@router.post("/img-gen/switch")
def switch_img_gen(req: ImageModelSwitchRequest):
    """切换图片生成模型"""
    return model_service.switch_img_gen(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
    )


# ==================== 图片理解模型 ====================


@router.get("/img-und")
def get_img_und_status():
    """获取图片理解模型状态"""
    return model_service.get_img_und_status()


@router.post("/img-und/switch")
def switch_img_und(req: ImageModelSwitchRequest):
    """切换图片理解模型"""
    return model_service.switch_img_und(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
    )
