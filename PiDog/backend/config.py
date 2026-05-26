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
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
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

# ---- 运行时状态 ----
class AppState:
    """全局单例状态"""
    current_provider: str = "bailian"        # 当前提供商 key
    current_model: str = "qwen-max"          # 当前模型
    custom_api_key: str = ""                 # 用户自填 key（优先级高于预设）

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
        qwen = data.get("qwen_config", {})
        PROVIDERS["bailian"]["api_key"] = qwen.get("api_key", "")
        AppState.current_model = qwen.get("model", "qwen-max")
        # 加载工作目录
        wd = data.get("working_directory", "")
        if wd:
            WORKING_DIRECTORY = wd.replace("\\", "/")
            os.makedirs(WORKING_DIRECTORY, exist_ok=True)

load_config_from_file()
