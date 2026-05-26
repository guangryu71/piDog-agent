# Shell Controller - PowerShell 命令行工具集

## 概述

Shell Controller 是 Agent 内置的 PowerShell 命令行执行工具集，仅在 Windows 系统上运行。

**实现位置**: `utils/shell_controler/tools/`

---

## 可用工具，最重要！最终需要在这里面选择最合适的方法！

### execute_command
- **功能**: 执行 PowerShell 命令，支持超时控制和输出捕获
- **文件路径**: `utils/shell_controler/tools/command_executor.py`
- **参数**:
  - `command` (必填): 要执行的 PowerShell 命令
  - `timeout` (可选): 超时时间（秒），默认 30
  - `capture_output` (可选): 是否捕获输出，默认 true
- **示例**: `execute_command(command="Get-Process", timeout=10)`

### execute_script
- **功能**: 执行 PowerShell 脚本文件 (.ps1)，支持参数传递
- **文件路径**: `utils/shell_controler/tools/command_executor.py`
- **参数**:
  - `script_path` (必填): 脚本文件路径 (.ps1)
  - `args` (可选): 脚本参数列表
  - `timeout` (可选): 超时时间（秒），默认 60
- **示例**: `execute_script(script_path="./deploy.ps1", args=["--env", "production"])`

### validate_python_syntax
- **功能**: 验证单个 Python 文件的语法正确性（使用 py_compile）
- **文件路径**: `utils/shell_controler/tools/command_executor.py`
- **参数**:
  - `file_path` (必填): Python 文件路径（必须是 .py 文件）
- **返回**: 
  - `status`: "success" | "failed" | "error"
  - `message`: 验证结果消息
  - `error`: 错误信息（如果失败）
- **示例**: `validate_python_syntax(file_path="product_management_system/src/product.py")`

### validate_multiple_python_files
- **功能**: 批量验证多个 Python 文件的语法，返回整体统计结果
- **文件路径**: `utils/shell_controler/tools/command_executor.py`
- **参数**:
  - `file_paths` (必填): Python 文件路径列表
- **返回**:
  - `status`: "success" | "partial_success" | "failed"
  - `total`: 总文件数
  - `passed`: 通过数量
  - `failed`: 失败数量
  - `results`: 每个文件的详细验证结果
- **示例**: 
```python
validate_multiple_python_files(file_paths=[
    "product_management_system/src/product.py",
    "product_management_system/src/manager.py",
    "product_management_system/src/main.py"
])
```

---

## 📋 使用规范与最佳实践

### 1. 删除/清理操作的协作规范

**当涉及删除、清理、移除、销毁等操作时，必须与 files_controler 配合使用：**

#### 工作流程
1. **files_controler**: 先使用 `list_directory` 识别需要删除的文件
2. **shell_controler**: 再使用 `execute_command` 执行 PowerShell 删除命令


### 2. 开发类任务的执行规范

**当用户要求"构建/创建/开发 XXX 系统/应用/项目"时，必须实际执行操作，而不是仅提供建议。**

#### 错误做法
❌ 仅回复："建议您使用以下命令创建虚拟环境：python -m venv venv"  
✅ 应该直接执行命令

---

### 3. 状态依赖型任务处理规范

**当任务需要先获取信息/状态，再基于该信息执行操作时，必须分两轮生成工作流。**

#### 判断标准
问自己："我是否知道执行命令所需的**关键信息**（如进程名称、服务状态等）？"
- 如果不知道 → 必须先调用信息查询命令
- 如果已知 → 可直接执行操作命令

---

### 4. 诊断优先原则

**当遇到执行错误时，绝对不要立即尝试修正！必须遵循以下步骤：**

#### 第 1 步：分析错误类型

| 错误类型 | 可能原因 | 诊断方向 |
|---------|---------|---------|
| `ModuleNotFoundError` | 导入路径错误或文件不存在 | 查看项目目录结构，确认文件实际位置 |
| `FileNotFoundError` | 文件路径错误或父目录不存在 | 检查目录层级关系 |
| `UnicodeEncodeError` | Windows GBK 编码无法处理 Unicode 字符 | 使用 ASCII 字符替代或设置 UTF-8 环境 |
| `SyntaxError` | Python 代码语法错误 | 读取代码文件，定位具体行号 |
| `ImportError` | 模块依赖缺失或循环导入 | 检查 `__init__.py` 文件和导入链 |

#### 第 2 步：收集诊断信息

**根据错误类型选择诊断工具：**
- **文件/模块找不到** → 使用 `list_directory` 查看目录结构
- **代码逻辑错误** → 使用 `read_file` 读取代码内容
- **命令执行失败** → 分析 stderr 输出，识别错误类型

#### 第 3 步：基于诊断结果制定修正方案

**只有完成诊断后，才能生成修正工作流！**

### 5. 死循环检测与避免

**如果连续两轮执行了相同的工具且参数相同，说明陷入死循环。**

#### ❌ 死循环示例（绝对禁止）
```
第 3 轮：运行测试 → ModuleNotFoundError: No module named 'src'
第 4 轮：list_directory("project") → 显示 src/ 和 tests/ 目录
第 5 轮：list_directory("project") → 再次显示 src/ 和 tests/ 目录  ❌ 错误！重复操作
第 6 轮：list_directory("project") → 还是显示 src/ 和 tests/ 目录  ❌ 错误！死循环
```

#### ✅ 正确的渐进式诊断流程
```
第 3 轮：运行测试 → ModuleNotFoundError: No module named 'src'
第 4 轮：list_directory("project") → 显示 src/ 和 tests/ 目录
         ↓ 分析：src 目录存在，但不知道里面有什么文件
第 5 轮：list_directory("project/src") → 显示 main.py, product.py 等  ✅ 深入一层
         ↓ 分析：文件确实存在，问题是测试代码的导入路径错误
第 6 轮：write_file 修正测试代码的 sys.path → sys.path.insert(0, '..')  ✅ 基于诊断结果修正
第 7 轮：重新运行测试 → 成功 ✅
```

**关键点**：
1. 第 4 轮看到 `src/` 目录存在
2. 第 5 轮**不是重复**查看父目录，而是**深入一层**查看 `src/` 子目录
3. 第 6 轮基于完整信息修正导入路径
4. 每一步都基于上一步的结果制定新策略

---

### 6. 常用 PowerShell 命令参考

#### 文件操作
- **复制**: `Copy-Item -Path '源路径' -Destination '目标路径' -Force`
- **移动**: `Move-Item -Path '源路径' -Destination '目标路径' -Force`
- **删除**: `Remove-Item -Path '文件路径' -Recurse -Force`
- **重命名**: `Rename-Item -Path '旧名称' -NewName '新名称'`
- **创建目录**: `New-Item -ItemType Directory -Path '目录路径' -Force`
- **列出文件**: `Get-ChildItem -Path '目录路径' | Select-Object Name, Length, LastWriteTime`

#### 系统查询
- **进程列表**: `Get-Process | Select-Object Name, Id, CPU -First 20`
- **磁盘信息**: `Get-Volume | Select-Object DriveLetter, Size, FreeSpace`
- **网络信息**: `Get-NetIPAddress | Select-Object IPAddress, InterfaceAlias`
- **服务列表**: `Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name, DisplayName`

#### Git 操作
- **提交**: `cd 仓库路径; git add .; git commit -m '提交信息'`
- **推送**: `git push origin 分支名`
- **拉取**: `git pull origin 分支名`
- **状态**: `git status`
