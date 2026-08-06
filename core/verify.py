"""自然语言验证：独立 codex 会话验证 blueprint.md，输出结构化判定。

沿用 Rethlas 设定：
- 验证与生成共用同一模型与推理强度；
- 输出 results/<run_id>/verification.json：{verification_report, verdict, repair_hints}；
- 对"证明缺失"误判做有限次重试。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import codex as codex_mod
from . import templates
from .config import Config
from .workspace import Workspace

PROOF_DELIMITER_START = "===BEGIN PROOF==="
PROOF_DELIMITER_END = "===END PROOF==="

# 验证器偶发把（非空）证明误判为"缺少证明文本"，保留窄关键词避免误伤真实数学漏洞。
MISSING_PROOF_KEYWORDS = (
    "proof text is missing",
    "proof text was not supplied",
    "no proof text was supplied",
    "no proof text was provided",
    "no proof text was found",
    "no proof text enclosed",
    "does not include any proof",
    "provides no markdown proof",
    "provides no proof text",
    "no markdown proof was supplied",
    "no markdown proof was provided",
    "no proof was supplied",
    "no proof was provided",
    "no proof body",
    "no theorem statement",
    "no statement was provided",
    "no statement was supplied",
    "statement is missing",
    "proof is missing from the prompt",
    "only a run_id",
    "proof cannot be verified",
    "missing_input",
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_id(statement: str) -> str:
    digest = hashlib.sha256(statement.encode("utf-8")).hexdigest()[:12]
    return f"verify_{_utc()}_{digest}"


def build_verify_prompt(run_id: str, statement: str, proof: str) -> str:
    return (
        f"Run_id: {run_id}\n"
        f"Statement: {statement}\n"
        f"Proof:\n"
        f"{PROOF_DELIMITER_START}\n"
        f"{proof}\n"
        f"{PROOF_DELIMITER_END}\n\n"
        "Use AGENTS.md to verify the above proof for the statement. "
        "The proof to verify is the complete text between the markers "
        f"{PROOF_DELIMITER_START} and {PROOF_DELIMITER_END}."
    )


def looks_like_missing_proof(payload: Dict[str, Any]) -> bool:
    """检测验证器把（非空）证明误判为缺失的假阴性，以便透明重试。"""
    verdict = str(payload.get("verdict", "")).lower()
    report = payload.get("verification_report")
    if not isinstance(report, dict):
        return False
    texts = [verdict, str(report.get("summary", "")).lower()]
    errors = report.get("critical_errors", [])
    if isinstance(errors, list):
        for err in errors:
            if isinstance(err, dict):
                texts.append(str(err.get("location", "")).lower())
                texts.append(str(err.get("issue", "")).lower())
    combined = " ".join(texts)
    return any(keyword in combined for keyword in MISSING_PROOF_KEYWORDS)


def _read_verification(vdir: Path, run_id: str) -> Optional[Dict[str, Any]]:
    for name in ("verification.json", "verificationt.json"):
        path = vdir / "results" / run_id / name
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None
    return None


def _setup_verify_workspace(vdir: Path) -> None:
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "AGENTS.md").write_text(templates.render_verification_agents(), encoding="utf-8")


def verify_proof(
    ws: Workspace,
    statement: str,
    proof: str,
    config: Config,
) -> Dict[str, Any]:
    """运行验证会话，返回 {verdict, verification_report, repair_hints, ...}。"""
    run_id = _run_id(statement)
    vdir = ws.verify_runs_dir / run_id
    _setup_verify_workspace(vdir)

    prompt = build_verify_prompt(run_id, statement, proof)
    log_path = ws.logs_dir / f"verify_{run_id}.md"
    max_attempts = max(1, int(config.get("verify", {}).get("max_attempts", 3) or 3))
    codex_cfg = config.get("codex", {})

    attempts = 0
    while True:
        attempts += 1
        res = codex_mod.run_codex(
            cwd=vdir,
            model=config.get("model", "gpt-5.6-terra"),
            reasoning_effort=config.get("reasoning_effort", "xhigh"),
            prompt=prompt,
            log_path=log_path,
            timeout_seconds=int(codex_cfg.get("timeout_seconds", 0) or 0),
            bin_name=codex_cfg.get("bin", "codex"),
        )
        if res.returncode != 0:
            raise RuntimeError(f"验证 codex 退出码 {res.returncode}；日志: {log_path}")
        payload = _read_verification(vdir, run_id)
        if payload is None:
            raise RuntimeError(
                f"未找到验证输出 {vdir}/results/{run_id}/verification.json；日志: {log_path}"
            )
        if attempts >= max_attempts or not looks_like_missing_proof(payload):
            return payload
