import sys, json, time, os
sys.path.insert(0, r"D:\developer\myProject\fianl_show\smart_agent_new")

from utils.web_controler.browser_engine import browser_use, set_workspace_dir

# Fix 1: workspace dir
ws = r"D:\developer\myProject\buffer\smart_agent_new\workplace"
set_workspace_dir(ws)
print("1. Workspace set:", ws)

# Fix 2: start browser
r = json.loads(browser_use(action='start', headed=True))
print("2. START:", r.get('ok'), '-', r.get('browser','?'))

# Fix 3: open Bilibili
r = json.loads(browser_use(action='open', url='https://www.bilibili.com'))
print("3. OPEN:", r.get('ok'), '-', r.get('url','?'))

# Fix 4: type with WRONG selector → should fallback to searchbox
r = json.loads(browser_use(action='type', selector="input[type='search']", text='python教程'))
print("4. TYPE (wrong selector):", r.get('ok'), '-', r.get('message','?'), 'via:', r.get('via',''))

# Fix 5: press Enter to search
r = json.loads(browser_use(action='press_key', key='Enter'))
print("5. ENTER:", r.get('ok'))

# Fix 6: screenshot with relative path
import time
r = json.loads(browser_use(action='screenshot', path='files/bilibili_search.png', full_page=True))
print("6. SCREENSHOT:", r.get('ok'), '-', r.get('path','?'))

# Verify file exists
full = os.path.join(ws, 'files', 'bilibili_search.png')
print("   Exists:", os.path.exists(full), full)

# 7. Stop
r = json.loads(browser_use(action='stop'))
print("7. STOP:", r.get('ok'))
