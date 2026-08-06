"""内部 MCP server：供 codex 生成/验证会话使用（memory / search / download）。

由 codex 的 .codex/config.toml 以 stdio 方式启动：
    python -E core/agent_mcp.py --workdir <workdir_root>

配合 `-E` 使用（避免 PYTHONPATH 污染），因此这里手动把工具根目录加入 sys.path。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_HERE = Path(__file__).resolve()
_TOOL_ROOT = _HERE.parent.parent
if str(_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOL_ROOT))

from core import search as search_mod  # noqa: E402
from core import pdf as pdf_mod  # noqa: E402
from core.config import load_config  # noqa: E402
from core.workspace import Workspace  # noqa: E402

CHANNEL_FILES: Dict[str, str] = {
    "immediate_conclusions": "immediate_conclusions.jsonl",
    "toy_examples": "toy_examples.jsonl",
    "counterexamples": "counterexamples.jsonl",
    "big_decisions": "big_decisions.jsonl",
    "subgoals": "subgoals.jsonl",
    "proof_steps": "proof_steps.jsonl",
    "failed_paths": "failed_paths.jsonl",
    "verification_reports": "verification_reports.jsonl",
    "branch_states": "branch_states.jsonl",
    "events": "events.jsonl",
    # 验证 agent 专用
    "statement_checks": "statement_checks.jsonl",
    "reference_checks": "reference_checks.jsonl",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_dir(workdir: Path, problem_id: str) -> Path:
    return workdir / problem_id / "memory"


def _channel_path(workdir: Path, problem_id: str, channel: str) -> Path:
    if channel not in CHANNEL_FILES:
        allowed = ", ".join(sorted(CHANNEL_FILES))
        raise ValueError(f"未知通道 '{channel}'。允许: {allowed}")
    return _memory_dir(workdir, problem_id) / CHANNEL_FILES[channel]


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _bm25(query: str, documents: List[str], *, k1: float = 1.5, b: float = 0.75) -> List[float]:
    query_tokens = _tokenize(query)
    if not query_tokens or not documents:
        return [0.0 for _ in documents]
    query_counts = Counter(query_tokens)
    doc_counts = [Counter(_tokenize(d)) for d in documents]
    doc_lengths = [len(dc) for dc in doc_counts]
    avg_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0
    total = len(documents)
    df: Counter[str] = Counter()
    for dc in doc_counts:
        for token in set(dc):
            df[token] += 1
    scores: List[float] = []
    for dc, length in zip(doc_counts, doc_lengths):
        score = 0.0
        norm = k1 * (1.0 - b + b * (length / avg_len)) if avg_len > 0 else k1
        for token, qtf in query_counts.items():
            tf = dc.get(token, 0)
            if tf <= 0:
                continue
            idf = math.log(1.0 + ((total - df[token] + 0.5) / (df[token] + 0.5)))
            score += qtf * idf * (tf * (k1 + 1.0) / (tf + norm))
        scores.append(score)
    return scores


def _search_memory(workdir: Path, problem_id: str, query: str,
                   channel: Optional[str] = None, top_k: int = 8) -> List[Dict[str, Any]]:
    if channel:
        paths = [_channel_path(workdir, problem_id, channel)]
    else:
        mem_dir = _memory_dir(workdir, problem_id)
        paths = [mem_dir / name for name in CHANNEL_FILES.values() if (mem_dir / name).exists()]
    docs: List[Dict[str, Any]] = []
    texts: List[str] = []
    for path in paths:
        for payload in _iter_jsonl(path):
            text = json.dumps(payload, ensure_ascii=False)
            docs.append({"channel": path.stem, "record": payload, "text": text})
            texts.append(text)
    if not docs:
        return []
    scores = _bm25(query, texts)
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [
        {"score": round(score, 4), "channel": doc["channel"], "record": doc["record"]}
        for score, doc in ranked[: max(1, int(top_k))]
        if score > 0
    ]


def build_app(workdir: Path, config_path: Optional[str]):
    try:
        from fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要 fastmcp；请安装依赖：pip install -r requirements.txt") from exc

    config = load_config(config_path)
    app = FastMCP("derive-agent")

    @app.tool(name="memory_init")
    def memory_init(problem_id: str, meta: Dict[str, Any] = {}) -> Dict[str, Any]:
        """初始化命题的记忆目录与 meta.json。"""
        mem_dir = _memory_dir(workdir, problem_id)
        mem_dir.mkdir(parents=True, exist_ok=True)
        meta_path = mem_dir / "meta.json"
        payload = {"problem_id": problem_id, "meta": meta, "created_at": _utc_now()}
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "memory_dir": str(mem_dir)}

    @app.tool(name="memory_append")
    def memory_append(problem_id: str, channel: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """向指定通道追加一条记忆记录（append-only）。"""
        path = _channel_path(workdir, problem_id, channel)
        payload = {"ts": _utc_now(), **record}
        _append_jsonl(path, payload)
        return {"ok": True, "channel": channel, "path": str(path)}

    @app.tool(name="memory_search")
    def memory_search(problem_id: str, query: str, channel: Optional[str] = None,
                      top_k: int = 8) -> List[Dict[str, Any]]:
        """按 BM25 在记忆通道中检索相关记录。"""
        return _search_memory(workdir, problem_id, query, channel=channel, top_k=top_k)

    @app.tool(name="search_arxiv_theorems")
    def search_arxiv_theorems(problem_id: str, query: str, num_results: int = 5) -> Dict[str, Any]:
        """语义搜索相关数学定理/论文（TheoremSearch），返回归一化结果列表。"""
        search_cfg = config.get("search", {})
        ts_cfg = search_cfg.get("theoremsearch", {})
        results = search_mod.search(
            query,
            n_results=max(1, int(num_results)),
            backend=search_cfg.get("backend", "theoremsearch"),
            theoremsearch=ts_cfg,
            timeout_seconds=int(ts_cfg.get("timeout_seconds", 120)),
        )
        return {"query": query, "count": len(results), "results": results}

    @app.tool(name="download_paper")
    def download_paper(problem_id: str, arxiv_id: str, fmt: str = "tex") -> Dict[str, Any]:
        """下载 arXiv 论文到命题的 downloads/（默认 TeX 源，免 PDF 转换）。

        若返回 PDF（PDF-only 投稿），自动提取文本到 downloads/.extracted/。
        """
        ws = Workspace(workdir, problem_id)
        dl_cfg = config.get("search", {}).get("download", {})
        got = search_mod.download_arxiv(
            arxiv_id,
            ws.downloads_dir,
            fmt=fmt,
            timeout_seconds=int(dl_cfg.get("timeout_seconds", 60)),
            ratelimit_seconds=float(dl_cfg.get("ratelimit_seconds", 2)),
        )
        result: Dict[str, Any] = {"kind": got["kind"], "path": got["path"]}
        if got["kind"] == "pdf":
            out_md = ws.downloads_dir / ".extracted" / f"{Path(got['path']).stem}.md"
            pdf_mod.extract_pdf(Path(got["path"]), out_md, config.get("pdf", {}))
            result["extracted_md"] = str(out_md)
        return result

    @app.tool(name="get_references")
    def get_references(problem_id: str) -> Dict[str, Any]:
        """列出当前命题可用的参考资料（refs / downloads / 搜索摘要）。"""
        ws = Workspace(workdir, problem_id)

        def _list(d: Path) -> List[str]:
            return sorted(str(p) for p in d.iterdir() if p.is_file()) if d.exists() else []

        return {
            "problem_id": problem_id,
            "refs": _list(ws.refs_dir),
            "refs_extracted": _list(ws.refs_extracted_dir),
            "downloads": _list(ws.downloads_dir),
            "search_summary": str(ws.search_summary_path) if ws.search_summary_path.exists() else None,
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="内部 MCP server（memory/search/download）")
    parser.add_argument("--workdir", required=True, help="命题数据工作目录根")
    parser.add_argument("--config", default=None, help="config.yaml 路径")
    args = parser.parse_args()
    workdir = Path(args.workdir).expanduser().resolve()
    app = build_app(workdir, args.config)
    app.run()


if __name__ == "__main__":
    main()
