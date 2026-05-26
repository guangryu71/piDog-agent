import json
import os
from pathlib import Path


SKILLS_LOCATOR_PATH: str = ""
def load_config(config_path: str = "confing.json") -> None:
    """
    配置导入方法，从配置文件中加载配置并赋值给全局常量
    
    Args:
        config_path: 配置文件路径，默认为 "confing.json"
    """
    global SKILLS_LOCATOR_PATH
    
    try:
        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        
        # 读取配置文件
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        # 从配置文件中提取各项配置并赋值给常量
        SKILLS_LOCATOR_PATH = config_data.get("skills_locator_path", "")
        print("skill注册器配置加载成功!")
        return SKILLS_LOCATOR_PATH
    
        
    except json.JSONDecodeError:
        print(f"错误: {config_path} 不是有效的JSON文件")
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"加载配置时发生错误: {e}")

def generate_thinker_md_from_skills(skills_data):
    """
    根据skills_locator.json数据生成checker.md内容字符串
    
    Args:
        skills_data: skills_locator.json的数据（字典格式）
        
    Returns:
        生成的MD内容字符串
    """
    # 直接读取thinker.md文件内容
    script_dir = Path(__file__).resolve().parent
    thinker_md_path = script_dir / "thinker.md"
    
    with open(thinker_md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 替换skills_data占位符为实际的技能数据
    import re
    skills_section = ""
    
    # 遍历技能数据，生成技能列表
    for key, value in skills_data.items():
        if key in ['version', 'description', 'statistics']:
            continue  # 跳过元数据字段
        
        if isinstance(value, dict) and 'description' in value and 'readme_path' in value:
            skills_section += f"\n### {key}\n"
            skills_section += f"- **描述**: {value['description']}\n"
            skills_section += f"- **文档路径**: {value['readme_path']}\n"
            # 如果有 keywords 字段，添加到生成内容中
            if 'keywords' in value and isinstance(value['keywords'], list) and len(value['keywords']) > 0:
                keywords_str = "、".join(value['keywords'])
                skills_section += f"- **匹配关键词**: {keywords_str}\n"
    
    # 将skills_data替换到md_content中
    md_content = md_content.replace("{skills_data}", skills_section)
    
    return md_content
    
def get_thinker_md_string() -> str:
    """
    生成checker.md内容字符串，将skills_locator.json的内容动态注入
    
    Args:
        skills_json_path: skills_locator.json文件路径
        
    Returns:
        生成的MD内容字符串
    """
    # 先获取skills_locator.json的位置
    skills_locator_path = load_config()
    skills_data = {}
    print(f"skills_locator.json位置：{skills_locator_path}")
    if skills_locator_path is None:
        # 使用相对路径找到skills_locator.json
        script_dir = Path(__file__).resolve().parent
        skills_locator_path = script_dir.parent.parent / "skills_locator.json"
    
    with open(skills_locator_path, 'r', encoding='utf-8') as f:
        skills_data=json.load(f)
    return generate_thinker_md_from_skills(skills_data)


def main():
    """主函数，执行动态注入"""
    md_content = get_thinker_md_string()
    print(md_content)  

if __name__ == "__main__":
    # load_config()
    # print(f"S{SKILLS_LOCATOR_PATH}")
    main()