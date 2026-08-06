"""探测 codex 0.146 是否从 -C 目录加载 .agents/skills。

用法：.venv\\Scripts\\python tests\\probe_skills.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import codex as codex_mod  # noqa: E402

SKILL = """---
name: test-derive-skill
description: A probe skill that knows the magic answer 42. Use to check skill loading.
---

# Test Derive Skill

If asked, reply that the magic answer is 42.
"""

AGENTS = """# Test Agent

## Skills

- Use `$test-derive-skill` when asked about the magic answer.
"""

PROMPT = (
    "List the skills that are available to you in this session (names only, "
    "one per line, e.g. names starting with test-). Then state the magic answer "
    "from the test skill. If no skills are available, reply exactly: NO_SKILLS"
)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
        (root / "statement.md").write_text("probe", encoding="utf-8")
        skill_dir = root / ".agents" / "skills" / "test-derive-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(SKILL, encoding="utf-8")

        log = root / "probe.log"
        res = codex_mod.run_codex(
            cwd=root,
            model="gpt-5.6-terra",
            reasoning_effort="low",
            prompt=PROMPT,
            log_path=log,
            bin_name="codex",
        )
        text = log.read_text(encoding="utf-8", errors="replace")
        print(f"rc: {res.returncode}")
        print(text[-2000:])


if __name__ == "__main__":
    main()
