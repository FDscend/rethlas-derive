"""模板渲染：codex 配置 toml、生成 AGENTS、验证 AGENTS。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .config import Config

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _load(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def render_codex_toml(
    config: Config,
    python_exe: str,
    server: str,
    tool_dir: str,
    workdir: str,
) -> str:
    text = _load("codex_config.toml")
    return (
        text.replace("{{MODEL}}", str(config.get("model", "gpt-5.6-terra")))
        .replace("{{EFFORT}}", str(config.get("reasoning_effort", "xhigh")))
        .replace("{{PYTHON}}", python_exe)
        .replace("{{SERVER}}", server)
        .replace("{{TOOL_DIR}}", tool_dir)
        .replace("{{WORKDIR}}", workdir)
    )


def render_generation_agents() -> str:
    return _load("AGENTS_generation.md")


def render_verification_agents() -> str:
    return _load("AGENTS_verification.md")
