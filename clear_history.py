"""
清空历史文件
"""
import json

def clear_history():
    history_path = "history/history.json"
    
    # 清空历史文件
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    
    print(f"✓ 历史文件已清空: {history_path}")

if __name__ == "__main__":
    clear_history()
