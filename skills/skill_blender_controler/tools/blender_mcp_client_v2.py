"""
Blender MCP 客户端 - 通过 MCP 协议与 Blender 通信
通过 TCP Socket (line-delimited JSON) 与 Blender MCP 服务交互
端口: 9876
消息格式: {"type": "execute_code", "params": {"code": "..."}}
"""

import json
import sys
import time
import socket
from typing import Dict, Any, Optional
from pathlib import Path


def _log_ok(func: str, detail: str = "") -> None:
    """成功日志"""
    detail_str = f" | {detail}" if detail else ""
    print(f"[✅ {func} 成功]{detail_str}", file=sys.stderr, flush=True)


def _log_fail(func: str, reason: str) -> None:
    """失败日志"""
    print(f"[❌ {func} 失败] {reason}", file=sys.stderr, flush=True)


def _log(msg: str, tag: str = "INFO") -> None:
    """标准日志"""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}][{tag}] {msg}", file=sys.stderr, flush=True)


def _load_blender_config() -> Dict[str, Any]:
    """
    从 skill.yaml 加载 Blender 配置
    
    Returns:
        dict: 包含 mcp_host, mcp_port 等配置
    """
    try:
        import yaml
        
        # 定位 skill.yaml 文件
        skill_yaml_path = Path(__file__).parent.parent / "skill.yaml"
        
        if not skill_yaml_path.exists():
            raise FileNotFoundError(f"找不到 skill.yaml 文件: {skill_yaml_path}")
        
        # 读取配置文件
        with open(skill_yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        settings = config.get('settings', {})
        
        return {
            'mcp_host': settings.get('mcp_host', {}).get('default', 'localhost'),
            'mcp_port': settings.get('mcp_port', {}).get('default', 9876),
            'connection_timeout': settings.get('connection_timeout', {}).get('default', 10),
        }
    except Exception as e:
        print(f"⚠️  警告: 读取 skill.yaml 失败: {e}，使用默认配置")
        return {
            'mcp_host': 'localhost',
            'mcp_port': 9876,
            'connection_timeout': 10,
        }


class BlenderMCPClient:
    """Blender MCP 客户端 - 使用 TCP + Line-delimited JSON 通信"""

    def __init__(self, host: str = "localhost", port: int = 9876):
        self.host = host
        self.port = port
        self.timeout = 30

    def is_running(self) -> bool:
        """检查 Blender MCP 服务是否正在运行"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _send_tcp_json(self, data: str, timeout: int = 30) -> str:
        """
        通过 TCP Socket 发送 JSON 数据并接收响应
        使用换行分隔的 JSON 协议（常见 Blender MCP 格式）
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((self.host, self.port))
        
        # 发送数据（换行分隔）
        sock.sendall((data.strip() + "\n").encode('utf-8'))
        
        # 接收响应
        response_buffer = b""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_buffer += chunk
                
                # 检查是否收到完整 JSON
                try:
                    decoded = response_buffer.decode('utf-8').strip()
                    # 尝试找最后一个完整的 JSON 行
                    lines = decoded.split('\n')
                    for line in reversed(lines):
                        line = line.strip()
                        if line:
                            json.loads(line)  # 验证是否有效 JSON
                            sock.close()
                            return line
                except json.JSONDecodeError:
                    continue
            except socket.timeout:
                break
        
        sock.close()
        return ""

    def execute_blender_code(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        执行 Blender Python 代码
        自动尝试多种消息格式直到成功
        """
        if not self.is_running():
            return {"status": "error", "error": "Blender MCP 服务未运行", "message": "Blender MCP 服务未运行"}
        
        # 多种消息格式尝试
        formats = [
            # 格式1: execute_code + params（可能服务按字段名映射参数）
            '{"type": "execute_code", "params": {"code": ' + json.dumps(code) + '}}',
            # 格式2: execute_code + code 顶级字段
            '{"type": "execute_code", "code": ' + json.dumps(code) + '}',
            # 格式3: execute_blender_code + params
            '{"type": "execute_blender_code", "params": {"code": ' + json.dumps(code) + '}}',
            # 格式4: execute_blender_code + code 顶级字段
            '{"type": "execute_blender_code", "code": ' + json.dumps(code) + '}',
            # 格式5: run_code
            '{"type": "run_code", "params": {"code": ' + json.dumps(code) + '}}',
            # 格式6: exec
            '{"type": "exec", "params": {"code": ' + json.dumps(code) + '}}',
            # 格式7: JSON-RPC 2.0 (MCP 标准)
            '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_blender_code","arguments":{"code":' + json.dumps(code) + '}},"id":1}',
            # 格式8: MCP 简化格式
            '{"method":"tools/call","params":{"name":"execute_blender_code","arguments":{"code":' + json.dumps(code) + '}},"id":1}',
        ]
        
        last_error = None
        
        for i, request_str in enumerate(formats):
            try:
                response_str = self._send_tcp_json(request_str, timeout=min(timeout, 10))
                
                if response_str:
                    response = json.loads(response_str)
                    
                    # 检查是否返回了 "Unknown command" 错误
                    if "error" in response:
                        error_info = response["error"]
                        if isinstance(error_info, dict):
                            error_msg = error_info.get("message", str(error_info))
                        else:
                            error_msg = str(error_info)
                        # 如果是 Unknown command，尝试下一种格式
                        if "Unknown" in str(error_msg) or "unknown" in str(error_msg).lower():
                            last_error = f"格式{i+1}: {error_msg}"
                            continue
                        last_error = error_msg
                        continue  # 继续尝试下一种格式
                    
                    # 成功！提取结果
                    # Blender MCP 返回格式: {"executed": true, "result": "..."}
                    if response.get("executed") == True or response.get("status") == "success":
                        result = (
                            response.get("result") or
                            response.get("output") or
                            response.get("data") or
                            response.get("message") or
                            ""
                        )
                        if isinstance(result, dict):
                            result = json.dumps(result, indent=2, ensure_ascii=False)
                        elif isinstance(result, list):
                            result = json.dumps(result, indent=2, ensure_ascii=False)
                        
                        return {
                            "status": "success",
                            "result": str(result) if result else response_str,
                            "message": f"代码执行成功（使用格式{i+1}）",
                            "format_used": i + 1,
                            "raw_response": response_str
                        }
                    else:
                        # 没有明确成功标志，但也没有错误，先返回
                        return {
                            "status": "success",
                            "result": response_str,
                            "message": f"代码已发送（使用格式{i+1}）",
                            "format_used": i + 1
                        }
                else:
                    last_error = f"格式{i+1}: 无响应"
                    
            except Exception as e:
                last_error = f"格式{i+1}: {str(e)}"
                continue
        
        # 所有格式都失败
        return {
            "status": "error",
            "error": last_error or "所有格式均失败",
            "message": last_error or "无法与 Blender MCP 通信"
        }

    def ensure_running(self) -> bool:
        """
        确保 Blender MCP 服务正在运行

        Returns:
            bool: 服务是否可用
        """
        if self.is_running():
            return True

        print(f"⚠️  Blender MCP 服务未运行在 {self.host}:{self.port}")
        print(f"   请确保 Blender 已启动并加载了 MCP 插件")
        print(f"   或者通过以下命令启动 MCP 服务:")
        print(f"   blender --background --python mcp_server.py")

        return False

    def get_scene_info(self) -> Dict[str, Any]:
        """
        获取当前场景信息

        Returns:
            dict: 场景信息（对象列表、材质等）
        """
        code = """
import bpy
import json

scene_info = {
    "objects": [],
    "materials": [],
    "cameras": [],
    "lights": []
}

# 获取对象信息
for obj in bpy.data.objects:
    scene_info["objects"].append({
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation": list(obj.rotation_euler),
        "scale": list(obj.scale)
    })

# 获取材质信息
for mat in bpy.data.materials:
    scene_info["materials"].append(mat.name)

# 获取相机
for cam in bpy.data.cameras:
    scene_info["cameras"].append(cam.name)

# 获取灯光
for light in bpy.data.lights:
    scene_info["lights"].append(light.name)

print(json.dumps(scene_info))
"""
        return self.execute_blender_code(code)

    def clear_scene(self) -> Dict[str, Any]:
        """
        清空当前场景

        Returns:
            dict: 执行结果
        """
        code = """
import bpy

# 删除所有对象
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

print("场景已清空")
"""
        return self.execute_blender_code(code)


def execute_blender_code(code: str, host: str = "localhost", port: int = 9876, timeout: int = 30) -> Dict[str, Any]:
    """
    执行 Blender Python 代码（便捷函数）

    Args:
        code: Blender Python 代码字符串
        host: MCP 服务器地址
        port: MCP 服务器端口
        timeout: 超时时间（秒）

    Returns:
        dict: 执行结果

    Examples:
        >>> from skills.skill_blender_controler.tools.blender_mcp_client_v2 import execute_blender_code
        >>>
        >>> code = '''
        ... import bpy
        ... # 创建立方体
        ... bpy.ops.mesh.primitive_cube_add()
        ... # 设置位置
        ... bpy.context.object.location = (0, 0, 0)
        ... '''
        >>> result = execute_blender_code(code)
        >>> if result['status'] == 'success':
        ...     print(result['message'])
        ... else:
        ...     print(f"错误: {result['error']}")
    """
    _log(f"▶ execute_blender_code(host={host}, port={port})", "CALL")

    client = BlenderMCPClient(host=host, port=port)

    # 确保服务运行
    if not client.ensure_running():
        _log_fail("execute_blender_code", "Blender MCP 服务未运行")
        return {
            "status": "error",
            "error": "Blender MCP 服务未运行",
            "message": "Blender MCP 服务未运行"
        }

    # 执行代码
    result = client.execute_blender_code(code, timeout=timeout)
    if result.get("status") == "success":
        _log_ok("execute_blender_code", result.get("message", ""))
    else:
        _log_fail("execute_blender_code", result.get("error", result.get("message", "未知错误")))
    return result


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Blender MCP 客户端测试（自动协议检测）")
    print("=" * 60)

    # 测试1: 检查服务状态
    print("\n1. 检查 Blender MCP 服务状态...")
    client = BlenderMCPClient()

    if not client.is_running():
        print("❌ Blender MCP 服务未运行")
        print("请确保:")
        print("  1. Blender 已启动")
        print("  2. MCP 插件已加载并运行在端口 9876")
        exit(1)

    print("✅ Blender MCP 服务正在运行")
    print(f"   连接方式: TCP (line-delimited JSON, {client.host}:{client.port})")

    # 测试2: 执行简单的 Blender 代码（创建立方体）
    print("\n2. 测试执行 Blender Python 代码（创建立方体）...")
    code = '''
import bpy

# 创建立方体
bpy.ops.mesh.primitive_cube_add(size=2)

# 重命名
bpy.context.active_object.name = "WebSocketTestCube"

# 检查是否创建成功
print(f"立方体创建成功: {bpy.context.active_object.name}")
'''

    result = execute_blender_code(code, timeout=15)

    if result['status'] == 'success':
        print(f"✅ {result.get('message', '执行成功')}")
        if result.get('result'):
            print(f"   输出: {result['result']}")
    else:
        print(f"❌ 执行失败: {result.get('error', result.get('message', '未知错误'))}")

    # 测试3: 获取场景信息（验证对象是否创建）
    print("\n3. 验证场景信息（检查对象是否创建）...")
    scene_info = client.get_scene_info()

    if scene_info['status'] == 'success':
        print(f"✅ {scene_info.get('message', '获取场景信息成功')}")
        result_str = scene_info.get('result', '')
        if result_str:
            print(f"   场景数据: {result_str[:500]}")
            # 检查是否包含我们创建的对象
            if 'WebSocketTestCube' in str(result_str):
                print("   ✅ 确认：立方体对象已创建！")
            else:
                print("   ⚠️  未找到创建的立方体对象")
    else:
        print(f"❌ 获取场景信息失败: {scene_info.get('error', scene_info.get('message', '未知错误'))}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
