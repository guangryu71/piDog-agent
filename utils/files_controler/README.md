# Files Controller - 文件操作工具集

## 概述

Files Controller 是 Agent 内置的文件操作工具集，提供完整的文件内容管理能力。

**实现位置**: `utils/files_controler/tools/`

**重要提示**: 对于新文件创建、目录生成、项目结构查看、目录浏览、系统信息获取等场景，优先使用 `shell_controler` 的 `execute_command` 工具，通过命令行方式实现（如 `Get-ChildItem`, `ls`, `dir` 等命令）。

---

## 可用工具,最重要！需要从这里面选择最合适的方法

### locate_file
- **功能**: 定位文件地址
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `filename` (必填): 文件名或通配符模式（如`*.py`）
  - `search_path` (可选): 搜索路径，默认当前目录
  - `recursive` (可选): 是否递归搜索，默认True
- **返回值**: 包含匹配文件列表、数量、搜索路径等信息的字典
- **示例**: `locate_file("*.py", recursive=True)`

### read_file_full
- **功能**: 读取文件的完整内容
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `encoding` (可选): 文件编码，默认从配置读取
- **返回值**: 包含文件内容、行数、大小、编码等信息的字典
- **示例**: `read_file_full("example.py")`

### read_file_lines
- **功能**: 读取文件的指定行内容
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `start_line` (可选): 起始行号（从1开始），None表示从头开始
  - `end_line` (可选): 结束行号，None表示到末尾
  - `encoding` (可选): 文件编码，默认从配置读取
- **返回值**: 包含指定行内容、行号范围、实际读取行数等信息的字典
- **示例**: `read_file_lines("example.py", start_line=1, end_line=10)`

### get_file_structure
- **功能**: 获取文件的结构信息，包括类、方法、属性、文档字符串等详细信息
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `encoding` (可选): 文件编码，默认从配置读取
- **返回值**: 包含类、方法、属性、模块级变量、导入语句、文档字符串、行号、装饰器等完整信息的字典
- **示例**: `get_file_structure("example.py")`

### find_method
- **功能**: 查找指定的一个或多个方法
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `method_names` (必填): 要查找的方法名列表
  - `class_names` (可选): 要查找的类名列表，与method_names一一对应
- **返回值**: 包含找到的方法信息列表、未找到的方法列表等信息的字典
- **示例**: `find_method("example.py", ["method1", "method2"], ["Class1", "Class2"])`

### get_file_info
- **功能**: 获取文件的基本信息
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `file_path` (必填): 文件路径
- **返回值**: 包含文件名、路径、大小、创建和修改时间等信息的字典
- **示例**: `get_file_info("example.py")`

### list_directory
- **功能**: 列出目录内容，支持递归获取指定深度的项目结构
- **文件路径**: `utils/files_controler/tools/file_reader.py`
- **参数**: 
  - `dir_path` (可选): 目录路径，默认当前目录 "."
  - `max_depth` (可选): 最大递归深度，默认 3
  - `current_depth` (可选): 当前递归深度（内部使用）
- **返回值**: 包含目录项列表、文件数量、目录数量、树形结构等信息的字典
- **示例**: `list_directory(".", max_depth=2)`

### write_file
- **功能**: 写入文件内容
- **文件路径**: `utils/files_controler/tools/file_writer.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `content` (必填): 要写入的内容
  - `mode` (可选): 写入模式，"overwrite"-覆盖 / "append"-追加，默认"overwrite"
  - `encoding` (可选): 文件编码，默认从配置读取
- **返回值**: 包含文件路径、写入模式、写入字节数等信息的字典
- **示例**: `write_file("example.txt", "Hello World", mode="overwrite")`

### replace_content
- **功能**: 替换文件中的指定内容
- **文件路径**: `utils/files_controler/tools/file_writer.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `old_content` (必填): 要替换的旧内容
  - `new_content` (必填): 新的内容
  - `encoding` (可选): 文件编码，默认从配置读取
- **返回值**: 包含文件路径、替换次数等信息的字典
- **示例**: `replace_content("example.txt", "old_text", "new_text")`

