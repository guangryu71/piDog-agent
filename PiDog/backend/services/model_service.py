"""
模型管理服务 —— 逻辑模型 + 图片生成模型 + 图片理解模型
"""

import json
import os
from config import (
    PROVIDERS, AppState, PROJECT_ROOT,
    IMAGE_GENERATION_PROVIDERS, IMAGE_UNDERSTANDING_PROVIDERS,
)
from api_schemas.schemas import (
    ModelStatus, ProviderInfo,
    ImageGenProviderInfo, ImageUndProviderInfo,
)


# ==================== 逻辑模型 ====================

def get_model_status() -> ModelStatus:
    """获取当前逻辑模型状态"""
    providers = []
    for key, info in PROVIDERS.items():
        providers.append(ProviderInfo(
            key=key,
            name=info["name"],
            base_url=info["base_url"],
            models=info["models"],
            default_model=info["default_model"],
            has_key=bool(info.get("api_key") or AppState.custom_api_key),
        ))
    return ModelStatus(
        current_provider=AppState.current_provider,
        current_model=AppState.get_effective_model(),
        providers=providers,
    )


def switch_model(provider: str, model: str = None, api_key: str = None) -> dict:
    """切换逻辑模型提供商和/或模型，并同步写入 confing.json"""
    if provider not in PROVIDERS:
        return {"ok": False, "error": f"Unknown provider: {provider}. Options: {list(PROVIDERS.keys())}"}

    info = PROVIDERS[provider]

    if model and model not in info["models"]:
        return {"ok": False, "error": f"Model '{model}' not in provider '{provider}'. Options: {info['models']}"}

    AppState.current_provider = provider
    if model:
        AppState.current_model = model
    else:
        AppState.current_model = info["default_model"]

    if api_key:
        AppState.custom_api_key = api_key

    _sync_config_to_file()
    return {
        "ok": True,
        "provider": AppState.current_provider,
        "model": AppState.current_model,
        "base_url": AppState.get_base_url(),
    }


# ==================== 图片生成模型 ====================

def get_img_gen_status() -> dict:
    """获取图片生成模型状态"""
    providers = []
    for key, info in IMAGE_GENERATION_PROVIDERS.items():
        providers.append(ImageGenProviderInfo(
            key=key,
            name=info["name"],
            base_url=info["base_url"],
            models=info["models"],
            default_model=info["default_model"],
            has_key=bool(info.get("api_key") or AppState.img_gen_api_key),
        ))
    return {
        "current_provider": AppState.img_gen_provider,
        "current_model": AppState.get_effective_img_gen_model(),
        "providers": providers,
    }


def switch_img_gen(provider: str, model: str = None, api_key: str = None) -> dict:
    """切换图片生成模型"""
    if provider not in IMAGE_GENERATION_PROVIDERS:
        return {
            "ok": False,
            "error": f"Unknown provider: {provider}. Options: {list(IMAGE_GENERATION_PROVIDERS.keys())}",
        }

    info = IMAGE_GENERATION_PROVIDERS[provider]
    if model and model not in info["models"]:
        return {"ok": False, "error": f"Model '{model}' not found. Options: {info['models']}"}

    AppState.img_gen_provider = provider
    if model:
        AppState.img_gen_model = model
    else:
        AppState.img_gen_model = info["default_model"]
    if api_key:
        AppState.img_gen_api_key = api_key

    _sync_image_config_to_file("img_gen_config", provider, AppState.img_gen_model, api_key)
    return {
        "ok": True,
        "provider": AppState.img_gen_provider,
        "model": AppState.img_gen_model,
        "base_url": AppState.get_img_gen_base_url(),
    }


# ==================== 图片理解模型 ====================

def get_img_und_status() -> dict:
    """获取图片理解模型状态"""
    providers = []
    for key, info in IMAGE_UNDERSTANDING_PROVIDERS.items():
        providers.append(ImageUndProviderInfo(
            key=key,
            name=info["name"],
            base_url=info["base_url"],
            models=info["models"],
            default_model=info["default_model"],
            has_key=bool(info.get("api_key") or AppState.img_und_api_key),
        ))
    return {
        "current_provider": AppState.img_und_provider,
        "current_model": AppState.get_effective_img_und_model(),
        "providers": providers,
    }


def switch_img_und(provider: str, model: str = None, api_key: str = None) -> dict:
    """切换图片理解模型"""
    if provider not in IMAGE_UNDERSTANDING_PROVIDERS:
        return {
            "ok": False,
            "error": f"Unknown provider: {provider}. Options: {list(IMAGE_UNDERSTANDING_PROVIDERS.keys())}",
        }

    info = IMAGE_UNDERSTANDING_PROVIDERS[provider]
    if model and model not in info["models"]:
        return {"ok": False, "error": f"Model '{model}' not found. Options: {info['models']}"}

    AppState.img_und_provider = provider
    if model:
        AppState.img_und_model = model
    else:
        AppState.img_und_model = info["default_model"]
    if api_key:
        AppState.img_und_api_key = api_key

    _sync_image_config_to_file("img_und_config", provider, AppState.img_und_model, api_key)
    return {
        "ok": True,
        "provider": AppState.img_und_provider,
        "model": AppState.img_und_model,
        "base_url": AppState.get_img_und_base_url(),
    }


# ==================== 配置文件同步 ====================

def _sync_config_to_file():
    """将当前逻辑模型配置同步写入 confing.json"""
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    qc = data.setdefault("qwen_config", {})
    provider = AppState.current_provider
    info = PROVIDERS.get(provider, {})

    qc["provider"] = provider
    qc["model"] = AppState.current_model
    qc["base_url"] = info.get("base_url", qc.get("base_url", ""))
    if AppState.custom_api_key:
        qc["api_key"] = AppState.custom_api_key
    elif info.get("api_key") and not qc.get("api_key"):
        qc["api_key"] = info["api_key"]

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        import logging
        logging.getLogger("model").info(
            "配置已保存: provider=%s model=%s -> %s",
            AppState.current_provider, AppState.current_model, config_path,
        )
    except Exception as e:
        import logging
        logging.getLogger("model").error("保存配置失败 %s: %s", config_path, e)


def _sync_image_config_to_file(section: str, provider: str, model: str, api_key: str = None):
    """将图片模型配置同步写入 confing.json"""
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    cfg = data.setdefault(section, {})
    cfg["provider"] = provider
    cfg["model"] = model
    if api_key:
        cfg["api_key"] = api_key

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
