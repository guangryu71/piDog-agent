"""
模型管理服务 —— 提供商切换、模型选择
"""

from config import PROVIDERS, AppState
from api_schemas.schemas import ModelStatus, ProviderInfo


def get_model_status() -> ModelStatus:
    """获取当前模型状态"""
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
    """切换模型提供商和/或模型"""
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

    return {
        "ok": True,
        "provider": AppState.current_provider,
        "model": AppState.current_model,
        "base_url": AppState.get_base_url(),
    }
