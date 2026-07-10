import openai
import json
import os
from typing import List, Dict, Optional
from datetime import datetime


class LLMChat:
    def __init__(self, api_key: str, base_url: str = None, model: str = "qwen-max", provider: str = "qwen", max_tokens: int = 3000, temperature: float = 0.7):
        """
        初始化LLM聊天对象
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 使用的模型名称
            provider: 模型提供商 ('qwen' 等)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.provider = provider.lower()
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # 设置OpenAI客户端（兼容通义千问等API）
        if base_url:
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = openai.OpenAI(api_key=api_key)
    
    def chat_with_tools(
            self,
            messages: List[Dict],
            tools: List[Dict],
            temperature: float = None,
            max_tokens: int = None,
            system_prompt: str = None,
            tool_choice: str = "auto",
            **kwargs
    ):
        """
        ✨ 原生 Function Calling —— 替代旧的"裸输出 JSON"方案

        将工具 Schema 直接传给大模型，大模型按 Schema 输出结构化 tool_calls。
        系统拿到 tool_calls 后按 Schema 校验执行，不再依赖正则解析 JSON。

        Args:
            messages: 消息列表
            tools: 工具 Schema 列表（来自 tool_registry.get_tool_schemas()）
            system_prompt: 系统提示词
            tool_choice: "auto"=自动选择, "none"=禁用, "required"=强制调用
            **kwargs: 其他参数

        Returns:
            OpenAI chat completion response 对象
            - response.choices[0].message.tool_calls → 工具调用列表
            - response.choices[0].message.content → 文本响应
        """
        processed_messages = []
        if system_prompt:
            processed_messages.append({"role": "system", "content": system_prompt})
        processed_messages.extend(messages)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                **kwargs
            )
            return response
        except Exception as e:
            raise Exception(f"Function Calling API 调用失败: {str(e)}")

    def chat_with_tools_stream(
            self,
            messages: List[Dict],
            tools: List[Dict],
            temperature: float = None,
            max_tokens: int = None,
            system_prompt: str = None,
            tool_choice: str = "auto",
            **kwargs
    ):
        """
        🚀 流式 Function Calling —— 边生成边返回 chunk，前端实现渐进式渲染

        与 chat_with_tools 参数相同，区别在于：
        - stream=True，返回迭代器而非完整 response
        - 每个 chunk 含 delta.tool_calls（工具名/参数逐 token 出现）
        - 最后一个 chunk 含 usage token 统计（需 stream_options={"include_usage": True}）

        Returns:
            OpenAI chat completion stream 迭代器
        """
        processed_messages = []
        if system_prompt:
            processed_messages.append({"role": "system", "content": system_prompt})
        processed_messages.extend(messages)

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs
            )
            return stream
        except Exception as e:
            raise Exception(f"Function Calling 流式 API 调用失败: {str(e)}")

    def chat_no_memory(self, 
                      messages: List[Dict], 
                      temperature: float = None, 
                      max_tokens: int = None,
                      stream: bool = False,
                      system_prompt: str = None,
                      **kwargs) -> str:
        """
        不带记忆的聊天方法
        
        Args:
            messages: 消息列表，格式为[{"role": "user", "content": "消息内容"}, ...]
            temperature: 温度参数，控制生成的随机性
            max_tokens: 最大token数
            stream: 是否流式返回
            system_prompt: 系统提示词，用于设定AI的行为和角色
            **kwargs: 其他传递给API的参数
            
        Returns:
            生成的回复内容
        """
        # 如果提供了系统提示词，则将其添加到消息列表的开头
        processed_messages = []
        if system_prompt:
            processed_messages.append({"role": "system", "content": system_prompt})
        processed_messages.extend(messages)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )
            
            if stream:
                # 流式响应处理
                full_response = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                return full_response
            else:
                # 非流式响应
                return response.choices[0].message.content
                
        except Exception as e:
            raise Exception(f"API调用失败: {str(e)}")
    
    def chat_with_memory(self, 
                        messages: List[Dict], 
                        history_file: str,
                        temperature: float = None, 
                        max_tokens: int = None,
                        stream: bool = False,
                        system_prompt: str  = "",
                        agent_name: str = None,
                        **kwargs) -> str:
        """
        带记忆的聊天方法
        
        Args:
            messages: 消息列表，格式为[{"role": "user", "content": "消息内容"}, ...]
            history_file: 历史记录保存文件路径
            temperature: 温度参数，控制生成的随机性
            max_tokens: 最大token数
            stream: 是否流式返回
            system_prompt: 系统提示词，用于设定AI的行为和角色
            agent_name: 代理名称，用于特殊处理某些代理的响应
            **kwargs: 其他传递给API的参数
            
        Returns:
            生成的回复内容
        """
        # 加载历史记录
        history_messages = self._load_history(history_file)
        
        # 如果提供了系统提示词，则将其作为第一条消息
        all_messages = []
        if system_prompt:
            # 检查历史记录中是否已有系统消息，如果没有则添加
            has_system_msg = any(msg.get("role") == "system" for msg in history_messages)
            if not has_system_msg:
                all_messages.append({"role": "system", "content": system_prompt})
        
        # 将历史记录格式化为自然语言形式
        if history_messages:
            formatted_history = "以下是工作历史记忆：\n\n"
            for msg in history_messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                run_result = msg.get("run_result", "")
                
                if role == "user":
                    formatted_history += f"用户询问: {content}\n"
                elif role == "assistant":
                    # 处理可能包含Markdown的内容，保留换行和格式
                    formatted_history += f"你: {content}\n"
                elif role == "system" and run_result:
                    # 处理运行结果，格式化显示
                    formatted_history += f"运行结果: {run_result}\n"
                elif role == "system":
                    formatted_history += f"系统信息: {content}\n"
            
            # 将格式化后的历史记录作为系统消息添加到消息列表中
            all_messages.append({"role": "system", "content": formatted_history})
        
        # 添加当前消息
        all_messages.extend(messages)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=all_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )
            
            if stream:
                # 流式响应处理
                full_response = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        
                # 添加当前请求和响应到历史记录
                # 检查是否已有用户消息，如果没有则添加（只在开头保存一次用户需求）
                has_user_message = any(msg.get("role") == "user" for msg in history_messages)
                if not has_user_message:
                    for msg in messages:
                        history_messages.append(msg)
                
                # 特殊处理workflower代理的响应
                if agent_name == "workflower":
                    # 解析workflower的响应，只提取operations中的description
                    try:
                        parsed_response = self._parse_workflower_response(full_response)
                        simplified_content = self._extract_descriptions(parsed_response)
                        history_messages.append({
                            "role": "assistant",
                            "content": simplified_content
                        })
                    except (ValueError, json.JSONDecodeError) as e:
                        # 解析失败时的降级处理
                        import re
                        # 尝试从原始响应中提取description字段的内容
                        desc_matches = re.findall(r'"description"\s*:\s*"([^"]*)"', full_response)
                        if desc_matches:
                            simplified_content = "工作流操作描述:\n" + "\n".join([f"- {desc}" for desc in desc_matches[:5]])
                        else:
                            simplified_content = "执行了工作流操作"
                        
                        history_messages.append({
                            "role": "assistant",
                            "content": simplified_content
                        })
                else:
                    history_messages.append({
                        "role": "assistant",
                        "content": full_response
                    })
                
                # 保存更新后的历史记录
                self._save_history(history_file, history_messages)
                
                return full_response
            else:
                # 非流式响应
                assistant_reply = response.choices[0].message.content
                
                # 添加当前请求和响应到历史记录
                # 检查是否已有用户消息，如果没有则添加（只在开头保存一次用户需求）
                has_user_message = any(msg.get("role") == "user" for msg in history_messages)
                if not has_user_message:
                    for msg in messages:
                        history_messages.append(msg)
                
                # 特殊处理workflower代理的响应
                if agent_name == "workflower":
                    # 解析workflower的响应，只提取operations中的description
                    try:
                        parsed_response = self._parse_workflower_response(assistant_reply)
                        simplified_content = self._extract_descriptions(parsed_response)
                        history_messages.append({
                            "role": "assistant",
                            "content": simplified_content
                        })
                    except (ValueError, json.JSONDecodeError) as e:
                        # 解析失败时的降级处理
                        import re
                        # 尝试从原始响应中提取description字段的内容
                        desc_matches = re.findall(r'"description"\s*:\s*"([^"]*)"', assistant_reply)
                        if desc_matches:
                            simplified_content = "工作流操作描述:\n" + "\n".join([f"- {desc}" for desc in desc_matches[:5]])
                        else:
                            simplified_content = "执行了工作流操作"
                        
                        history_messages.append({
                            "role": "assistant",
                            "content": simplified_content
                        })
                else:
                    history_messages.append({
                        "role": "assistant",
                        "content": assistant_reply
                    })
                
                # 保存更新后的历史记录
                self._save_history(history_file, history_messages)
                
                return assistant_reply
                
        except Exception as e:
            raise Exception(f"API调用失败: {str(e)}")

    def _extract_descriptions(self, parsed_response: dict) -> str:
        """
        从workflower响应中提取description信息
        
        Args:
            parsed_response: 解析后的响应字典
            
        Returns:
            包含所有操作描述的字符串
        """
        descriptions = []
        
        if isinstance(parsed_response, dict) and 'operations' in parsed_response:
            operations = parsed_response['operations']
            if isinstance(operations, list):
                for i, op in enumerate(operations):
                    if isinstance(op, dict) and 'description' in op:
                        descriptions.append(f"操作{i+1}: {op['description']}")
        
        return "\n".join(descriptions) if descriptions else "执行了工作流操作"
    
    def _parse_workflower_response(self, response_text: str) -> dict:
        """
        解析workflower的响应，支持markdown格式
        
        Args:
            response_text: 原始响应文本
            
        Returns:
            解析后的字典
        """
        import re
        
        # 首先尝试直接解析
        try:
            return json.loads(response_text)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # 尝试从 markdown 代码块中提取 JSON
        # 匹配 ```json ... ``` 或 ``` ... ```
        json_match = re.search(r'```(?:json)?\s*\n?({.*?})\n?\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            return json.loads(json_str)
        
        # 如果还是没有找到，尝试直接查找大括号内容
        start_pos = response_text.find('{')
        end_pos = response_text.rfind('}')
        if start_pos != -1 and end_pos != -1:
            json_str = response_text[start_pos:end_pos+1]
            return json.loads(json_str)
        
        raise ValueError("无法从响应中提取JSON内容")
    
    def _load_history(self, history_file: str) -> List[Dict]:
        """
        从文件加载历史记录
        
        Args:
            history_file: 历史记录文件路径
            
        Returns:
            历史消息列表
        """
        if not os.path.exists(history_file):
            # 如果文件不存在，创建一个空的历史记录
            os.makedirs(os.path.dirname(history_file), exist_ok=True)
            self._save_history(history_file, [])
            return []
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
                # 如果是 JSON 格式（旧格式）
                if content.startswith('['):
                    return json.loads(content)
                
                # 如果是 Markdown 格式（新格式）
                return self._parse_markdown_history(content)
                
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _parse_markdown_history(self, markdown_content: str) -> List[Dict]:
        """
        解析 Markdown 格式的历史记录
        
        Args:
            markdown_content: Markdown 格式的历史记录内容
            
        Returns:
            历史消息列表
        """
        import re
        
        messages = []
        
        # 分割不同的消息块（使用 --- 分隔符）
        blocks = re.split(r'\n---\n', markdown_content)
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # 提取角色
            role_match = re.search(r'\*\*角色\*\*:\s*(\w+)', block)
            if not role_match:
                continue
            
            role = role_match.group(1).strip()
            
            # 提取内容（从 **内容**: 之后到块结尾）
            content_match = re.search(r'\*\*内容\*\*:\s*\n?(.*)', block, re.DOTALL)
            if not content_match:
                continue
            
            content = content_match.group(1).strip()
            
            # 处理 run_result（系统运行结果）
            run_result = ""
            if role == "system":
                # 对于系统消息，将内容作为 run_result
                run_result = content
                content = "以下为上面工作流操作的方法运行结果:"
            
            messages.append({
                "role": role,
                "content": content,
                "run_result": run_result
            })
        
        return messages
    
    def _save_history(self, history_file: str, messages: List[Dict]):
        """
        保存历史记录到文件（Markdown 格式）
        
        Args:
            history_file: 历史记录文件路径
            messages: 要保存的消息列表
        """
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        
        # 将文件扩展名改为 .md
        if history_file.endswith('.json'):
            history_file = history_file.replace('.json', '.md')
        
        with open(history_file, 'w', encoding='utf-8') as f:
            f.write("# 工作记忆历史\n\n")
            
            assistant_count = 0
            system_count = 0
            
            for i, msg in enumerate(messages):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                run_result = msg.get("run_result", "")
                
                # 根据角色生成标题
                if role == "user":
                    f.write("## 用户请求\n")
                elif role == "assistant":
                    assistant_count += 1
                    f.write(f"## 助手回复 #{assistant_count}\n")
                elif role == "system":
                    system_count += 1
                    f.write(f"## 系统运行结果 #{system_count}\n")
                else:
                    f.write(f"## 消息 #{i+1}\n")
                
                # 写入角色信息
                f.write(f"**角色**: {role}\n")
                
                # 写入内容
                if run_result:
                    # 如果有运行结果，格式化显示
                    f.write(f"**内容**: \n{content}\n\n")
                    # 将运行结果格式化为列表
                    # 解析运行结果中的各个操作
                    operations = run_result.split('\n')
                    for op in operations:
                        op = op.strip()
                        if op and not op.startswith('以下为上面'):
                            f.write(f"- {op}\n")
                else:
                    # 普通内容直接写入
                    f.write(f"**内容**: \n{content}\n")
                
                # 添加分隔符
                f.write("\n---\n\n")


def create_chat_from_config(config_path: str = "confing.json"):
    """
    根据配置文件创建LLMChat实例（默认使用国内模型提供商）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        LLMChat实例
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # 默认使用通义千问配置
    provider_config = config.get("qwen_config", {})
    
    api_key = provider_config.get("api_key")
    base_url = provider_config.get("base_url")
    model = provider_config.get("model", "qwen-max")
    provider = provider_config.get("provider", "qwen")
    max_tokens = provider_config.get("max_tokens", 3000)
    temperature = provider_config.get("temperature", 0.7)

    
    return LLMChat(api_key=api_key, base_url=base_url, model=model, provider=provider, max_tokens=max_tokens, temperature=temperature)


