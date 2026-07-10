# -*- coding: utf-8 -*-
"""
SmartAgent V2 — 原生 Playwright 浏览器引擎（异步兼容版）
========================================================
在独立后台线程中运行 async Playwright，避免与 FastAPI asyncio 冲突。

架构：
  browser_use() (sync entry, thread-safe)
        ↓
  _BROWSER_THREAD (dedicated thread + event loop)
        ↓
  async Playwright → Chrome / Edge

核心接口：
  browser_use(action, **kwargs) → str (JSON)
"""
import asyncio
import atexit
import json
import logging
import os
import socket
import threading
import time
from concurrent import futures
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

from .browser_snapshot import build_role_snapshot_from_aria

_log = logging.getLogger("browser_engine")

# ── 工作区路径（由 PiDog 设置，用于文件输出目录）────────────
_WORKSPACE_DIR: str = ""

def set_workspace_dir(path: str):
    """由 PiDog 在启动时调用，设置浏览器文件输出的根目录。"""
    global _WORKSPACE_DIR
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = Path.cwd() / p
        p.mkdir(parents=True, exist_ok=True)
        _WORKSPACE_DIR = str(p.resolve())
        _log.info("Browser workspace set to: %s", _WORKSPACE_DIR)

def _get_output_dir() -> Path:
    if _WORKSPACE_DIR:
        return Path(_WORKSPACE_DIR)
    d = Path.cwd() / "browser_output"
    d.mkdir(parents=True, exist_ok=True)
    return d

# ── 从 confing.json 加载浏览器配置 ───────────────────────────
def _load_browser_config() -> dict:
    candidates = []
    try:
        candidates.append(Path(__file__).parent.parent.parent / "confing.json")
    except Exception:
        pass
    try:
        candidates.append(Path.cwd() / "confing.json")
    except Exception:
        pass
    for config_path in candidates:
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = data.get("browser", {})
                if cfg:
                    _log.info("Browser config loaded from %s: %s", config_path, cfg)
                    return cfg
        except Exception as e:
            _log.warning("Failed to load config from %s: %s", config_path, e)
    _log.warning("No browser config found")
    return {}

