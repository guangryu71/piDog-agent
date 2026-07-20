"""
模型管理服务 —— 单一主模型
Agent 统一使用一个主模型，不区分逻辑/图片生成/图片理解
"""

import json
import os
from config import PROVIDERS, AppState, PROJECT_ROOT
from api_schemas.schemas import ModelStatus, ProviderInfo


def get_model_capabilities(model_name: str) -> dict:
    """检测模型的能力"""
    name = model_name.lower()
    return {
        "vision": any(kw in name for kw in ["vl", "vision", "minicpmv", "cogvlm",
                     "llava", "gpt-4o", "claude-3", "gemini", "qvq", "internvl",
                     "deepseek-vl", "phi-3-vision", "glm-4v"]),
        "ocr": any(kw in name for kw in ["ocr", "vl", "vision", "minicpmv",
                    "cogvlm", "llava", "gpt-4o", "claude-3", "gemini", "qvq",
                    "internvl", "deepseek-vl", "phi-3-vision", "glm-4v"]),
        "image_gen": any(kw in name for kw in ["flux", "stable-diffusion", "sd3",
                        "sana", "pixart", "kolors", "wanx", "dall-e",
                        "black-forest-labs", "stabilityai"]),
        "reasoning": any(kw in name for kw in ["r1", "qwq", "reasoning", "deepseek-r1", "o1-", "o3-"]),
    }


def get_model_status() -> ModelStatus:
    """获取当前模型状态"""
    current_model = AppState.get_effective_model()
    capabilities = get_model_capabilities(current_model)

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
        current_model=current_model,
        capabilities=capabilities,
        has_global_key=bool(AppState.custom_api_key or any(
            info.get("api_key") for info in PROVIDERS.values()
        )),
        has_ocr_key=bool(AppState.ocr_api_key),
        providers=providers,
    )


def switch_model(provider: str, model: str = None, api_key: str = None) -> dict:
    """切换模型提供商和/或模型，并同步写入 confing.json"""
    if provider not in PROVIDERS:
        return {"ok": False, "error": f"未知提供商: {provider}. 可选: {list(PROVIDERS.keys())}"}

    info = PROVIDERS[provider]

    if model and model not in info["models"]:
        return {"ok": False, "error": f"模型 '{model}' 不在提供商 '{provider}' 中. 可选: {info['models']}"}

    AppState.current_provider = provider
    if model:
        AppState.current_model = model
    else:
        AppState.current_model = info["default_model"]

    if api_key:
        AppState.custom_api_key = api_key
    else:
        # 切换提供商时清空旧 key（不同云厂商的 key 不通用）
        AppState.custom_api_key = ""

    _sync_config_to_file()
    return {
        "ok": True,
        "provider": AppState.current_provider,
        "model": AppState.current_model,
        "base_url": AppState.get_base_url(),
    }


def _sync_config_to_file():
    """将当前模型配置同步写入 confing.json"""
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    mc = data.setdefault("model_config", {})
    provider = AppState.current_provider
    info = PROVIDERS.get(provider, {})

    mc["provider"] = provider
    mc["model"] = AppState.current_model
    mc["base_url"] = info.get("base_url", mc.get("base_url", ""))
    # 写入 key：用户自定义 key 优先，否则用提供商预设 key，都没有则为空
    mc["api_key"] = AppState.custom_api_key or info.get("api_key", "")

    # 移除旧的不再使用的配置段
    data.pop("qwen_config", None)
    data.pop("img_gen_config", None)
    data.pop("img_und_config", None)

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


def save_ocr_api_key(api_key: str) -> dict:
    """保存 DeepSeek-OCR API Key 并写入 confing.json"""
    AppState.ocr_api_key = api_key
    _sync_ocr_key_to_config()
    import logging
    logging.getLogger("model").info("OCR API Key %s", "已保存" if api_key else "已清空")
    return {"ok": True, "has_ocr_key": bool(api_key)}


def _sync_ocr_key_to_config():
    """将 OCR API Key 写入 confing.json ocr_config 段"""
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    ocr = data.setdefault("ocr_config", {})
    ocr["api_key"] = AppState.ocr_api_key or ""

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import logging
        logging.getLogger("model").error("保存 OCR 配置失败: %s", e)
