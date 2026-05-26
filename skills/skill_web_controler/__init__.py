"""
浏览器自动化控制技能（基于 QwenPaw）

通过调用 QwenPaw 服务的统一聊天接口，实现网页浏览、数据采集、表单填写等浏览器自动化操作。
当用户需要进行网页浏览、数据采集、表单填写等操作时触发此技能。

核心原则：
- 只有一个工具函数 execute_browser_command
- 所有浏览器操作通过自然语言指令发送给 QwenPaw
- QwenPaw 负责解析指令并执行具体操作
"""

from .tools import execute_browser_command

__all__ = ['execute_browser_command']
