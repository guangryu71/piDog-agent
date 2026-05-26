import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.llm.llm_chat import LLMChat

def test_history_format():
    """
    测试历史记忆是否被正确转换为自然语言形式传给大模型
    """
    # 创建LLMChat实例（使用模拟参数）
    chat = LLMChat(api_key="fake_key", base_url="fake_url", model="fake_model", provider="fake_provider")
    
    # 读取当前的历史记录
    history_path = "history/history.json"
    if Path(history_path).exists():
        with open(history_path, 'r', encoding='utf-8') as f:
            history_messages = json.load(f)
    else:
        print(f"历史文件 {history_path} 不存在，使用空列表")
        history_messages = []
    
    # 手动执行历史记录格式化逻辑（模拟chat_with_memory中的逻辑）
    if history_messages:
        formatted_history = "以下是工作历史记忆：\n\n"
        for i, msg in enumerate(history_messages):
            role = msg.get("role", "")
            content = msg.get("content", "")
            run_result = msg.get("run_result", "")
            
            if role == "user":
                formatted_history += f"{i+1}. 用户询问: {content}\n"
            elif role == "assistant":
                formatted_history += f"{i+1}. 你: {content}\n"
            elif role == "system" and run_result:
                # 处理运行结果
                formatted_history += f"{i+1}. 运行结果: {run_result}\n"
            elif role == "system":
                formatted_history += f"{i+1}. 系统信息: {content}\n"
        
        print("格式化后的历史记忆:")
        print(formatted_history)
    else:
        print("没有历史记录")
    
    # 模拟当前用户消息
    current_user_message = "测试消息"
    messages = [{"role": "user", "content": current_user_message}]
    
    # 模拟系统提示词
    system_prompt = "你是一个智能助手"
    
    # 构建最终发送给大模型的消息列表
    all_messages = []
    
    # 添加系统提示词（如果历史中没有系统消息）
    has_system_msg = any(msg.get("role") == "system" for msg in history_messages)
    if system_prompt and not has_system_msg:
        all_messages.append({"role": "system", "content": system_prompt})
    
    # 添加格式化后的历史记录
    if history_messages:
        all_messages.append({"role": "system", "content": formatted_history})
    
    # 添加当前消息
    all_messages.extend(messages)
    
    print("\n发送给大模型的完整消息列表:")
    for i, msg in enumerate(all_messages):
        print(f"[{i}] Role: {msg['role']}, Content Length: {len(str(msg['content']))} chars")
        print(f"Content Preview: {str(msg['content'])[:200]}...")
        print("-" * 50)

if __name__ == "__main__":
    test_history_format()