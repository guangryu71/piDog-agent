"""
PiDog Backend 配置 —— 多模型提供商 + 全局设置
"""

import os
import json
from typing import Dict, List
from pydantic import BaseModel

# ---- 项目根目录（smart_agent_new） ----
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---- 工作目录（从 confing.json 加载，所有工具的默认输出路径） ----
WORKING_DIRECTORY = ""

# ---- 提供商预设 ----
PROVIDERS: Dict[str, dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "default_model": "deepseek-v4-flash",
        "api_key": "",  # 用户填写
    },
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Pro/Qwen/Qwen2.5-7B-Instruct",
        ],
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "api_key": "",
    },
    "bailian": {
        "name": "阿里百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-max-latest"],
        "default_model": "qwen-max",
        "api_key": "",
    },
}

# ---- 图片生成模型配置 ----
IMAGE_GENERATION_PROVIDERS: Dict[str, dict] = {
    "dashscope_img_gen": {
        "name": "阿里百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "wanx2.1-t2i-turbo",
            "wanx2.1-i2i-turbo",
            "wanx2.1-t2i-plus",
            "flux-schnell",
        ],
        "default_model": "wanx2.1-t2i-turbo",
        "api_key": "",
    },
    "siliconflow_img_gen": {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "black-forest-labs/FLUX.1-schnell",
            "stabilityai/stable-diffusion-3-5-large",
            "Pro/black-forest-labs/FLUX.1-dev",
        ],
        "default_model": "black-forest-labs/FLUX.1-schnell",
        "api_key": "",
    },
}

# ---- 图片理解（多模态）模型配置 ----
IMAGE_UNDERSTANDING_PROVIDERS: Dict[str, dict] = {
    "dashscope_img_und": {
        "name": "阿里百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen-vl-max",
            "qwen-vl-plus",
            "qwen-vl-ocr",
        ],
        "default_model": "qwen-vl-max",
        "api_key": "",
    },
    "siliconflow_img_und": {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "Qwen/Qwen2.5-VL-72B-Instruct",
            "deepseek-ai/deepseek-vl2",
        ],
        "default_model": "Qwen/Qwen2.5-VL-72B-Instruct",
        "api_key": "",
    },
}


# ---- 运行时状态 ----
class AppState:
    """全局单例状态"""

    # 逻辑模型
    current_provider: str = "bailian"
    current_model: str = "qwen-max"
    custom_api_key: str = ""

    # 图片生成模型
    img_gen_provider: str = "dashscope_img_gen"
    img_gen_model: str = "wanx2.1-t2i-turbo"
    img_gen_api_key: str = ""

    # 图片理解模型
    img_und_provider: str = "dashscope_img_und"
    img_und_model: str = "qwen-vl-max"
    img_und_api_key: str = ""

    # 魔搭 MCP Token
    modelscope_token: str = ""

    # ---- 逻辑模型方法 ----
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

    # ---- 图片生成模型方法 ----
    @classmethod
    def get_img_gen_api_key(cls) -> str:
        if cls.img_gen_api_key:
            return cls.img_gen_api_key
        return IMAGE_GENERATION_PROVIDERS.get(cls.img_gen_provider, {}).get("api_key", "")

    @classmethod
    def get_img_gen_base_url(cls) -> str:
        return IMAGE_GENERATION_PROVIDERS.get(cls.img_gen_provider, {}).get("base_url", "")

    @classmethod
    def get_effective_img_gen_model(cls) -> str:
        return cls.img_gen_model or IMAGE_GENERATION_PROVIDERS.get(cls.img_gen_provider, {}).get("default_model", "")

    # ---- 图片理解模型方法 ----
    @classmethod
    def get_img_und_api_key(cls) -> str:
        if cls.img_und_api_key:
            return cls.img_und_api_key
        return IMAGE_UNDERSTANDING_PROVIDERS.get(cls.img_und_provider, {}).get("api_key", "")

    @classmethod
    def get_img_und_base_url(cls) -> str:
        return IMAGE_UNDERSTANDING_PROVIDERS.get(cls.img_und_provider, {}).get("base_url", "")

    @classmethod
    def get_effective_img_und_model(cls) -> str:
        return cls.img_und_model or IMAGE_UNDERSTANDING_PROVIDERS.get(cls.img_und_provider, {}).get("default_model", "")


def load_config_from_file():
    """从项目 confing.json 加载初始配置"""
    global WORKING_DIRECTORY
    config_path = os.path.join(PROJECT_ROOT, "confing.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 逻辑模型（原 qwen_config）
        qwen = data.get("qwen_config", {})
        provider_name = qwen.get("provider", "bailian")
        AppState.current_provider = provider_name
        AppState.current_model = qwen.get("model", "qwen-max")
        # 将 confing.json 中的 api_key 同步到对应 PROVIDER
        if provider_name in PROVIDERS and qwen.get("api_key"):
            PROVIDERS[provider_name]["api_key"] = qwen["api_key"]

        # 图片生成模型配置
        img_gen = data.get("img_gen_config", {})
        if img_gen.get("provider"):
            AppState.img_gen_provider = img_gen["provider"]
        if img_gen.get("model"):
            AppState.img_gen_model = img_gen["model"]
        if img_gen.get("api_key"):
            AppState.img_gen_api_key = img_gen["api_key"]

        # 图片理解模型配置
        img_und = data.get("img_und_config", {})
        if img_und.get("provider"):
            AppState.img_und_provider = img_und["provider"]
        if img_und.get("model"):
            AppState.img_und_model = img_und["model"]
        if img_und.get("api_key"):
            AppState.img_und_api_key = img_und["api_key"]

        # 魔搭 MCP 配置
        ms = data.get("modelscope_config", {})
        if ms.get("token"):
            AppState.modelscope_token = ms["token"]

        # 加载工作目录
        wd = data.get("working_directory", "")
        if wd:
            WORKING_DIRECTORY = wd.replace("\\", "/")
            os.makedirs(WORKING_DIRECTORY, exist_ok=True)

load_config_from_file()
