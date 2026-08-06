"""定理搜索（TheoremSearch 官方服务）+ arXiv 论文下载（默认 TeX 源，免 PDF 转换）。

论文下载由本工具自身实现：
- 用搜索结果里的 arXiv ID 构造 https://arxiv.org/e-print/{id} 下载 TeX 源；
  e-print 返回 tar.gz（含多个 .tex）或单 .tex；解压后拼接所有 .tex 为 <id>.tex。
- 仅当 e-print 不可用（PDF-only 投稿）时降级下载 PDF。
- 仅 source=arXiv 的结果可下载；Stacks Project / ProofWiki 等来源跳过。
- 下载需限速、设超时，失败跳过（不强求全文）。
"""
from __future__ import annotations

import io
import re
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ARXIV_E_PRINT = "https://arxiv.org/e-print/{id}"
ARXIV_PDF = "https://arxiv.org/pdf/{id}"


def search_theoremsearch(
    query: str,
    n_results: int = 5,
    api_base: str = "https://api.theoremsearch.com",
    timeout_seconds: int = 120,
) -> List[Dict[str, Any]]:
    """调用 TheoremSearch /search，归一化为统一结构（含 arxiv_id）。"""
    if not query.strip():
        raise ValueError("query 不能为空")
    url = f"{api_base.rstrip('/')}/search"
    payload = {"query": query, "n_results": max(1, int(n_results))}
    resp = requests.post(url, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("theorems", []) if isinstance(data, dict) else []
    normalized: List[Dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        paper = item.get("paper") or {}
        paper_id = paper.get("paper_id")
        arxiv_id = None
        if paper.get("source") == "arXiv" and paper_id:
            arxiv_id = paper_id
        normalized.append(
            {
                "name": item.get("name"),
                "body": item.get("body"),
                "slogan": item.get("slogan"),
                "source": paper.get("source"),
                "paper_id": paper_id,
                "paper_title": paper.get("title"),
                "link": paper.get("link"),
                "arxiv_id": arxiv_id,
                "similarity": item.get("similarity"),
            }
        )
    return normalized


def search_leansearch(
    query: str,
    n_results: int = 5,
    endpoint: str = "https://leansearch.net/thm/search",
    timeout_seconds: int = 30,
) -> List[Dict[str, Any]]:
    """leansearch 后端（预留，可配置切换）。"""
    if not query.strip():
        raise ValueError("query 不能为空")
    payload = {
        "query": query,
        "task": (
            "Given a math statement, retrieve useful references, such as "
            "theorems, lemmas, and definitions, that are useful for solving "
            "the given problem."
        ),
        "num_results": max(1, int(n_results)),
    }
    resp = requests.post(endpoint, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "name": item.get("title"),
                "body": item.get("theorem"),
                "slogan": item.get("theorem"),
                "source": "arXiv",
                "paper_id": item.get("arxiv_id"),
                "paper_title": item.get("title"),
                "link": None,
                "arxiv_id": item.get("arxiv_id"),
                "similarity": None,
            }
        )
    return normalized


def search(
    query: str,
    n_results: int = 5,
    backend: str = "theoremsearch",
    theoremsearch: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 120,
) -> List[Dict[str, Any]]:
    """按配置的后端搜索。"""
    if backend == "leansearch":
        return search_leansearch(query, n_results=n_results, timeout_seconds=timeout_seconds)
    cfg = theoremsearch or {}
    return search_theoremsearch(
        query,
        n_results=n_results,
        api_base=cfg.get("api_base", "https://api.theoremsearch.com"),
        timeout_seconds=timeout_seconds,
    )


def _strip_version(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def _extract_tex_tarball(content: bytes, tex_dest: Path) -> None:
    parts: List[str] = []
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as tar:
        members = [
            m for m in tar.getmembers() if m.isfile() and m.name.lower().endswith(".tex")
        ]
        if not members:
            raise RuntimeError("tar.gz 源码中未找到 .tex 文件")
        for member in members:
            f = tar.extractfile(member)
            if f is None:
                continue
            text = f.read().decode("utf-8", errors="replace")
            parts.append(f"\n% ===== file: {member.name} =====\n")
            parts.append(text)
    tex_dest.write_text("\n".join(parts), encoding="utf-8")


def download_arxiv(
    arxiv_id: str,
    dest_dir: Path,
    fmt: str = "tex",
    timeout_seconds: int = 60,
    ratelimit_seconds: float = 2.0,
) -> Dict[str, Any]:
    """下载 arXiv 论文。

    fmt="tex"：下载 e-print 源码；tar.gz 解压拼接 .tex；单 .tex 直接保存；
               若返回 PDF（PDF-only 投稿）则保存为 .pdf（kind="pdf"）。
    fmt="pdf"：直接下载 PDF。
    已存在时幂等返回。返回 {"kind": "tex"|"pdf", "path": str}。
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = _strip_version(arxiv_id)
    tex_dest = dest_dir / f"{base}.tex"
    pdf_dest = dest_dir / f"{base}.pdf"
    if fmt == "tex" and tex_dest.exists():
        return {"kind": "tex", "path": str(tex_dest)}
    if fmt == "pdf" and pdf_dest.exists():
        return {"kind": "pdf", "path": str(pdf_dest)}

    if ratelimit_seconds and ratelimit_seconds > 0:
        time.sleep(ratelimit_seconds)

    if fmt == "tex":
        resp = requests.get(
            ARXIV_E_PRINT.format(id=arxiv_id),
            timeout=timeout_seconds,
            allow_redirects=True,
        )
        resp.raise_for_status()
        ctype = (resp.headers.get("content-type") or "").lower()
        if "gzip" in ctype or "x-tar" in ctype or "octet-stream" in ctype or resp.content[:2] == b"\x1f\x8b":
            _extract_tex_tarball(resp.content, tex_dest)
            return {"kind": "tex", "path": str(tex_dest)}
        if "pdf" in ctype:
            pdf_dest.write_bytes(resp.content)
            return {"kind": "pdf", "path": str(pdf_dest)}
        # 其余按纯文本 .tex 处理
        tex_dest.write_bytes(resp.content)
        return {"kind": "tex", "path": str(tex_dest)}

    resp = requests.get(ARXIV_PDF.format(id=arxiv_id), timeout=timeout_seconds, allow_redirects=True)
    resp.raise_for_status()
    pdf_dest.write_bytes(resp.content)
    return {"kind": "pdf", "path": str(pdf_dest)}


def download_if_arxiv(result: Dict[str, Any], dest_dir: Path, fmt: str = "tex",
                      timeout_seconds: int = 60, ratelimit_seconds: float = 2.0) -> Optional[Dict[str, Any]]:
    """若搜索结果来自 arXiv 且有 arxiv_id，则下载；否则返回 None（跳过）。"""
    if result.get("source") != "arXiv" or not result.get("arxiv_id"):
        return None
    try:
        return download_arxiv(
            result["arxiv_id"],
            dest_dir,
            fmt=fmt,
            timeout_seconds=timeout_seconds,
            ratelimit_seconds=ratelimit_seconds,
        )
    except Exception as exc:  # 下载失败跳过，不强求全文
        print(f"[search] 下载 arXiv {result['arxiv_id']} 失败: {exc}")
        return None
