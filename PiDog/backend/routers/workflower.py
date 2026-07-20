"""
工作流资产路由 —— 保存和加载工作流执行资产
每次执行工作流后将 monitor / output 节点的内容持久化到 workflower/ 目录
"""

import os
import json
import time
import base64
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import PROJECT_ROOT

router = APIRouter(prefix="/api/workflower", tags=["Workflow Assets"])

# ── 资产存储目录 ──
ASSETS_DIR = os.path.join(PROJECT_ROOT, "PiDog", "workflower")
os.makedirs(ASSETS_DIR, exist_ok=True)


# ── 数据模型 ──
class NodeAsset(BaseModel):
    nodeId: str
    type: str
    modelName: str
    category: str          # "output" | "monitor"
    order: int
    contentType: str       # "text" | "image" | "audio" | "video"
    content: str           # text 或 base64 数据
    fileName: Optional[str] = None  # 二进制文件保存后的文件名


class SaveAssetRequest(BaseModel):
    timestamp: str
    formattedTime: str
    nodeCount: int
    duration: str
    nodes: list[NodeAsset]


# ── 工具 ──
def _read_meta(timestamp: str) -> Optional[dict]:
    """读取单个资产的 metadata.json"""
    p = os.path.join(ASSETS_DIR, timestamp, "metadata.json")
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ── API ──

@router.get("/list")
def list_assets():
    """列出所有已保存的工作流资产（仅元信息，不含文件内容）"""
    if not os.path.isdir(ASSETS_DIR):
        return {"assets": []}
    try:
        items = []
        for name in sorted(os.listdir(ASSETS_DIR), reverse=True):
            meta = _read_meta(name)
            if meta:
                items.append(meta)
        return {"assets": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{timestamp}")
def get_asset(timestamp: str):
    """获取单个资产详情，加载二进制文件内容为 data URL"""
    meta = _read_meta(timestamp)
    if not meta:
        raise HTTPException(status_code=404, detail="资产未找到")
    asset_dir = os.path.join(ASSETS_DIR, timestamp)

    for node in meta.get("nodes", []):
        fname = node.get("fileName", "")
        ct = node.get("contentType", "")
        if fname and ct in ("image", "audio", "video"):
            fp = os.path.join(asset_dir, fname)
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                prefix_map = {
                    "image": "data:image/png;base64,",
                    "audio": "data:audio/mpeg;base64,",
                    "video": "data:video/mp4;base64,",
                }
                node["content"] = (prefix_map.get(ct, "data:;base64,")) + b64
    return meta


@router.post("/save")
def save_asset(req: SaveAssetRequest):
    """保存工作流执行资产"""
    ts = req.timestamp
    asset_dir = os.path.join(ASSETS_DIR, ts)
    os.makedirs(asset_dir, exist_ok=True)

    meta = {
        "timestamp": ts,
        "formattedTime": req.formattedTime,
        "nodeCount": req.nodeCount,
        "duration": req.duration,
    }

    nodes_meta = []
    for node in req.nodes:
        nd = node.model_dump()
        ct = node.contentType
        # 二进制内容 → 写入独立文件，metadata 只保留文件名引用
        if ct in ("image", "audio", "video") and node.content:
            if not nd.get("fileName"):
                ext_map = {"image": "png", "audio": "mp3", "video": "mp4"}
                nd["fileName"] = f"{node.nodeId}.{ext_map.get(ct, 'dat')}"
            # 解码 base64（含 data URL 前缀或纯 base64）
            raw = node.content
            if "," in raw:
                raw = raw.split(",", 1)[1]
            try:
                bin_data = base64.b64decode(raw)
                fp = os.path.join(asset_dir, nd["fileName"])
                with open(fp, "wb") as f:
                    f.write(bin_data)
            except Exception:
                nd["fileName"] = ""  # 解码失败则跳过
            nd["content"] = ""  # 不在 JSON 中嵌入大段二进制
        nodes_meta.append(nd)

    meta["nodes"] = nodes_meta

    with open(os.path.join(asset_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"success": True, "timestamp": ts}


@router.get("/{timestamp}/file/{node_id}")
def get_asset_file(timestamp: str, node_id: str):
    """获取某个节点的二进制内容文件"""
    meta = _read_meta(timestamp)
    if not meta:
        raise HTTPException(status_code=404, detail="资产未找到")

    for node in meta.get("nodes", []):
        if node["nodeId"] == node_id and node.get("fileName"):
            fp = os.path.join(ASSETS_DIR, timestamp, node["fileName"])
            if os.path.isfile(fp):
                media_map = {
                    "image": "image/png",
                    "audio": "audio/mpeg",
                    "video": "video/mp4",
                }
                mt = media_map.get(node.get("contentType", ""), "application/octet-stream")
                return FileResponse(fp, media_type=mt, filename=node["fileName"])

    raise HTTPException(status_code=404, detail="文件未找到")
