"""
PiDog Backend 配置 —— 单一提供商 + Agent 主模型
Agent 统一使用一个主模型进行工作，不区分逻辑/图片生成/图片理解
"""

import os
import json
from typing import Dict, List
from pydantic import BaseModel

# ---- 项目根目录（smart_agent_new） ----
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---- 工作目录（从 confing.json 加载，所有工具的默认输出路径） ----
WORKING_DIRECTORY = ""

# ---- 云提供商预设 ----
PROVIDERS: Dict[str, dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-ocr"],
        "default_model": "deepseek-v4-flash",
        "api_key": "",
    },
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-VL-72B-Instruct",
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Pro/Qwen/Qwen2.5-7B-Instruct",
            "black-forest-labs/FLUX.1-schnell",
            "stabilityai/stable-diffusion-3-5-large",
            "CosyVoice2-0.5B",
        ],
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "api_key": "",
    },
    "bailian": {
        "name": "阿里百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen-max", "qwen-plus", "qwen-turbo", "qwen-max-latest",
            "qwen-vl-max", "qwen-vl-plus",
            "wanx2.1-t2i-turbo", "wanx2.1-i2i-turbo",
        ],
        "default_model": "qwen-max",
        "api_key": "",
    },
}


# ---- 运行时状态 ----
class AppState:
    """全局单例状态 —— Agent 统一使用一个主模型"""

    current_provider: str = "bailian"
    current_model: str = "qwen-max"
    custom_api_key: str = ""

    # 魔搭 MCP Token
    modelscope_token: str = ""

    # DeepSeek-OCR 专用 API Key
    ocr_api_key: str = ""

    @classmethod
    def get_api_key(cls) -> str:
        if cls.custom_api_key:
            return cls.custom_api_key
        return PROVIDERS.get(cls.current_provider, {}).get("api_key", "")

    @classmethod
    def get_base_url(cls) -> str:
        return PROVIDERS.get(cls.current_provider, {}).get("base_url", "")

    @classmethod
    def get_effective_model(cls) -> str:
        return cls.current_model or PROVIDERS.get(cls.current_provider, {}).get("default_model", "")


def load_config_from_file():
    """从项目 confing.json 加载初始配置"""
    global WORKING_DIRECTORY
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 主模型配置（兼容旧字段 qwen_config / model_config）
        mc = data.get("model_config") or data.get("qwen_config", {})
        provider_name = mc.get("provider", "bailian")
        AppState.current_provider = provider_name
        AppState.current_model = mc.get("model", "qwen-max")
        if provider_name in PROVIDERS:
            PROVIDERS[provider_name]["api_key"] = mc.get("api_key", "") or ""

        # 魔搭 MCP 配置
        ms = data.get("modelscope_config", {})
        if ms.get("token"):
            AppState.modelscope_token = ms["token"]

        # 加载工作目录
        wd = data.get("working_directory", "")
        if wd:
            WORKING_DIRECTORY = wd.replace("\\", "/")
            os.makedirs(WORKING_DIRECTORY, exist_ok=True)

        # 加载 OCR 专用 Key
        ocr_cfg = data.get("ocr_config", {})
        if ocr_cfg.get("api_key"):
            AppState.ocr_api_key = ocr_cfg["api_key"]

load_config_from_file()
