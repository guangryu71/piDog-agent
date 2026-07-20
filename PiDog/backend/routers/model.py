"""
模型路由 —— Agent 主模型
统一使用一个主模型，不区分逻辑/图片生成/图片理解
"""

from fastapi import APIRouter
from api_schemas.schemas import ModelSwitchRequest, OcrApiKeyRequest
from services import model_service
from config import AppState

router = APIRouter(prefix="/api/model", tags=["Model"])


@router.get("")
def get_model_status():
    """获取当前主模型状态和所有提供商"""
    return model_service.get_model_status()


@router.post("/switch")
def switch_model(req: ModelSwitchRequest):
    """切换主模型提供商和/或模型"""
    return model_service.switch_model(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
    )


@router.post("/apikey")
def save_api_key(req: ModelSwitchRequest):
    """单独保存 API Key（不切换模型）"""
    return model_service.switch_model(
        provider=req.provider or AppState.current_provider,
        model=None,
        api_key=req.api_key,
    )


@router.post("/ocr-apikey")
def save_ocr_api_key(req: OcrApiKeyRequest):
    """保存 DeepSeek-OCR API Key"""
    return model_service.save_ocr_api_key(req.api_key)
