"""环境变量 / .env 文件读取（当前工作目录 + 工具根目录）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


def _tool_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _env_candidates() -> List[Path]:
    return [Path.cwd() / ".env", _tool_root() / ".env"]


def load_env_value(key: str, env_path: Optional[Path] = None) -> Optional[str]:
    """从环境变量或 .env 文件读取 key（支持 KEY=value，自动去除引号/首尾空白）。"""
    value = os.environ.get(key)
    if value:
        return value.strip()
    candidates: List[Path] = []
    if env_path:
        candidates.append(env_path)
    candidates += _env_candidates()
    for cand in candidates:
        if cand and cand.exists():
            try:
                for line in cand.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line.startswith(key) and "=" in line:
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
            except OSError:
                continue
    return None