_BROWSER_CONFIG = _load_browser_config()
_CONFIG_EXECUTABLE = _BROWSER_CONFIG.get("executable_path", "")
_EDGE_CANDIDATES = [
    _CONFIG_EXECUTABLE,
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# ── 工具函数 ────────────────────────────────────────────────
def _ok(**kwargs) -> str:
    return json.dumps({"ok": True, **kwargs}, ensure_ascii=False, indent=2)

def _err(error: str) -> str:
    return json.dumps({"ok": False, "error": error}, ensure_ascii=False, indent=2)

def _resolve_path(path: str) -> str:
    if not path:
        return ""
    if Path(path).is_absolute():
        return path
    return str((_get_output_dir() / path).resolve())

def _find_edge_exe() -> Optional[str]:
    for candidate in _EDGE_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None

# ── 浏览器状态（仅线程内访问）───────────────────────────────
class _BrowserState:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.pages: Dict[str, Any] = {}
        self.current_page_id: Optional[str] = None
        self.refs: Dict[str, Dict] = {}
        self.headless = True
        self.headed_requested = False
        self.browser_args = ""
        self.executable_path = ""
        self.console_logs: Dict[str, list] = {}
        self.network_logs: Dict[str, list] = {}
        self._browser_name = ""
        self._last_error = ""

_STATE = _BrowserState()

# ── 后台线程 ─────────────────────────────────────────────────
_BROWSER_LOOP: Optional[asyncio.AbstractEventLoop] = None
_BROWSER_THREAD: Optional[threading.Thread] = None
_SHUTDOWN = threading.Event()

def _get_page(page_id: str):
    if page_id == "default" and _STATE.current_page_id:
        page_id = _STATE.current_page_id
    return _STATE.pages.get(page_id)

def _get_refs(page_id: str) -> dict:
    if page_id == "default" and _STATE.current_page_id:
        page_id = _STATE.current_page_id
    return _STATE.refs.get(page_id, {})

def _get_selector_from_ref(ref: str, page_id: str) -> Optional[str]:
    refs = _get_refs(page_id)
    info = refs.get(ref)
    if not info:
        return None
    role = info["role"]
    name = info.get("name", "")
    nth = info.get("nth", 0)
    sel = f'[role="{role}"]'
    if name:
        sel += f'[name="{name}"]'
    if nth > 0:
        sel = f"{sel}:nth-of-type({nth + 1})"
    return sel

# ── 页面监听（async）─────────────────────────────────────────
def _attach_page_listeners(page, page_id: str):
    _STATE.console_logs[page_id] = []
    _STATE.network_logs[page_id] = []
    async def on_console(msg):
        _STATE.console_logs[page_id].append(f"[{msg.type}] {msg.text}")
    async def on_request(request):
        _STATE.network_logs[page_id].append(f"[REQ] {request.method} {request.url}")
    async def on_response(response):
        _STATE.network_logs[page_id].append(f"[RES] {response.status} {response.url}")
    page.on("console", on_console)
    page.on("request", on_request)
    page.on("response", on_response)

# ── 核心操作（全部 async，只在浏览器线程内调用）─────────────
async def _async_start_browser() -> bool:
    if _STATE.browser is not None and _STATE.browser.is_connected():
        return True
    _STATE._last_error = ""
    try:
        pw = await async_playwright().start()
        _STATE.playwright = pw
        launch_kwargs = {"headless": _STATE.headless}
        exe = _STATE.executable_path
        if exe and Path(exe).is_file():
            launch_kwargs["executable_path"] = exe
        args = _STATE.browser_args
        if args:
            launch_kwargs["args"] = args.split()
        browser = None
        browser_name = ""
        last_error = ""
        # 1. 有指定 exe 直接用
        if "executable_path" in launch_kwargs:
            ep = launch_kwargs["executable_path"].lower()
            try:
                kw = {k: v for k, v in launch_kwargs.items() if k != "executable_path"}
                if "edge" in ep:
                    browser = await pw.chromium.launch(channel="msedge", **kw)
                    browser_name = f"Edge ({launch_kwargs['executable_path']})"
                elif "chrome" in ep:
                    browser = await pw.chromium.launch(channel="chrome", **kw)
                    browser_name = f"Chrome ({launch_kwargs['executable_path']})"
                else:
                    browser = await pw.chromium.launch(**launch_kwargs)
                    browser_name = "Custom browser"
            except Exception as e:
                last_error = str(e)
        else:
            # 2. 自动检测 Edge → Chrome → Chromium
            try:
                browser = await pw.chromium.launch(channel="msedge", **launch_kwargs)
                browser_name = "Edge (channel)"
            except Exception as e:
                last_error = f"Edge(channel): {e}"
            if browser is None:
                edge_exe = _find_edge_exe()
                if edge_exe:
                    kw = {k: v for k, v in launch_kwargs.items() if k != "executable_path"}
                    try:
                        browser = await pw.chromium.launch(executable_path=edge_exe, **kw)
                        browser_name = f"Edge ({edge_exe})"
                    except Exception as e:
                        last_error += f" | Edge(exe): {e}"
            if browser is None:
                try:
                    browser = await pw.chromium.launch(channel="chrome", **launch_kwargs)
                    browser_name = "Chrome"
                except Exception as e:
                    last_error += f" | Chrome: {e}"
            if browser is None:
                try:
                    browser = await pw.chromium.launch(**launch_kwargs)
                    browser_name = "Chromium"
                except Exception as e:
                    last_error += f" | Chromium: {e}"
        if browser is None:
            await pw.stop()
            _STATE.playwright = None
            _STATE._last_error = last_error or "No browser found"
            _log.error("Browser launch failed: %s", last_error)
            return False
        context = await browser.new_context(viewport={"width": 1280, "height": 720}, accept_downloads=True)
        _STATE.browser = browser
        _STATE.context = context
        _STATE._browser_name = browser_name
        _STATE._last_error = ""
        page = await context.new_page()
        _attach_page_listeners(page, "default")
        _STATE.pages["default"] = page
        _STATE.current_page_id = "default"
        return True
    except Exception as e:
        _STATE._last_error = str(e)
        _log.error("Browser launch exception: %s", e)
        return False

async def _async_stop_browser():
    for pid in list(_STATE.pages.keys()):
        try:
            await _STATE.pages[pid].close()
        except Exception:
            pass
    _STATE.pages.clear()
    _STATE.refs.clear()
    _STATE.console_logs.clear()
    _STATE.network_logs.clear()
    _STATE.current_page_id = None
    try:
        if _STATE.context:
            await _STATE.context.close()
    except Exception:
        pass
    _STATE.context = None
    try:
        if _STATE.browser:
            await _STATE.browser.close()
    except Exception:
        pass
    _STATE.browser = None
    try:
        if _STATE.playwright:
            await _STATE.playwright.stop()
    except Exception:
        pass
    _STATE.playwright = None

async def _async_open(url: str, page_id: str) -> str:
    if not _STATE.browser or not _STATE.browser.is_connected():
        ok = await _async_start_browser()
        if not ok:
            return _err(f"Browser not running. Use action='start' first. ({_STATE._last_error})")
    url = url.strip()
    if not url.startswith(("http://", "https://", "about:")):
        url = "https://" + url
    if page_id == "default":
        page = _STATE.pages.get("default")
        if page:
            try:
                await page.goto(url, timeout=30000)
                _STATE.current_page_id = "default"
                return _ok(message="Opened URL", url=page.url, title=await page.title())
            except Exception as e:
                return _err(f"Failed to open URL: {e}")
        return _err("Default page missing")
    try:
        page = await _STATE.context.new_page()
        _attach_page_listeners(page, page_id)
        await page.goto(url, timeout=30000)
        _STATE.pages[page_id] = page
        _STATE.current_page_id = page_id
        return _ok(message="Opened URL in new tab", page_id=page_id, url=page.url, title=await page.title())
    except Exception as e:
        return _err(f"Failed to open URL: {e}")

async def _async_navigate(url: str, page_id: str) -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found. Open a page first.")
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        await page.goto(url, timeout=30000)
        return _ok(message="Navigated", url=page.url, title=await page.title())
    except Exception as e:
        return _err(f"Navigate failed: {e}")

async def _async_navigate_back(page_id: str) -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        await page.go_back()
        return _ok(message="Navigated back", url=page.url)
    except Exception as e:
        return _err(f"Navigate back failed: {e}")

async def _async_snapshot(page_id: str, filename: str = "") -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        raw = await page.locator(":root").aria_snapshot()
        raw_str = str(raw) if raw else ""
        snapshot, refs = build_role_snapshot_from_aria(raw_str, interactive=False, compact=False)
        pid = page_id if page_id != "default" else (_STATE.current_page_id or "default")
        _STATE.refs[pid] = refs
        out = {"ok": True, "snapshot": snapshot, "refs": list(refs.keys()), "url": page.url}
        if filename:
            resolved = _resolve_path(filename)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(snapshot)
            out["filename"] = resolved
        return json.dumps(out, ensure_ascii=False, indent=2)
    except Exception as e:
        return _err(f"Snapshot failed: {e}")

async def _async_click(page_id: str, selector: str = "", ref: str = "", wait: int = 0,
                       double_click: bool = False, button: str = "left") -> str:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _err("selector or ref required for click")
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        if wait:
            await asyncio.sleep(wait / 1000.0)
        btn = button if button in ("left", "right", "middle") else "left"
        if ref:
            css = _get_selector_from_ref(ref, page_id)
            if not css:
                return _err(f"Unknown ref: {ref}")
            locator = page.locator(css).first
        else:
            locator = page.locator(selector).first
        if double_click:
            await locator.dblclick(button=btn)
        else:
            await locator.click(button=btn)
        return _ok(message=f"Clicked: {ref or selector}")
    except Exception as e:
        return _err(f"Click failed: {e}. Use action='snapshot' to get page element refs.")

async def _async_type(page_id: str, text: str, selector: str = "", ref: str = "",
                      submit: bool = False, slowly: bool = False) -> str:
    text = text or ""
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _err("selector or ref required for type. Use action='snapshot' first to get page refs.")
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        if ref:
            css = _get_selector_from_ref(ref, page_id)
            if not css:
                return _err(f"Unknown ref: {ref}")
            locator = page.locator(css).first
        else:
            locator = page.locator(selector).first
        await locator.fill("")
        if slowly:
            await locator.type(text, delay=50)
        else:
            await locator.fill(text)
        if submit:
            await locator.press("Enter")
        return _ok(message=f"Typed into: {ref or selector}")
    except Exception as e:
        # Fallback：CSS选择器失败时，尝试通用角色定位
        if not ref and selector:
            tips = []
            try:
                search = page.get_by_role("searchbox").first
                if await search.count() > 0:
                    await search.fill("")
                    await search.fill(text)
                    if submit:
                        await search.press("Enter")
                    return _ok(message="Typed (searchbox fallback)", via="searchbox")
                tips.append("searchbox")
            except Exception:
                tips.append("searchbox")
            try:
                txt = page.get_by_role("textbox").first
                if await txt.count() > 0:
                    await txt.fill("")
                    await txt.fill(text)
                    if submit:
                        await txt.press("Enter")
                    return _ok(message="Typed (textbox fallback)", via="textbox")
                tips.append("textbox")
            except Exception:
                tips.append("textbox")
            hint = ""
            if tips:
                hint = f" Fallback attempts: {', '.join(tips)} also failed."
            return _err(f"Type failed: selector '{selector}' not found.{hint} "
                        f"Use action='snapshot' to inspect page elements and target them by ref.")
        return _err(f"Type failed: {e}. Use action='snapshot' to get page element refs.")

async def _async_screenshot(page_id: str, path: str = "", full_page: bool = False,
                            screenshot_type: str = "png", ref: str = "") -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    if not path:
        ext = "jpeg" if screenshot_type == "jpeg" else "png"
        path = f"screenshot-{int(time.time())}.{ext}"
    path = _resolve_path(path)
    try:
        stype = "jpeg" if screenshot_type == "jpeg" else "png"
        if ref:
            css = _get_selector_from_ref(ref, page_id)
            if not css:
                return _err(f"Unknown ref: {ref}")
            locator = page.locator(css).first
            await locator.screenshot(path=path, type=stype)
        else:
            await page.screenshot(path=path, full_page=full_page, type=stype)
        # 返回工作区相对路径（供前端/LLM引用）
        result_path = path
        if _WORKSPACE_DIR and path.startswith(_WORKSPACE_DIR):
            rel = path[len(_WORKSPACE_DIR):].lstrip("\\/")
            result_path = rel if rel else path
        return _ok(message="Screenshot saved", path=result_path)
    except Exception as e:
        return _err(f"Screenshot failed: {e}")

async def _async_eval(page_id: str, code: str) -> str:
    code = (code or "").strip()
    if not code:
        return _err("code required for eval")
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        if code.startswith("(") or code.startswith("function"):
            result = await page.evaluate(code)
        else:
            result = await page.evaluate(f"() => {{ return ({code}); }}")
        return _ok(result=result)
    except Exception as e:
        return _err(f"Eval failed: {e}")

async def _async_close(page_id: str) -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        await page.close()
        actual_id = page_id if page_id != "default" else _STATE.current_page_id
        if actual_id in _STATE.pages:
            del _STATE.pages[actual_id]
        if actual_id in _STATE.refs:
            del _STATE.refs[actual_id]
        if _STATE.current_page_id == actual_id:
            remaining = list(_STATE.pages.keys())
            _STATE.current_page_id = remaining[0] if remaining else None
        return _ok(message=f"Closed page '{page_id}'")
    except Exception as e:
        return _err(f"Close failed: {e}")

async def _async_tabs(tab_action: str, index: int = 0) -> str:
    if tab_action == "list":
        tabs = []
        for pid, page in _STATE.pages.items():
            try:
                tabs.append({"page_id": pid, "url": page.url, "title": await page.title(),
                             "current": pid == _STATE.current_page_id})
            except Exception:
                tabs.append({"page_id": pid, "url": "unknown", "title": "unknown", "current": False})
        return _ok(tabs=tabs)
    elif tab_action == "new":
        try:
            page = await _STATE.context.new_page()
            pid = f"tab-{len(_STATE.pages)}"
            _attach_page_listeners(page, pid)
            _STATE.pages[pid] = page
            _STATE.current_page_id = pid
            return _ok(message="New tab created", page_id=pid)
        except Exception as e:
            return _err(f"New tab failed: {e}")
    elif tab_action == "close":
        pids = list(_STATE.pages.keys())
        if 0 <= index < len(pids):
            return await _async_close(pids[index])
        return _err(f"Invalid tab index: {index}")
    elif tab_action == "select":
        pids = list(_STATE.pages.keys())
        if 0 <= index < len(pids):
            _STATE.current_page_id = pids[index]
            return _ok(message=f"Switched to tab {index}", page_id=pids[index])
        return _err(f"Invalid tab index: {index}")
    return _err(f"Unknown tab action: {tab_action}")

async def _async_press_key(page_id: str, key: str) -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        await page.keyboard.press(key)
        return _ok(message=f"Pressed key: {key}")
    except Exception as e:
        return _err(f"Key press failed: {e}")

async def _async_wait_for(page_id: str, wait_time: float = 0, text_gone: str = "") -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    try:
        if text_gone:
            await page.wait_for_selector(f"text={text_gone}", state="detached", timeout=30000)
            return _ok(message=f"Text '{text_gone}' disappeared")
        if wait_time:
            await asyncio.sleep(wait_time)
            return _ok(message=f"Waited {wait_time}s")
        return _err("Specify wait_time or text_gone")
    except Exception as e:
        return _err(f"Wait failed: {e}")

async def _async_pdf(page_id: str, path: str = "") -> str:
    page = _get_page(page_id)
    if not page:
        return _err(f"Page '{page_id}' not found.")
    if not path:
        path = f"page-{int(time.time())}.pdf"
    path = _resolve_path(path)
    try:
        await page.pdf(path=path)
        return _ok(message="PDF saved", path=path)
    except Exception as e:
        return _err(f"PDF failed: {e}")

async def _async_console_messages(page_id: str, level: str = "info") -> str:
    pid = page_id if page_id != "default" else (_STATE.current_page_id or "default")
    logs = _STATE.console_logs.get(pid, [])
    if level and level != "info":
        logs = [l for l in logs if f"[{level}]" in l]
    return _ok(messages=logs[-50:], count=len(logs))

async def _async_network_requests(page_id: str, include_static: bool = False) -> str:
    pid = page_id if page_id != "default" else (_STATE.current_page_id or "default")
    logs = _STATE.network_logs.get(pid, [])
    return _ok(requests=logs[-50:], count=len(logs))

# ── Action 路由（async）──────────────────────────────────────
_ACTION_MAP = {
    "start": "start", "stop": "stop", "open": "open", "navigate": "navigate",
    "navigate_back": "navigate_back", "snapshot": "snapshot", "click": "click",
    "type": "type", "screenshot": "screenshot", "eval": "eval", "evaluate": "eval",
    "close": "close", "tabs": "tabs", "press_key": "press_key", "wait_for": "wait_for",
    "pdf": "pdf", "console_messages": "console_messages", "network_requests": "network_requests",
}

async def _dispatch_async(action: str, **kwargs) -> str:
    """在浏览器线程内分发并执行操作"""
    act = (action or "").strip().lower()
    if act not in _ACTION_MAP:
        return _err(f"Unknown action: {act}. Supported: {', '.join(_ACTION_MAP.keys())}")
    # viewport
    w, h = kwargs.get("width", 0), kwargs.get("height", 0)
    if w and h:
        page = _get_page(kwargs.get("page_id", "default"))
        if page:
            try:
                await page.set_viewport_size({"width": w, "height": h})
            except Exception:
                pass
    try:
        if act == "start":
            headed = kwargs.get("headed", False)
            _STATE.headless = not headed
            _STATE.headed_requested = headed
            _STATE.browser_args = kwargs.get("browser_args", "")
            _STATE.executable_path = kwargs.get("executable_path", "")
            ok = await _async_start_browser()
            if ok:
                mode = "headed (visible)" if headed else "headless"
                return _ok(message=f"Browser started ({mode}, {_STATE._browser_name})",
                           headed=headed, headless=not headed, browser=_STATE._browser_name)
            return _err(f"Failed to start browser: {_STATE._last_error}. Ensure Edge/Chrome is installed.")
        elif act == "stop":
            await _async_stop_browser()
            return _ok(message="Browser stopped")
        elif act == "open":
            return await _async_open(kwargs.get("url", ""), kwargs.get("page_id", "default"))
        elif act == "navigate":
            return await _async_navigate(kwargs.get("url", ""), kwargs.get("page_id", "default"))
        elif act == "navigate_back":
            return await _async_navigate_back(kwargs.get("page_id", "default"))
        elif act == "snapshot":
            return await _async_snapshot(kwargs.get("page_id", "default"),
                                         kwargs.get("snapshot_filename", "") or kwargs.get("filename", ""))
        elif act == "click":
            return await _async_click(kwargs.get("page_id", "default"),
                                      kwargs.get("selector", "") or kwargs.get("start_selector", ""),
                                      kwargs.get("ref", "") or kwargs.get("start_ref", ""),
                                      kwargs.get("wait", 0),
                                      kwargs.get("double_click", False),
                                      kwargs.get("button", "left"))
        elif act == "type":
            return await _async_type(kwargs.get("page_id", "default"), kwargs.get("text", ""),
                                     kwargs.get("selector", ""), kwargs.get("ref", ""),
                                     kwargs.get("submit", False), kwargs.get("slowly", False))
        elif act == "screenshot":
            return await _async_screenshot(kwargs.get("page_id", "default"),
                                           kwargs.get("path", "") or kwargs.get("filename", ""),
                                           kwargs.get("full_page", False),
                                           kwargs.get("screenshot_type", "png"),
                                           kwargs.get("ref", ""))
        elif act in ("eval", "evaluate"):
            return await _async_eval(kwargs.get("page_id", "default"), kwargs.get("code", ""))
        elif act == "close":
            return await _async_close(kwargs.get("page_id", "default"))
        elif act == "tabs":
            return await _async_tabs(kwargs.get("tab_action", ""), kwargs.get("index", -1))
        elif act == "press_key":
            return await _async_press_key(kwargs.get("page_id", "default"), kwargs.get("key", ""))
        elif act == "wait_for":
            return await _async_wait_for(kwargs.get("page_id", "default"),
                                         kwargs.get("wait_time", 0), kwargs.get("text_gone", ""))
        elif act == "pdf":
            return await _async_pdf(kwargs.get("page_id", "default"), kwargs.get("path", ""))
        elif act == "console_messages":
            return await _async_console_messages(kwargs.get("page_id", "default"), kwargs.get("level", "info"))
        elif act == "network_requests":
            return await _async_network_requests(kwargs.get("page_id", "default"), kwargs.get("include_static", False))
    except Exception as e:
        return _err(f"Action '{act}' raised: {e}")

# ── 后台线程管理 ─────────────────────────────────────────────
def _run_browser_loop():
    """浏览器后台线程：运行独立的 asyncio event loop"""
    global _BROWSER_LOOP
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _BROWSER_LOOP = loop
    try:
        loop.run_forever()
    finally:
        # 清理：停止浏览器
        try:
            loop.run_until_complete(_async_stop_browser())
        except Exception:
            pass
        loop.close()
        _BROWSER_LOOP = None

def _ensure_thread():
    """确保浏览器后台线程已启动"""
    global _BROWSER_THREAD
    if _BROWSER_THREAD is None or not _BROWSER_THREAD.is_alive():
        _SHUTDOWN.clear()
        _BROWSER_THREAD = threading.Thread(target=_run_browser_loop, name="browser-engine", daemon=True)
        _BROWSER_THREAD.start()
        # 等待 event loop 就绪
        for _ in range(50):
            if _BROWSER_LOOP is not None:
                return
            time.sleep(0.02)
        raise RuntimeError("Browser event loop failed to start")

def _run_async_in_thread(coro) -> str:
    """在浏览器线程中执行 async 函数，阻塞等待结果"""
    _ensure_thread()
    fut = asyncio.run_coroutine_threadsafe(coro, _BROWSER_LOOP)
    try:
        return fut.result(timeout=120)
    except Exception as e:
        return _err(f"Browser operation failed: {e}")

def _shutdown():
    """进程退出时清理"""
    _SHUTDOWN.set()
    if _BROWSER_LOOP:
        _BROWSER_LOOP.call_soon_threadsafe(_BROWSER_LOOP.stop)

atexit.register(_shutdown)

# ── 统一入口 ────────────────────────────────────────────────
def browser_use(
    action: str,
    url: str = "",
    page_id: str = "default",
    selector: str = "",
    text: str = "",
    code: str = "",
    path: str = "",
    wait: int = 0,
    full_page: bool = False,
    width: int = 0,
    height: int = 0,
    level: str = "info",
    filename: str = "",
    accept: bool = True,
    prompt_text: str = "",
    ref: str = "",
    element: str = "",
    paths_json: str = "",
    fields_json: str = "",
    key: str = "",
    submit: bool = False,
    slowly: bool = False,
    include_static: bool = False,
    screenshot_type: str = "png",
    snapshot_filename: str = "",
    double_click: bool = False,
    button: str = "left",
    modifiers_json: str = "",
    start_ref: str = "",
    end_ref: str = "",
    start_selector: str = "",
    end_selector: str = "",
    start_element: str = "",
    end_element: str = "",
    values_json: str = "",
    tab_action: str = "",
    index: int = -1,
    wait_time: float = 0,
    text_gone: str = "",
    frame_selector: str = "",
    headed: bool = False,
    cdp_port: int = 0,
    private_mode: bool = False,
    browser_args: str = "",
    executable_path: str = "",
    actions_json: str = "",
    cdp_url: str = "",
    port: int = 0,
    port_min: int = 0,
    port_max: int = 0,
) -> str:
    """
    浏览器统一操作入口（sync，线程安全）。
    所有参数对齐 QwenPaw browser_use，LLM 可直接生成 tool_calls。
    内部在独立线程中运行 async Playwright，与 FastAPI asyncio 无冲突。
    """
    kwargs = dict(
        action=action, url=url, page_id=page_id, selector=selector, text=text,
        code=code, path=path, wait=wait, full_page=full_page, width=width,
        height=height, level=level, filename=filename, ref=ref,
        key=key, submit=submit, slowly=slowly, include_static=include_static,
        screenshot_type=screenshot_type, snapshot_filename=snapshot_filename,
        double_click=double_click, button=button,
        tab_action=tab_action, index=index, wait_time=wait_time,
        text_gone=text_gone, headed=headed, browser_args=browser_args,
        executable_path=executable_path,
    )
    coro = _dispatch_async(**kwargs)
    return _run_async_in_thread(coro)
