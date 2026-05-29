"""
模型管理服务 —— 提供商切换、模型选择
"""

import json
import os
from config import PROVIDERS, AppState, PROJECT_ROOT
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


def _sync_config_to_file():
    """将当前 AppState 中的模型配置同步写入 confing.json"""
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    # 更新 qwen_config 中的关键字段
    qc = data.setdefault("qwen_config", {})
    provider = AppState.current_provider
    info = PROVIDERS.get(provider, {})

    qc["provider"] = provider
    qc["model"] = AppState.current_model
    qc["base_url"] = info.get("base_url", qc.get("base_url", ""))
    # 保留可能手动填入的 api_key（不覆盖）
    if AppState.custom_api_key:
        qc["api_key"] = AppState.custom_api_key
    elif info.get("api_key") and not qc.get("api_key"):
        qc["api_key"] = info["api_key"]

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def switch_model(provider: str, model: str = None, api_key: str = None) -> dict:
    """切换模型提供商和/或模型，并同步写入 confing.json"""
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

    # 同步写入 confing.json
    _sync_config_to_file()

    return {
        "ok": True,
        "provider": AppState.current_provider,
        "model": AppState.current_model,
        "base_url": AppState.get_base_url(),
    }
