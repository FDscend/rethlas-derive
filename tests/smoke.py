"""冒烟测试：不依赖 codex 的部分（配置 / workspace / 搜索 / arXiv 下载 / PDF 提取 / 内部 MCP）。

用法（在项目根目录）：
    .venv\\Scripts\\python tests\\smoke.py [--offline]

--offline 时跳过需要网络的搜索与 arXiv 下载。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import load_config  # noqa: E402
from core.workspace import Checkpoint, Workspace, proposition_id  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def test_config() -> None:
    print("== config ==")
    c = load_config()
    check("model default", c.get("model") == "gpt-5.6-terra")
    check("max_iterations default", c.max_iterations == 8)
    check("workdir resolved", str(c.workdir).endswith("workspace"))
    overridden = c.apply_overrides(max_iterations=3, workdir="./tmp_w")
    check("override max_iterations", overridden.max_iterations == 3)
    check("override workdir", str(overridden.workdir).endswith("tmp_w"))
    check("nested override", c.get("search")["download"]["format"] == "tex")


def test_workspace() -> None:
    print("== workspace ==")
    s = "If P is a projective module over a local ring R, then P is free."
    pid = proposition_id(s)
    check("id stable", proposition_id(s) == pid)
    with tempfile.TemporaryDirectory() as td:
        ws = Workspace(Path(td), pid)
        ws.create_dirs()
        ws.write_statement(s)
        cp = Checkpoint(id=pid, statement=s, created_at="t", updated_at="t", max_iterations=8)
        cp.iterations_used = 3
        cp.codex_session_id = "sess_123"
        ws.save_checkpoint(cp)
        cp2 = ws.load_checkpoint()
        check("checkpoint roundtrip", cp2 is not None and cp2.iterations_used == 3 and cp2.codex_session_id == "sess_123")
        # cleanup intermediate keeps statement/refs/results/checkpoint
        res = ws.cleanup("intermediate")
        check("clean intermediate", ws.statement_path.exists() and ws.checkpoint_path.exists() and not ws.logs_dir.exists())


def test_search(offline: bool) -> None:
    print("== search + arXiv download ==")
    from core import search as sm

    if offline:
        print("  (跳过网络测试)")
        return
    res = sm.search("Any projective module over a local ring is free", n_results=3)
    check("search returns results", len(res) > 0)
    arxiv_items = [r for r in res if r.get("arxiv_id")]
    check("search includes arxiv_id", len(arxiv_items) > 0, f"got {len(arxiv_items)}")
    if arxiv_items:
        with tempfile.TemporaryDirectory() as td:
            got = sm.download_arxiv(arxiv_items[0]["arxiv_id"], Path(td), fmt="tex", ratelimit_seconds=0)
            check("arxiv tex download", got["kind"] == "tex" and Path(got["path"]).exists())


def test_pdf(offline: bool) -> None:
    print("== pdf (PyMuPDF) ==")
    import fitz
    from core import pdf as pdf_mod

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "doc.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello theorem: all rings are commutative.")
        doc.save(str(src))
        doc.close()
        out = Path(td) / "extracted" / "doc.md"
        pdf_mod.extract_pdf(src, out, {"backend": "pymupdf", "pymupdf": {"layout": True}})
        text = out.read_text(encoding="utf-8")
        check("pymupdf extraction", "commutative" in text)
    if offline:
        print("  (跳过 MinerU CLI 链，仅测离线降级)")


async def _mcp_tools(workdir: Path) -> list:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-E", str(ROOT / "core" / "agent_mcp.py"), "--workdir", str(workdir)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [t.name for t in tools.tools]


async def _mcp_call(workdir: Path, tool: str, args: dict):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-E", str(ROOT / "core" / "agent_mcp.py"), "--workdir", str(workdir)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            text = "".join(
                item.text for item in result.content if hasattr(item, "text") and item.text
            )
            return json.loads(text) if text else None


def test_agent_mcp() -> None:
    print("== internal MCP server ==")
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        pid = "prop_test"
        names = asyncio.run(_mcp_tools(workdir))
        expected = {"memory_init", "memory_append", "memory_search",
                    "search_arxiv_theorems", "download_paper", "get_references"}
        check("tools exposed", expected.issubset(set(names)), f"got {names}")

        init = asyncio.run(_mcp_call(workdir, "memory_init", {"problem_id": pid, "meta": {"k": "v"}}))
        check("memory_init", init is not None and init.get("ok") is True)

        ap = asyncio.run(_mcp_call(workdir, "memory_append",
                                   {"problem_id": pid, "channel": "proof_steps",
                                    "record": {"step": "use Zorn's lemma"}}))
        check("memory_append", ap is not None and ap.get("ok") is True)

        hit = asyncio.run(_mcp_call(workdir, "memory_search",
                                    {"problem_id": pid, "query": "Zorn lemma"}))
        check("memory_search hit", isinstance(hit, list) and len(hit) >= 1, f"got {hit}")

        refs = asyncio.run(_mcp_call(workdir, "get_references", {"problem_id": pid}))
        check("get_references", isinstance(refs, dict) and refs.get("problem_id") == pid)


def test_cli() -> None:
    print("== cli ==")
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli.py"), "list", "--workdir", td],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        check("cli list rc=0", proc.returncode == 0, proc.stderr[-500:])
        data = json.loads(proc.stdout)
        check("cli list json", isinstance(data, dict) and data.get("workdir", "").endswith(td))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="跳过网络测试")
    args = parser.parse_args()
    test_config()
    test_workspace()
    test_search(args.offline)
    test_pdf(args.offline)
    test_agent_mcp()
    test_cli()
    print(f"\n结果: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
