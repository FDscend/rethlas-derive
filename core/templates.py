"""模板渲染：生成 AGENTS、验证 AGENTS、生成侧 skills。"""
from __future__ import annotations

from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

GEN_SKILLS = (
    "obtain-immediate-conclusions",
    "construct-toy-examples",
    "construct-counterexamples",
    "propose-subgoal-decomposition-plans",
    "direct-proving",
    "identify-key-failures",
    "query-memory",
    "search-math-results",
    "recursive-proving",
)


def _load(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def render_generation_agents() -> str:
    return _load("AGENTS_generation.md")


def render_verification_agents() -> str:
    return _load("AGENTS_verification.md")


def render_generation_skill(name: str) -> str:
    if name not in GEN_SKILLS:
        raise ValueError(f"未知 skill: {name}")
    return _load(f"skills/{name}/SKILL.md")
