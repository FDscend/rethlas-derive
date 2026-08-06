"""网络搜索：Tavily REST（优先），无 key 时由调用方降级到 codex 内置 web search。

参考：
- 总览  https://docs.tavily.com/welcome
- API   https://docs.tavily.com/documentation/api-reference/introduction
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .env import load_env_value

TAVILY_API = "https://api.tavily.com/search"


def get_tavily_key(env_path: Optional[Any] = None) -> Optional[str]:
    return load_env_value("TAVILY_API_KEY", env_path)


def tavily_search(
    query: str,
    api_key: str,
    max_results: int = 5,
    timeout_seconds: int = 30,
    search_depth: str = "basic",
) -> List[Dict[str, Any]]:
    """Tavily REST 搜索，返回归一化结果。"""
    if not query.strip():
        raise ValueError("query 不能为空")
    resp = requests.post(
        TAVILY_API,
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max(1, int(max_results)),
            "search_depth": search_depth,
        },
        timeout=timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", []) if isinstance(data, dict) else []
    normalized: List[Dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score"),
            }
        )
    return normalized


def web_search(
    query: str,
    max_results: int = 5,
    timeout_seconds: int = 30,
    env_path: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """若配置了 TAVILY_API_KEY 则用 Tavily；否则返回 []（调用方应降级到 codex web_search=live）。"""
    key = get_tavily_key(env_path)
    if not key:
        return []
    return tavily_search(
        query, api_key=key, max_results=max_results, timeout_seconds=timeout_seconds
    )
