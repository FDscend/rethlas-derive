"""命题 id / checkpoint / 目录管理。

id 由命题表述内容哈希生成（稳定）：同一命题多次运行 id 相同。
checkpoint 记录推导进度，每轮迭代后更新到 checkpoint.json。
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def proposition_id(statement: str) -> str:
    digest = hashlib.sha256(statement.encode("utf-8")).hexdigest()[:12]
    return f"prop_{digest}"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class Checkpoint:
    id: str
    statement: str
    created_at: str
    updated_at: str
    iterations_used: int = 0
    max_iterations: int = 0
    codex_session_id: Optional[str] = None
    status: str = "running"  # running | verified | failed
    last_verdict: Optional[str] = None  # correct | wrong
    refs: List[str] = field(default_factory=list)
    downloads: List[str] = field(default_factory=list)
    verify_report_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "iterations_used": self.iterations_used,
            "max_iterations": self.max_iterations,
            "codex_session_id": self.codex_session_id,
            "status": self.status,
            "last_verdict": self.last_verdict,
            "refs": self.refs,
            "downloads": self.downloads,
            "verify_report_path": self.verify_report_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(
            id=str(data.get("id", "")),
            statement=str(data.get("statement", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            iterations_used=int(data.get("iterations_used", 0) or 0),
            max_iterations=int(data.get("max_iterations", 0) or 0),
            codex_session_id=data.get("codex_session_id"),
            status=str(data.get("status", "running")),
            last_verdict=data.get("last_verdict"),
            refs=list(data.get("refs", []) or []),
            downloads=list(data.get("downloads", []) or []),
            verify_report_path=data.get("verify_report_path"),
        )


class Workspace:
    """单个命题的目录（<workdir>/<id>/），兼作 codex 生成会话的工作目录。"""

    def __init__(self, workdir: Path, problem_id: str):
        self.workdir_root = workdir
        self.root = workdir / problem_id
        self.problem_id = problem_id

    # ---- 路径 ----
    @property
    def statement_path(self) -> Path:
        return self.root / "statement.md"

    @property
    def agents_path(self) -> Path:
        return self.root / "AGENTS.md"

    @property
    def codex_config_dir(self) -> Path:
        return self.root / ".codex"

    @property
    def refs_dir(self) -> Path:
        return self.root / "refs"

    @property
    def refs_extracted_dir(self) -> Path:
        return self.refs_dir / ".extracted"

    @property
    def downloads_dir(self) -> Path:
        return self.root / "downloads"

    @property
    def search_summary_path(self) -> Path:
        return self.downloads_dir / "search_summary.md"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs" / "iter"

    @property
    def memory_dir(self) -> Path:
        return self.root / "memory"

    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    @property
    def blueprint_path(self) -> Path:
        return self.results_dir / "blueprint.md"

    @property
    def blueprint_verified_path(self) -> Path:
        return self.results_dir / "blueprint_verified.md"

    @property
    def checkpoint_path(self) -> Path:
        return self.root / "checkpoint.json"

    @property
    def verify_runs_dir(self) -> Path:
        return self.root / ".verify"

    def exists(self) -> bool:
        return self.root.exists()

    # ---- 初始化 ----
    def create_dirs(self) -> None:
        for d in (
            self.root,
            self.refs_dir,
            self.refs_extracted_dir,
            self.downloads_dir,
            self.logs_dir,
            self.memory_dir,
            self.results_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def write_statement(self, statement: str) -> None:
        self.statement_path.write_text(statement, encoding="utf-8")

    def load_statement(self) -> str:
        return self.statement_path.read_text(encoding="utf-8")

    def add_refs(self, ref_paths: List[str]) -> List[Path]:
        """把主 agent 传入的参考文件复制进 refs/（不记录原路径，避免移动后断链）。"""
        copied: List[Path] = []
        for raw in ref_paths:
            src = Path(raw)
            if not src.exists():
                raise FileNotFoundError(f"参考文件不存在: {raw}")
            if not src.is_file():
                raise ValueError(f"参考路径不是文件: {raw}")
            dest = self.refs_dir / src.name
            shutil.copy2(src, dest)
            copied.append(dest)
        return copied

    # ---- checkpoint ----
    def save_checkpoint(self, cp: Checkpoint) -> None:
        self.checkpoint_path.write_text(
            json.dumps(cp.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_checkpoint(self) -> Optional[Checkpoint]:
        if not self.checkpoint_path.exists():
            return None
        try:
            data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return Checkpoint.from_dict(data)

    # ---- 结果 ----
    def copy_verified(self, verify_report: Optional[Dict[str, Any]] = None) -> Path:
        """blueprint.md -> blueprint_verified.md（附上验证报告）。"""
        text = self.blueprint_path.read_text(encoding="utf-8")
        if verify_report:
            report_md = (
                "\n\n---\n\n## 验证报告\n\n```json\n"
                + json.dumps(verify_report, ensure_ascii=False, indent=2)
                + "\n```\n"
            )
            text += report_md
        self.blueprint_verified_path.write_text(text, encoding="utf-8")
        return self.blueprint_verified_path

    # ---- 清理 ----
    def cleanup(self, target: str, keep_checkpoint: bool = False) -> Dict[str, Any]:
        removed: List[str] = []

        def _rm(path: Path) -> None:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed.append(str(path))

        if target in ("intermediate", "all"):
            _rm(self.logs_dir)
            _rm(self.memory_dir)
            _rm(self.downloads_dir)
            _rm(self.verify_runs_dir)
        if target == "failed":
            if not keep_checkpoint:
                _rm(self.blueprint_path)
                _rm(self.checkpoint_path)
                _rm(self.verify_runs_dir)
            else:
                _rm(self.verify_runs_dir)
        if target in ("success", "all"):
            _rm(self.blueprint_verified_path)
        if target == "all":
            _rm(self.root)
        return {"id": self.problem_id, "target": target, "removed": removed}
