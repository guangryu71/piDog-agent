"""
浏览器自动化工具 —— 基于原生 Playwright（不再依赖 QwenPaw 服务）

v4.0: 替换 qwenpaw_client.py，直接使用 Playwright 控制本地浏览器
"""

from .browser_engine import browser_use
from .browser_snapshot import build_role_snapshot_from_aria

__all__ = ['browser_use', 'build_role_snapshot_from_aria']
