"""推导循环逻辑测试（不真跑 codex，用 fake 替代 run_codex / verify_proof）。

验证：fresh derive -> 搜索(空) -> 生成 -> 验证wrong -> 续迭代 -> 验证correct -> 成功；
以及 resume 续推路径。使用临时 workdir，不污染真实 workspace。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import codex as codex_mod  # noqa: E402
from core import derive as derive_mod  # noqa: E402
from core import search as search_mod  # noqa: E402
from core import verify as verify_mod  # noqa: E402
from core.config import Config  # noqa: E402
from core.workspace import proposition_id  # noqa: E402

STATEMENT = "If P is a projective module over a local ring R, then P is free."


def make_config(workdir: str) -> Config:
    return Config(
        {
            "model": "test-model",
            "reasoning_effort": "xhigh",
            "max_iterations": 3,
            "workdir": workdir,
            "codex": {"bin": "codex", "timeout_seconds": 0},
            "search": {
                "backend": "theoremsearch",
                "download_papers": False,
                "theoremsearch": {"n_results": 3, "timeout_seconds": 30},
            },
            "pdf": {"backend": "pymupdf"},
            "verify": {"enabled": True, "max_attempts": 1},
            "logging": {"level": "INFO"},
        }
    )


def main() -> None:
    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    # --- fake codex：写 blueprint.md + 在日志里写入 session id ---
    def fake_run_codex(cwd, model, reasoning_effort, prompt, log_path,
                       timeout_seconds=0, bin_name="codex", resume_session_id=None,
                       extra_configs=None):
        cwd = Path(cwd)
        results = cwd / "results"
        results.mkdir(parents=True, exist_ok=True)
        n = len(list((cwd / "logs" / "iter").glob("iter_*.md"))) if (cwd / "logs" / "iter").exists() else 0
        body = (
            f"# theorem\n\n## statement\n{STATEMENT}\n\n## proof\n"
            f"Draft proof iteration {n + 1} (resume={resume_session_id is not None}).\n"
        )
        (results / "blueprint.md").write_text(body, encoding="utf-8")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"session id: fake_session_{n + 1}\n", encoding="utf-8")
        return codex_mod.CodexResult(0, f"fake_session_{n + 1}", log_path)

    # --- fake verify：第一次 wrong，之后 correct ---
    state = {"calls": 0}

    def fake_verify(ws, statement, proof, config):
        state["calls"] += 1
        if state["calls"] == 1:
            return {
                "verdict": "wrong",
                "verification_report": {"summary": "missing one argument"},
                "repair_hints": ["add the missing argument"],
            }
        return {"verdict": "correct", "verification_report": {"summary": "ok"}}

    derive_mod.codex_mod.run_codex = fake_run_codex
    derive_mod.verify_mod.verify_proof = fake_verify
    search_calls = {"n": 0}

    def fake_search(*a, **k):
        search_calls["n"] += 1
        return []  # 搜索返回空，避免网络

    derive_mod.search_mod.search = fake_search
    derive_mod.web_search_mod.get_tavily_key = lambda *a, **k: None  # 无 Tavily key

    with tempfile.TemporaryDirectory() as td:
        config = make_config(td)
        print("== fresh derive (wrong -> correct) ==")
        result = derive_mod.derive(STATEMENT, config=config)
        check("success after 2 iters", result["success"] is True)
        check("iterations_used == 2", result["iterations_used"] == 2, )
        check("status verified", result["status"] == "verified")
        check("result_md exists", result["result_md_path"] and Path(result["result_md_path"]).exists())
        check("id stable", result["id"] == proposition_id(STATEMENT))
        check("draft + verified", Path(result["draft_md_path"]).exists())

        ws_dir = Path(td) / result["id"]
        check("AGENTS.md written", (ws_dir / "AGENTS.md").exists())
        agents = (ws_dir / "AGENTS.md").read_text(encoding="utf-8")
        check("AGENTS objective", "blueprint.md" in agents)
        check("AGENTS file-based memory", "memory/" in agents)
        check("AGENTS references skills", "$direct-proving" in agents)
        check("checkpoint verified", (ws_dir / "checkpoint.json").exists())

        # P1-1：按需检索触发（初始 1 轮 + 第 2 轮迭代重搜）
        check("re-search triggered", search_calls["n"] >= 2)
        summary = (ws_dir / "downloads" / "search_summary.md").read_text(encoding="utf-8")
        check("search summary accumulated", "第 2 轮搜索" in summary)

        # P2-1：skills 生成到工作区
        skills = ws_dir / ".agents" / "skills"
        check("skills generated", (skills / "obtain-immediate-conclusions" / "SKILL.md").exists()
               and (skills / "search-math-results" / "SKILL.md").exists())

        # 重复 derive：应直接返回已成功
        again = derive_mod.derive(STATEMENT, config=config)
        check("re-derive short-circuits", again["success"] is True and again["iterations_used"] == result["iterations_used"])

    # --- resume 路径：fresh 全 wrong（跑满 3 轮失败），resume 追加 2 轮后成功 ---
    state_all_wrong = {"n": 0}

    def fake_verify_all_wrong(ws, statement, proof, config):
        state_all_wrong["n"] += 1
        return {"verdict": "wrong", "verification_report": {"summary": "nope"}, "repair_hints": []}

    derive_mod.verify_mod.verify_proof = fake_verify_all_wrong

    with tempfile.TemporaryDirectory() as td:
        config = make_config(td)
        print("== resume path ==")
        r1 = derive_mod.derive(STATEMENT, config=config, cli_workdir=td)
        check("first derive failed (ran max=3)", r1["success"] is False and r1["iterations_used"] == 3)
        pid = r1["id"]

        state_pass = {"n": 0}

        def fake_verify_wrong_then_pass(ws, statement, proof, config):
            state_pass["n"] += 1
            if state_pass["n"] <= 1:
                return {"verdict": "wrong", "verification_report": {"summary": "still missing"}, "repair_hints": []}
            return {"verdict": "correct", "verification_report": {"summary": "ok"}}

        derive_mod.verify_mod.verify_proof = fake_verify_wrong_then_pass
        r2 = derive_mod.derive("", config=config, cli_workdir=td, resume_id=pid, extra_iterations=2)
        check("resume succeeded", r2["success"] is True)
        check("resume total iters == 5", r2["iterations_used"] == 5)
        check("resume same id", r2["id"] == pid)

        # resume 不存在的 id -> 报错
        try:
            derive_mod.derive("", config=config, cli_workdir=td, resume_id="prop_nonexist", extra_iterations=1)
            check("resume unknown id raises", False)
        except FileNotFoundError:
            check("resume unknown id raises", True)

    print(f"\n结果: {'ALL PASS' if fails == 0 else str(fails) + ' FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
