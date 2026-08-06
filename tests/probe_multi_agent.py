"""探测 codex 0.146 exec 模式下 multi_agent + subgoal-prover 子代理是否可用。

用法：.venv\\Scripts\\python tests\\probe_multi_agent.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import codex as codex_mod  # noqa: E402

CODEX_CFG = """model = "gpt-5.6-terra"
model_reasoning_effort = "low"

[features]
multi_agent = true

[features.multi_agent_v2]
hide_spawn_agent_metadata = false
tool_namespace = "agents"

[agents]
max_threads = 4
max_depth = 2

[agents.subgoal-prover]
description = "An agent that proves all the subgoals in a subgoal decomposition plan."
config_file = "./agents/subgoal-prover.toml"
"""
SUBAGENT_CFG = """name = "subgoal-prover"
description = "An agent that tries to prove all the subgoals in a subgoal decomposition plan."
model = "gpt-5.6-terra"
model_reasoning_effort = "low"
developer_instructions = \"\"\"
You are a subgoal prover agent. Your task is to prove all the subgoals in a subgoal decomposition plan. You follow AGENTS.md to work on this task. If you cannot prove all the subgoals, please summarize the subgoals that you have proved and the subgoals that you have not proved, and explain the reasons why you cannot prove the remaining subgoals.
\"\"\"
"""

AGENTS = """# Probe Agent

You may spawn sub-agents using the collaboration tools (spawn_agent / spawn_agents / wait_agent).
"""

PROMPT = (
    "You MUST use the collaboration tool to spawn a sub-agent for the following task: "
    "prove that every finite group of prime order is cyclic. "
    "IMPORTANT: spawn a plain generic sub-agent — do NOT specify agent_type, and do NOT "
    "fork with full history. Spawn a fresh sub-agent with just the task message, then use "
    "wait to collect its result, and report the verdict it returns. "
    "If you cannot spawn sub-agents, reply exactly: NO_SUBAGENT_TOOL"
)


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = Path(td)
        (root / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
        (root / "statement.md").write_text("probe", encoding="utf-8")
        (root / ".codex").mkdir(exist_ok=True)
        (root / ".codex" / "config.toml").write_text(CODEX_CFG, encoding="utf-8")
        # config_file 相对 .codex/ 解析：Rethlas 把 subgoal-prover.toml 放在 .codex/agents/
        (root / ".codex" / "agents").mkdir(exist_ok=True)
        (root / ".codex" / "agents" / "subgoal-prover.toml").write_text(SUBAGENT_CFG, encoding="utf-8")

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
        # 子代理证据
        for kw in ("spawn_agent", "spawn_agents", "subagent", "sub-agent", "subgoal-prover", "NO_SUBAGENT_TOOL", "wait_agent"):
            count = text.lower().count(kw.lower())
            print(f"  '{kw}': {count}")
        print("---- log tail ----")
        print(text[-2500:])


if __name__ == "__main__":
    main()
