"""推导循环编排：搜索 -> 生成（codex 会话）-> 验证 -> 迭代 -> checkpoint。

流程完全在本工具内完成；主 agent 只需传入完整命题表述与可选参考文件。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import codex as codex_mod
from . import search as search_mod
from . import templates
from . import verify as verify_mod
from .config import Config
from .workspace import Checkpoint, Workspace, proposition_id


def _utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _tool_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ---------- 工作区与素材准备 ----------

def _setup_generation_workspace(ws: Workspace, config: Config, tool_dir: Path, workdir: Path) -> None:
    (ws.root / "AGENTS.md").write_text(templates.render_generation_agents(), encoding="utf-8")
    codex_dir = ws.root / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "config.toml").write_text(
        templates.render_codex_toml(
            config=config,
            python_exe=sys.executable,
            server=str(tool_dir / "core" / "agent_mcp.py"),
            tool_dir=str(tool_dir),
            workdir=str(workdir),
        ),
        encoding="utf-8",
    )


def _extract_ref_pdfs(ws: Workspace, config: Config) -> None:
    pdf_cfg = config.get("pdf", {})
    for pdf in sorted(ws.refs_dir.glob("*.pdf")):
        out_md = ws.refs_extracted_dir / f"{pdf.stem}.md"
        if out_md.exists():
            continue
        try:
            from . import pdf as pdf_mod

            pdf_mod.extract_pdf(pdf, out_md, pdf_cfg)
            print(f"[derive] 已提取参考 PDF: {pdf.name} -> {out_md}")
        except Exception as exc:
            print(f"[derive] 提取参考 PDF {pdf.name} 失败: {exc}")


def _search_round(ws: Workspace, cp: Checkpoint, statement: str, config: Config) -> None:
    search_cfg = config.get("search", {})
    ts_cfg = search_cfg.get("theoremsearch", {})
    n_results = int(ts_cfg.get("n_results", 5))
    timeout = int(ts_cfg.get("timeout_seconds", 120))
    backend = search_cfg.get("backend", "theoremsearch")
    try:
        results = search_mod.search(
            statement,
            n_results=n_results,
            backend=backend,
            theoremsearch=ts_cfg,
            timeout_seconds=timeout,
        )
        print(f"[derive] 搜索完成，得到 {len(results)} 条结果（backend={backend}）")
    except Exception as exc:
        print(f"[derive] 搜索失败: {exc}")
        results = []

    downloaded = []
    if search_cfg.get("download_papers", True):
        dl_cfg = search_cfg.get("download", {})
        fmt = dl_cfg.get("format", "tex")
        dto = int(dl_cfg.get("timeout_seconds", 60))
        drl = float(dl_cfg.get("ratelimit_seconds", 2))
        for r in results:
            got = search_mod.download_if_arxiv(
                r, ws.downloads_dir, fmt=fmt, timeout_seconds=dto, ratelimit_seconds=drl
            )
            if got:
                downloaded.append(got["path"])
                cp.downloads.append(got["path"])

    lines = ["# 搜索摘要\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. {r.get('name') or '(unnamed)'}  [{r.get('source')}]")
        lines.append(f"- statement: {r.get('body') or r.get('slogan') or ''}")
        lines.append(f"- paper: {r.get('paper_title')} (paper_id={r.get('paper_id')})")
        if r.get("arxiv_id"):
            status = "已下载到 downloads/" if r["arxiv_id"] in [str(Path(p).stem) for p in downloaded] else "未下载"
            lines.append(f"- arxiv: {r['arxiv_id']}（{status}）")
        lines.append("")
    ws.search_summary_path.write_text("\n".join(lines), encoding="utf-8")
    cp.updated_at = _utc()


# ---------- 生成提示词 ----------

def _gen_prompt_first(ws: Workspace) -> str:
    return (
        f"Use AGENTS.md exactly to solve the math problem in statement.md "
        f"(the statement is complete; assume all conditions are present). "
        f"problem_id={ws.problem_id}. "
        f"Read refs/ and downloads/ (including downloads/search_summary.md) as needed, "
        f"and use the MCP tools (memory, search, download) as instructed. "
        f"Write your best complete proof to results/blueprint.md (overwrite)."
    )


def _gen_prompt_resume(ws: Workspace, verify_payload: Optional[Dict[str, Any]]) -> str:
    if verify_payload:
        verdict = verify_payload.get("verdict", "?")
        report = verify_payload.get("verification_report") or {}
        summary = str(report.get("summary", ""))[:2000]
        hints = verify_payload.get("repair_hints")
        hint_text = f"\nRepair hints: {hints}" if hints else ""
        feedback = (
            f"The external verifier checked your last proof and returned verdict={verdict}. "
            f"Verification report: {summary}{hint_text}"
        )
    else:
        feedback = "The verifier has not produced feedback yet."
    return (
        f"Please continue working on the proof in results/blueprint.md. "
        f"{feedback} Fix the issues and overwrite results/blueprint.md with your best "
        f"complete proof. You may search more (MCP search/download) or reason deeply."
    )


# ---------- 主入口 ----------

def _result(ws: Workspace, cp: Checkpoint, success: bool,
            verify_payload: Optional[Dict[str, Any]], summary: str) -> Dict[str, Any]:
    result_md = str(ws.blueprint_verified_path) if success and ws.blueprint_verified_path.exists() else str(ws.blueprint_path)
    return {
        "id": cp.id,
        "success": success,
        "status": cp.status,
        "iterations_used": cp.iterations_used,
        "max_iterations": cp.max_iterations,
        "checkpoint": cp.iterations_used,
        "result_md_path": result_md,
        "draft_md_path": str(ws.blueprint_path),
        "log_dir": str(ws.logs_dir),
        "verification": verify_payload,
        "summary": summary,
    }


def derive(
    statement: str,
    refs: Optional[List[str]] = None,
    config: Optional[Config] = None,
    *,
    cli_workdir: Optional[str] = None,
    resume_id: Optional[str] = None,
    extra_iterations: Optional[int] = None,
    add_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """推导主流程。resume_id 非空时表示从 checkpoint 续推。"""
    if config is None:
        from .config import load_config

        config = load_config()
    workdir = config.resolve_workdir(cli_workdir)
    tool_dir = _tool_root()

    pid = resume_id or proposition_id(statement)
    ws = Workspace(workdir, pid)

    if resume_id:
        cp = ws.load_checkpoint()
        if cp is None:
            raise FileNotFoundError(f"workdir {workdir} 下未找到命题 {pid} 的 checkpoint（无法续推）")
        if add_refs:
            for p in ws.add_refs(add_refs):
                cp.refs.append(str(p))
        cp.max_iterations = cp.iterations_used + max(1, int(extra_iterations or 1))
        cp.updated_at = _utc()
        cp.status = "running"
        statement = cp.statement
    else:
        if ws.exists() and ws.blueprint_verified_path.exists():
            existing = ws.load_checkpoint()
            if existing is None:
                existing = Checkpoint(id=pid, statement=statement, created_at=_utc(), updated_at=_utc(),
                                      max_iterations=config.max_iterations, status="verified")
            return _result(ws, existing, True, None, "该命题已推导成功（已有 blueprint_verified.md）")
        ws.create_dirs()
        ws.write_statement(statement)
        copied = ws.add_refs(refs or []) if refs else []
        cp = Checkpoint(
            id=pid,
            statement=statement,
            created_at=_utc(),
            updated_at=_utc(),
            max_iterations=config.max_iterations,
            status="running",
            refs=[str(p) for p in copied],
        )

    # 素材准备
    _extract_ref_pdfs(ws, config)
    if not cp.downloads:
        _search_round(ws, cp, statement, config)
    _setup_generation_workspace(ws, config, tool_dir, workdir)
    ws.save_checkpoint(cp)

    total = cp.max_iterations
    last_verify: Optional[Dict[str, Any]] = None
    codex_cfg = config.get("codex", {})
    model = config.get("model", "gpt-5.6-terra")
    effort = config.get("reasoning_effort", "xhigh")
    timeout = int(codex_cfg.get("timeout_seconds", 0) or 0)
    bin_name = codex_cfg.get("bin", "codex")
    verify_enabled = bool(config.get("verify", {}).get("enabled", True))

    while cp.iterations_used < total:
        iter_no = cp.iterations_used + 1
        log_file = ws.logs_dir / f"iter_{iter_no}.md"
        if ws.blueprint_verified_path.exists():
            cp.status = "verified"
            cp.updated_at = _utc()
            ws.save_checkpoint(cp)
            return _result(ws, cp, True, last_verify, "推导已通过验证（blueprint_verified.md 已存在）")

        print(f"[derive] 第 {iter_no}/{total} 轮迭代开始 -> {log_file}")
        try:
            if iter_no == 1 and not cp.codex_session_id:
                res = codex_mod.run_codex(
                    cwd=ws.root, model=model, reasoning_effort=effort,
                    prompt=_gen_prompt_first(ws), log_path=log_file,
                    timeout_seconds=timeout, bin_name=bin_name,
                )
                if res.session_id:
                    cp.codex_session_id = res.session_id
            else:
                res = codex_mod.run_codex(
                    cwd=ws.root, model=model, reasoning_effort=effort,
                    prompt=_gen_prompt_resume(ws, last_verify), log_path=log_file,
                    timeout_seconds=timeout, bin_name=bin_name,
                    resume_session_id=cp.codex_session_id,
                )
        except Exception as exc:
            cp.status = "failed"
            cp.updated_at = _utc()
            ws.save_checkpoint(cp)
            return _result(ws, cp, False, last_verify, f"codex 运行失败: {exc}")

        cp.iterations_used = iter_no
        cp.updated_at = _utc()
        ws.save_checkpoint(cp)

        if res.returncode != 0:
            cp.status = "failed"
            ws.save_checkpoint(cp)
            return _result(ws, cp, False, last_verify, f"codex 退出码 {res.returncode}（见 {log_file}）")
        if not cp.codex_session_id:
            cp.status = "failed"
            ws.save_checkpoint(cp)
            return _result(ws, cp, False, last_verify, f"未能从日志提取 codex 会话 id（见 {log_file}）")

        # 验证当前草稿
        if verify_enabled and ws.blueprint_path.exists():
            try:
                payload = verify_mod.verify_proof(
                    ws, statement, ws.blueprint_path.read_text(encoding="utf-8"),
                    config, tool_dir, workdir,
                )
            except Exception as exc:
                print(f"[derive] 验证失败: {exc}")
                payload = None
            if payload:
                verdict = payload.get("verdict")
                cp.last_verdict = verdict
                cp.updated_at = _utc()
                if verdict == "correct":
                    ws.copy_verified(payload)
                    cp.status = "verified"
                    ws.save_checkpoint(cp)
                    return _result(ws, cp, True, payload, "推导通过验证")
                last_verify = payload
                print(f"[derive] 第 {iter_no} 轮验证未通过（verdict={verdict}），进入下一轮")
                ws.save_checkpoint(cp)
        else:
            last_verify = None

    cp.status = "failed"
    cp.updated_at = _utc()
    ws.save_checkpoint(cp)
    return _result(ws, cp, False, last_verify, f"达到最大迭代次数 {total}，仍未通过验证")
