"""
专业文件操作助手
提供文件定位、读取、写入、替换等专业功能
"""

from .tools import (
    locate_file,
    read_file_full,
    read_file_lines,
    write_file,
    replace_content,
    replace_lines,
    get_file_info,
    list_directory,
    get_file_structure,
    find_method
)

__all__ = [
    'locate_file',
    'read_file_full',
    'read_file_lines',
    'write_file',
    'replace_content',
    'replace_lines',
    'get_file_info',
    'list_directory',
    'get_file_structure',
    'find_method'
]