"""
Token 追踪服务 —— 拦截 LLM API 调用并记录 token 消耗
"""

import os
import json
import threading
from typing import List, Dict
from datetime import datetime

from config import PROJECT_ROOT
from api_schemas.schemas import TokenUsage, TokenStats

TOKEN_LOG_FILE = os.path.join(PROJECT_ROOT, "PiDog", "backend", "token_usage.jsonl")
_lock = threading.Lock()


def record_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int):
    """记录单次 API 调用的 token 消耗"""
    entry = {
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "timestamp": datetime.now().isoformat(),
    }
    with _lock:
        os.makedirs(os.path.dirname(TOKEN_LOG_FILE), exist_ok=True)
        with open(TOKEN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_stats(days: int = 30) -> TokenStats:
    """查询 token 统计（最近 N 天）"""
    stats = TokenStats()
    if not os.path.exists(TOKEN_LOG_FILE):
        return stats

    cutoff = datetime.now().timestamp() - days * 86400

    with _lock:
        with open(TOKEN_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
                if ts < cutoff:
                    continue

                p_tokens = entry.get("prompt_tokens", 0)
                c_tokens = entry.get("completion_tokens", 0)
                provider = entry.get("provider", "unknown")
                model = entry.get("model", "unknown")

                stats.total_prompt += p_tokens
                stats.total_completion += c_tokens
                stats.total_all += p_tokens + c_tokens
                stats.calls += 1
                stats.by_provider[provider] = stats.by_provider.get(provider, 0) + p_tokens + c_tokens
                stats.by_model[model] = stats.by_model.get(model, 0) + p_tokens + c_tokens
                stats.recent.append(TokenUsage(
                    provider=provider,
                    model=model,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=p_tokens + c_tokens,
                    timestamp=entry["timestamp"],
                ))

    # 只保留最近 50 条
    stats.recent = stats.recent[-50:]
    return stats


def get_recent_usage(limit: int = 20) -> List[Dict]:
    """获取最近 N 条 token 使用记录"""
    if not os.path.exists(TOKEN_LOG_FILE):
        return []
    entries = []
    with _lock:
        with open(TOKEN_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries[-limit:]
