# 浏览器自动化助手 (v4.0)

基于原生 Playwright 的浏览器自动化控制，直接操控本地 Chrome/Chromium/Edge 浏览器。

## 核心能力
- **网页访问**: 打开/导航任意 URL
- **智能交互**: 点击、输入、按键等页面操作
- **内容提取**: 快照（ARIA 树 + ref）、截图
- **JS 执行**: 在页面上下文中执行任意 JavaScript
- **监控**: 控制台日志、网络请求抓取
- **输出**: 截图 (PNG/JPEG)、PDF 导出

## 使用流程
1. `start` → 启动浏览器（headed=true 显示窗口）
2. `open(url)` → 打开网页
3. `snapshot` → 获取页面交互元素（带 ref）
4. `click(ref=...)` / `type(text=...)` → 操作页面
5. `screenshot` → 截图保存
6. `stop` → 关闭浏览器

## 技术实现
- 引擎: Playwright (sync API via ThreadPoolExecutor)
- 浏览器: Chrome / Chromium / Edge (自动检测)
- 默认模式: headless（后台运行）
