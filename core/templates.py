"""模板渲染：生成 AGENTS、验证 AGENTS。"""
from __future__ import annotations

from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _load(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def render_generation_agents() -> str:
    return _load("AGENTS_generation.md")


def render_verification_agents() -> str:
    return _load("AGENTS_verification.md")
