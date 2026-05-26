"""
浏览器自动化工具 - 从 skills/skill_web_controler/tools 迁移到 utils 统一管理
"""

from .qwenpaw_client import run, QwenPawClient

__all__ = ['run', 'QwenPawClient']
