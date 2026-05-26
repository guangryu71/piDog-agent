def get_checker_md():
    """
    获取checker.md文件的内容并返回字符串
    """
    import os
    
    # 获取当前文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建checker.md的完整路径
    checker_md_path = os.path.join(current_dir, 'checker.md')
    
    # 检查文件是否存在
    if not os.path.exists(checker_md_path):
        raise FileNotFoundError(f"checker.md文件不存在: {checker_md_path}")
    
    # 读取并返回checker.md文件的内容
    with open(checker_md_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    return content