# 示例用法函数
def chat_with_memory_main(user_message: str, system_prompt: str, agent_name: str = None):
    # """示例用法，仅在显式调用时才执行"""
    chat = create_chat_from_config()
    # 测试带记忆的聊天
    import json
    with open("confing.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    history_file = config.get("history_path")
    print(f"记忆文件: {history_file}")
    
    # 获取的系统提示词
    # print(f"系统提示词:\n {system_prompt}")
        
    # 使用带系统提示词的带记忆聊天
    model_chat_messages = [{"role": "user", "content": f"{user_message}"}]
    response_with_memory = chat.chat_with_memory(
        messages=model_chat_messages, 
        temperature=chat.temperature,
        max_tokens=chat.max_tokens,
        history_file=history_file,
        system_prompt=system_prompt,
        agent_name=agent_name
    )
    return(response_with_memory)


def chat_no_memery_main(user_message: str, system_prompt: str):
    chat = create_chat_from_config()
    model_chat_messages = [{"role": "user", "content": f"{user_message}"}]
    response_with_no_memory = chat.chat_no_memory(
        messages=model_chat_messages, 
        temperature=chat.temperature,
        max_tokens=chat.max_tokens,
        system_prompt=system_prompt,
    )
    return(response_with_no_memory)
# 只有在直接运行此文件时才执行示例代码
if __name__ == "__main__":
    response = chat_with_memory_main("构建学生管理系统","""
                                     
# 工作指导专家

## 角色定义
你是工作指导专家，专门处理阶段性工作执行过程中的相关指导。我负责根据历史记忆检查当前工作流程，识别潜在问题，并提供相应的修复建议。对于不需要结束工作的流程（if_end_all_work=False），我会根据记忆指出工作的问题并提供改进建议。

## 核心职责
- 检查工作流执行结果中的错误
- 验证操作的正确性和完整性
- 根据工作记忆发现问题并提供解决方案
- 在发现问题时提供修复建议

## 工作逻辑
根据if_end_all_work的状态进行不同处理：
- 如果 if_have_error==True:  生成error_position和suggestion
- 如果 if_have_error==False: 只生成简洁的阶段性工作总结suggestion

## 核心规则 ##
请根据下面的返回格式规范生成正确的内容,不返回纯json内容即认为失败,没有任何商量的余地,只能生成json内容!

## 返回格式,非常重要！一定要实现 ##
- 必须以标准化JSON格式输出结果
- 重要的事情说三遍！:
- 只需要返回下面定义的json内容，其他内容不要生成！
- 只需要返回下面定义的json内容，其他内容不要生成！
- 只需要返回下面定义的json内容，其他内容不要生成！

``json
{
  "if_have_error": True/False,
  "error_position": "如果有错误则用文字描述错误点或者位置，没错则为空",
  "suggestion": "如果有错误则用文字描述修复建议，没错则生成简洁的阶段性工作总结"
}
```

## 重要! ##
- 只需要返回上面定义的json内容，其他内容不要生成！
- 只需要返回上面定义的json内容，其他内容不要生成！
- 只需要返回上面定义的json内容，其他内容不要生成！

## JSON属性说明
- if_have_error: (必有)布尔值，表示是否有错误
- error_position: (没有错误就为空，有错误就必填)字符串，指出错误位置
- suggestion: (如果有错误则描述修复建议，如果没有错误则生成简洁的阶段性工作总结)字符串，提供修复建议或工作总结


                                     """)
    print(response)
