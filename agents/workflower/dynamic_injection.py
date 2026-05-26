import json
import os
from pathlib import Path

def inject_history_to_workflower(skills_md: str = "", auto_file_skill: str = "", auto_shell_skill: str = "", working_directory: str = "", iteration_count: int = 1) -> str:
    """
    将技能信息注入到workflower.md中
    
    Args:
        skills_md: 技能信息内容字符串，默认为空字符串
        auto_file_skill: 文件操作技能内容字符串，默认为空字符串
        auto_shell_skill: Shell操作技能内容字符串，默认为空字符串
        working_directory: 工作目录路径，默认为空字符串
        iteration_count: 当前迭代次数，默认为1
        
    Returns:
        注入技能信息后的MD内容字符串
    """

    # 获取workflower.md文件路径
    script_dir = Path(__file__).resolve().parent
    workflower_md_path = script_dir / "workflower.md"
    
    with open(workflower_md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 如果提供了skills_md，则替换{skill_methods}占位符
    if skills_md:
        md_content = md_content.replace("{skill_methods}", skills_md)
    
    # 如果提供了auto_file_skill，则替换{auto_file_skill}占位符
    if auto_file_skill:
        md_content = md_content.replace("{auto_file_skill}", auto_file_skill)
    
    # 如果提供了auto_shell_skill，则替换{auto_shell_skill}占位符
    if auto_shell_skill:
        md_content = md_content.replace("{auto_shell_skill}", auto_shell_skill)
    
    # 如果提供了working_directory，则替换{WORKING_DIRECTORY}占位符
    if working_directory:
        md_content = md_content.replace("{WORKING_DIRECTORY}", working_directory)
    
    # 添加迭代次数提示（关键！）
    if iteration_count > 1:
        iteration_warning = f"""

## ⚠️ 极其重要：当前是第 {iteration_count} 次迭代
**你仍然必须且只能输出标准JSON格式！绝对不能因为之前的交互而改变输出格式！**

- 不管历史记忆中有什么，你当前这次响应**必须**是纯JSON
- **不要**模仿历史中的对话模式
- **不要**输出分析、解释、问候
- **直接**输出JSON对象，以 {{ 开始，以 }} 结束

**记住：每次迭代都是独立的，你必须始终输出JSON！**
"""
        # 在文件末尾添加迭代警告
        md_content += iteration_warning
    
    return md_content


def get_workflower_md_string(skills_md: str = "", auto_file_skill: str = "", auto_shell_skill: str = "", working_directory: str = "", iteration_count: int = 1) -> str:
    """
    生成workflower.md内容字符串，将技能信息动态注入
    注意：历史记忆已由API对话代理处理，无需在此处额外处理
    
    Args:
        skills_md: 技能信息内容字符串，默认为空字符串
        auto_file_skill: 文件操作技能内容字符串，默认为空字符串
        auto_shell_skill: Shell操作技能内容字符串，默认为空字符串
        working_directory: 工作目录路径，默认为空字符串
        iteration_count: 当前迭代次数，默认为1
        
    Returns:
        生成的MD内容字符串
    """
    return inject_history_to_workflower(skills_md, auto_file_skill, auto_shell_skill, working_directory, iteration_count)


def load_history_from_file(history_file_path: str = "history/history.json") -> str:
    """
    从历史文件中加载历史记忆内容
    
    Args:
        history_file_path: 历史文件路径，默认为 "history/history.json"
        
    Returns:
        历史记忆内容字符串
    """
    try:
        # 检查历史文件是否存在
        if not os.path.exists(history_file_path):
            raise FileNotFoundError(f"历史文件 {history_file_path} 不存在")
        
        # 读取历史文件
        with open(history_file_path, "r", encoding="utf-8") as f:
            history_data = json.load(f)
        
        # 将历史数据转换为字符串格式
        history_str = json.dumps(history_data, ensure_ascii=False, indent=2)
        return history_str
        
    except json.JSONDecodeError:
        print(f"错误: {history_file_path} 不是有效的JSON文件")
        return ""
    except FileNotFoundError as e:
        print(f"错误: {e}")
        return ""
    except Exception as e:
        print(f"加载历史文件时发生错误: {e}")
        return ""


def load_auto_skills() -> tuple[str, str]:
    """
    加载默认的文件操作和Shell操作技能内容
    
    Returns:
        包含(auto_file_skill, auto_shell_skill)的元组
    """
    try:
        # 读取文件操作技能内容
        auto_file_skill_path = "utils\\files_controler\\README.md"
        with open(auto_file_skill_path, 'r', encoding='utf-8') as file:
            auto_file_skill = file.read()
        
        # 读取Shell操作技能内容
        auto_shell_skill_path = "utils\\shell_controler\\README.md"
        with open(auto_shell_skill_path, 'r', encoding='utf-8') as file:
            auto_shell_skill = file.read()
        
        return auto_file_skill, auto_shell_skill
        
    except FileNotFoundError as e:
        print(f"错误: 无法找到技能文件 - {e}")
        return "", ""
    except Exception as e:
        print(f"加载技能内容时发生错误: {e}")
        return "", ""


def main():
    """主函数，演示动态注入功能"""
    # 注意：历史记忆已在API对话代理中处理，无需在此处加载
    # 加载默认技能内容
    auto_file_skill, auto_shell_skill = load_auto_skills()
    # 生成注入了技能内容的workflower.md和工作目录地址的内容
    md_content = get_workflower_md_string(
        skills_md="",
        auto_file_skill=auto_file_skill,
        auto_shell_skill=auto_shell_skill
    )
    print(md_content)


if __name__ == "__main__":
    main()