"""
skill_web_controler - 浏览器自动化控制工具集（QwenPaw 代理）

核心原则：
- 只有一个工具函数 execute_browser_command
- 所有浏览器操作通过自然语言指令发送给 QwenPaw
- QwenPaw 负责解析指令并执行具体操作
- 本模块只负责转发请求和接收响应

工具模块：qwenpaw_client.py
"""

from .qwenpaw_client import QwenPawClient, PendingApproval, run as execute_browser_command

# 导出主要的工具函数和类
__all__ = ['execute_browser_command', 'QwenPawClient', 'PendingApproval']
