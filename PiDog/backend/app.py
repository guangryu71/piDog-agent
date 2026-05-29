"""
PiDog Backend —— FastAPI 主应用
启动: uvicorn app:app --host 0.0.0.0 --port 8765 --reload
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import chat, model, tool, skill, token
from config import WORKING_DIRECTORY

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = FastAPI(
    title="PiDog Backend",
    description="SmartAgent V2 后端服务",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务 —— 让前端能直接访问工作目录下的图片等文件
if WORKING_DIRECTORY and os.path.isdir(WORKING_DIRECTORY):
    app.mount("/files", StaticFiles(directory=WORKING_DIRECTORY), name="files")

# API 路由（必须在 StaticFiles 挂载之前注册）
app.include_router(chat.router)
app.include_router(model.router)
app.include_router(tool.router)
app.include_router(skill.router)
app.include_router(token.router)


# ---- 页面路由（必须在 StaticFiles 挂载之前注册） ----

@app.get("/ui")
@app.get("/ui/")
def serve_ui():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "index.html not found"}


@app.get("/")
def root():
    return {"service": "PiDog Backend", "version": "1.0.0", "docs": "/docs", "ui": "/ui"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- 前端静态文件（放在最后，仅兜底匹配 — 所有显式路由优先） ----
# html=True 让 / 或未知路径自动返回 index.html
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8765, reload=True)
