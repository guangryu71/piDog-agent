"""
Token 路由 —— 消耗统计
"""

from fastapi import APIRouter, Query
from services import token_service

router = APIRouter(prefix="/api/tokens", tags=["Tokens"])


@router.get("/stats")
def get_stats(days: int = Query(30, description="统计最近 N 天")):
    """获取 token 消耗统计"""
    return token_service.get_stats(days)


@router.get("/recent")
def get_recent(limit: int = Query(20, description="最近 N 条记录")):
    """获取最近 token 使用记录"""
    return token_service.get_recent_usage(limit)
