"""
V1 Pipeline: 动态注入 — 扫描 skills/ 文件夹生成 thinke.md 的内容
取代原来读取 skills_locator.json 的方式，改用 tool_registry.scan_skills()
"""

import json
import os
from pathlib import Path


def load_config(config_path: str = "confing.json") -> dict:
    """配置导入方法"""
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        print("配置加载成功!")
        return config_data
    except json.JSONDecodeError:
        print(f"错误: {config_path} 不是有效的JSON文件")
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"加载配置时发生错误: {e}")
    return {}


def generate_thinker_md_from_skills(skills_data):
    """
    根据技能数据生成 thinke.md 内容字符串

    Args:
        skills_data: {skill_name: description} 字典

    Returns:
        生成的MD内容字符串
    """
    script_dir = Path(__file__).resolve().parent
    thinker_md_path = script_dir / "thinker.md"

    with open(thinker_md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    skills_section = ""
    for name, desc in sorted(skills_data.items()):
        skills_section += f"\n### {name}\n"
        skills_section += f"- **描述**: {desc}\n"
        skills_section += f"- **文档路径**: skills/{name}/README.md\n"

    md_content = md_content.replace("{skills_data}", skills_section)
    return md_content


def get_thinker_md_string() -> str:
    """
    扫描 skills/ 文件夹，生成 thinke.md 内容字符串。
    用 scan_skills() 取代原来读取 skills_locator.json。
    """
    from utils.tool_registry import scan_skills
    skills_data = scan_skills()
    return generate_thinker_md_from_skills(skills_data)


def main():
    md_content = get_thinker_md_string()
    print(md_content)


if __name__ == "__main__":
    main()