### replace_lines
- **功能**: 替换文件中的指定行
- **文件路径**: `utils/files_controler/tools/file_writer.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `line_number` (必填): 要替换的行号（从1开始）
  - `new_content` (必填): 新的行内容
  - `encoding` (可选): 文件编码，默认从配置读取
- **返回值**: 包含文件路径、被替换的行号等信息的字典
- **示例**: `replace_lines("example.txt", 1, "New first line")`

### delete_lines
- **功能**: 删除文件中的指定行范围
- **文件路径**: `utils/files_controler/tools/file_writer.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `ifAll` (可选): 是否删除所有行（清空文件内容），默认 False
  - `start_line` (可选): 起始行号（从1开始），默认第1行（仅在 ifAll=False 时有效）
  - `end_line` (可选): 结束行号（从1开始），None表示到文件末尾（仅在 ifAll=False 时有效）
  - `encoding` (可选): 文件编码，默认 "utf-8"
- **返回值**: 包含操作结果消息、删除行数、剩余行数等信息的字典
- **示例**: 
  - `delete_lines("example.txt", ifAll=True)` - 清空整个文件
  - `delete_lines("example.txt", ifAll=False, start_line=1, end_line=5)` - 删除前5行

### clear_file
- **功能**: 清空文件内容（将文件内容设置为空）
- **文件路径**: `utils/files_controler/tools/file_writer.py`
- **参数**: 
  - `file_path` (必填): 文件路径
  - `encoding` (可选): 文件编码，默认 "utf-8"
- **返回值**: 包含操作结果消息、原始文件大小等信息的字典
- **示例**: `clear_file("example.txt")`

---

## 📋 使用规范与最佳实践

### 1. 项目结构查看优先使用命令行

**重要原则**: 对于项目结构查看、目录浏览、文件系统信息获取等场景，优先使用 `shell_controler` 的 `execute_command` 工具，通过命令行方式实现。

#### 为什么使用命令行工具优先？

1. **性能更好**: 命令行工具（如 `Get-ChildItem`）专为目录操作优化
2. **功能更丰富**: 提供更多格式化选项和过滤能力
3. **结果更直观**: 树形结构、详细信息等
4. **系统集成更好**: 与操作系统原生功能集成

#### 2.命令行 vs 文件工具的使用场景

| 场景 | 优先使用 | 说明 |
|------|----------|------|
| 查看目录结构 | `shell_controler.execute_command` | 使用 `Get-ChildItem -Path student_management_system -Recurse -Depth 3`
| 读取文件内容 | `files_controler.read_file_full` | 读取文件内容 |
| 写入文件内容 | `files_controler.write_file` | 写入文件内容 |
| 搜索文件 | `shell_controler.execute_command` | 使用 `Get-ChildItem -Recurse -Filter "*.py"` |
| 修改文件内容 | `files_controler.replace_content` | 修改文件内容 |

---

### 3. 删除/清理操作的协作规范

**当涉及删除、清理、移除、销毁等操作时，必须与 shell_controler 配合使用：**

#### 工作流程
1. **files_controler**: 先使用 `read_file_full` 或其他工具确认文件内容
2. **shell_controler**: 再使用 `execute_command` 执行 PowerShell 删除命令

### 4. 开发类任务的执行规范

**当用户要求"构建/创建/开发 XXX 系统/应用/项目"时，必须实际执行操作，而不是仅提供建议。**

### 4. 状态依赖型任务处理规范

**当任务需要先获取信息/状态，再基于该信息执行操作时，必须分两轮生成工作。**

#### 5. 判断标准
问自己："我是否知道执行操作所需的**关键信息**（如文件路径、文件内容等）？"
- 如果不知道 → 必须先调用信息获取工具（如 `read_file_full`, `locate_file`）
- 如果已知 → 可直接执行操作
## 注意事项

- 大文件读取时注意内存占用
- 写入操作会覆盖原文件，建议先备份
- 替换操作区分大小写
- 路径使用正斜杠或双反斜杠
- 特殊字符需要转义处理