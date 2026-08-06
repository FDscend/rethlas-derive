"""统一配置：默认值 + 可选 config.yaml + CLI 覆盖。

字段清单见 config.yaml（TODO.md「配置」节）：
所有默认值均可被 CLI 参数覆盖。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML 在 requirements.txt 中
    yaml = None

DEFAULT_CONFIG: Dict[str, Any] = {
    "model": "gpt-5.6-terra",
    "reasoning_effort": "xhigh",
    "max_iterations": 8,
    "workdir": "./workspace",
    "codex": {
        "bin": "codex",
        "timeout_seconds": 0,
    },
    "search": {
        "backend": "theoremsearch",
        "max_search_rounds": 3,
        "download_papers": True,
        "download": {
            "format": "tex",
            "timeout_seconds": 60,
            "ratelimit_seconds": 2,
        },
        "theoremsearch": {
            "api_base": "https://api.theoremsearch.com",
            "n_results": 5,
            "timeout_seconds": 120,
        },
        "leansearch": {
            "endpoint": "https://leansearch.net/thm/search",
        },
    },
    "pdf": {
        "backend": "mineru",
        "mineru": {
            "mode": "extract",
            "model": "vlm",
            "auth": "npm-cli",
            "timeout_seconds": 900,
        },
        "pymupdf": {
            "layout": True,
        },
    },
    "verify": {
        "enabled": True,
        "max_attempts": 3,
    },
    "logging": {
        "level": "INFO",
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并 override 到 base 的副本上。"""
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def workdir(self) -> Path:
        return Path(self.data["workdir"]).expanduser().resolve()

    @property
    def max_iterations(self) -> int:
        return max(1, int(self.data.get("max_iterations", 8)))

    def resolve_workdir(self, cli_workdir: Optional[str] = None) -> Path:
        if cli_workdir:
            return Path(cli_workdir).expanduser().resolve()
        return self.workdir

    def apply_overrides(self, **overrides: Any) -> "Config":
        """把 CLI 覆盖项合并进配置（如 max_iterations=…, workdir=…）。"""
        self.data = deep_merge(self.data, overrides)
        return self


def find_default_config_path() -> Optional[Path]:
    env_cfg = os.environ.get("DERIVE_CONFIG")
    if env_cfg:
        return Path(env_cfg)
    here = Path(__file__).resolve().parent.parent
    for name in ("config.yaml", "config.yml"):
        candidate = here / name
        if candidate.exists():
            return candidate
    return None


def load_config(path: Optional[str] = None) -> Config:
    """加载配置：默认值 <- config.yaml <- （后续由 CLI 覆盖）。"""
    data = deep_merge({}, DEFAULT_CONFIG)
    config_path = Path(path) if path else find_default_config_path()
    if config_path and config_path.exists():
        if yaml is None:
            raise RuntimeError(
                "读取 config.yaml 需要 PyYAML；请先安装依赖：pip install -r requirements.txt"
            )
        with config_path.open("r", encoding="utf-8") as fh:
            user_data = yaml.safe_load(fh) or {}
        data = deep_merge(data, user_data)
    return Config(data)
