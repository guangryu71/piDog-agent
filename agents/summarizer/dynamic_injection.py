def get_summarizer_md():
    """
    获取summarizer.md文件的内容并返回字符串
    """
    import os
    
    # 获取当前文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建summarizer.md的完整路径
    summarizer_md_path = os.path.join(current_dir, 'summarizer.md')
    
    # 读取并返回summarizer.md文件的内容
    with open(summarizer_md_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    return content