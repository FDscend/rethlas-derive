"""PDF 提取（主 agent 传入的本地 PDF，以及 arXiv TeX 下载失败/PDF-only 投稿的降级）。

默认 MinerU（完整转换模式 + VLM，忽略快速模式），按以下顺序降级：
1. npm CLI：mineru-open-api extract（本地 npm 已认证 token）——默认
2. python 实现：CLI 不可用/失败时，检查 .env 中的 MINERU_TOKEN，用 python 客户端调用
3. 离线降级：两者都没有时，降级到 PyMuPDF（纯 python 库，无外部二进制依赖）

可通过配置强制离线（pdf.backend=pymupdf）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

MINERU_API_BASE = "https://mineru.net"


def _find_mineru_bin() -> Optional[str]:
    return shutil.which("mineru-open-api")


def _load_env_token(env_path: Optional[Path] = None) -> Optional[str]:
    env_token = os.environ.get("MINERU_TOKEN")
    if env_token:
        return env_token.strip()
    candidates: List[Path] = []
    if env_path:
        candidates.append(env_path)
    candidates += [Path.cwd() / ".env", Path(".env")]
    for cand in candidates:
        if cand and cand.exists():
            try:
                for line in cand.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line.startswith("MINERU_TOKEN") and "=" in line:
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
            except OSError:
                continue
    return None


def _find_md(out_dir: Path) -> Optional[Path]:
    for p in sorted(out_dir.rglob("*.md")):
        return p
    return None


def _run_mineru_cli(pdf_path: Path, out_dir: Path, config: Dict[str, Any]) -> Optional[Path]:
    bin_ = _find_mineru_bin()
    if not bin_:
        raise RuntimeError("mineru-open-api 未安装")
    cmd = [bin_, "extract", str(pdf_path), "-o", str(out_dir)]
    model = config.get("model")
    if model:
        cmd += ["--model", model]
    timeout = int(config.get("timeout_seconds", 900))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"mineru-open-api extract 失败: {(proc.stderr or '')[-2000:]}")
    md = _find_md(out_dir)
    return md


def _mineru_python_client(pdf_path: Path, out_dir: Path, token: str, config: Dict[str, Any]) -> Optional[Path]:
    """python 实现（参考 mineru API 文档）。端点/字段以 https://mineru.net/apiManage/docs 为准，
    失败时返回 None 由上层降级。"""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with pdf_path.open("rb") as fh:
            resp = requests.post(
                f"{MINERU_API_BASE}/api/v4/extract/task",
                headers=headers,
                files={"file": (pdf_path.name, fh, "application/pdf")},
                timeout=120,
            )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        batch_id = data.get("batch_id")
        extract_id = data.get("extract_id")
        if not batch_id or not extract_id:
            return None
        deadline = time.time() + int(config.get("timeout_seconds", 900))
        while time.time() < deadline:
            time.sleep(5)
            st = requests.get(
                f"{MINERU_API_BASE}/api/v4/extract/task/{batch_id}/{extract_id}",
                headers=headers,
                timeout=60,
            )
            st.raise_for_status()
            state = st.json().get("data", {}).get("state") or st.json().get("data", {}).get("status")
            if state in ("done", "finished", "success"):
                break
            if state in ("failed", "cancelled", "error"):
                return None
        else:
            return None
        result = requests.get(
            f"{MINERU_API_BASE}/api/v4/extract/result/{batch_id}/{extract_id}",
            headers=headers,
            timeout=120,
        )
        result.raise_for_status()
        out_zip = out_dir / "mineru_result.zip"
        out_zip.write_bytes(result.content)
        with zipfile.ZipFile(out_zip) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".md")]
            if not names:
                return None
            zf.extract(names[0], out_dir)
            return out_dir / names[0]
    except Exception:
        return None


def extract_pdf_pymupdf(pdf_path: Path, out_md: Path, layout: bool = True) -> Path:
    """PyMuPDF 离线提取。"""
    import fitz  # PyMuPDF

    out_md.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    parts: List[str] = []
    for page in doc:
        text = page.get_text("text" if layout else "blocks")
        parts.append(f"\n<!-- page {page.number + 1} -->\n")
        parts.append(text)
    doc.close()
    out_md.write_text("\n".join(parts), encoding="utf-8")
    return out_md


def extract_pdf(
    pdf_path: Path,
    out_md: Path,
    pdf_config: Dict[str, Any],
    env_path: Optional[Path] = None,
) -> Path:
    """按配置的 PDF 后端提取 PDF 到 out_md，返回提取出的 md 路径。"""
    backend = pdf_config.get("backend", "mineru")
    if backend == "pymupdf":
        return extract_pdf_pymupdf(pdf_path, out_md, layout=bool(pdf_config.get("pymupdf", {}).get("layout", True)))

    mineru_cfg = pdf_config.get("mineru", {})
    out_dir = out_md.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) npm CLI
    if mineru_cfg.get("auth", "npm-cli") == "npm-cli":
        try:
            md = _run_mineru_cli(pdf_path, out_dir, mineru_cfg)
            if md:
                return md
        except Exception:
            pass
    # 2) python 实现（.env MINERU_TOKEN）
    token = _load_env_token(env_path)
    if token:
        md = _mineru_python_client(pdf_path, out_dir, token, mineru_cfg)
        if md:
            return md
    # 3) 离线降级
    return extract_pdf_pymupdf(pdf_path, out_md, layout=bool(pdf_config.get("pymupdf", {}).get("layout", True)))
