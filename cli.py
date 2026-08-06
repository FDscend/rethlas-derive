#!/usr/bin/env python
"""命题推导工具 CLI。

用法示例：
  python cli.py derive --statement "..." [--ref a.pdf --ref b.tex] [--max-iterations 8]
  python cli.py derive --statement-file s.md --workdir ./workspace
  python cli.py resume <id> --extra-iterations 2 --add-ref extra.pdf
  python cli.py status <id>
  python cli.py list
  python cli.py clean <id> --target failed [--keep-checkpoint]

stdout 统一输出 JSON。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import derive as derive_mod
from core.config import load_config
from core.workspace import Workspace


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _load_statement(args: argparse.Namespace) -> str:
    if args.statement and args.statement_file:
        raise SystemExit("--statement 与 --statement-file 二选一")
    if args.statement_file:
        path = Path(args.statement_file)
        if not path.exists():
            raise SystemExit(f"命题文件不存在: {path}")
        return path.read_text(encoding="utf-8")
    if args.statement:
        return args.statement
    raise SystemExit("必须提供 --statement 或 --statement-file")


def _build_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    if getattr(args, "max_iterations", None) is not None:
        overrides["max_iterations"] = args.max_iterations
    if getattr(args, "workdir", None):
        overrides["workdir"] = args.workdir
    if getattr(args, "download_format", None):
        overrides.setdefault("search", {})["download"] = {"format": args.download_format}
    if getattr(args, "search_backend", None):
        overrides.setdefault("search", {})["backend"] = args.search_backend
    if getattr(args, "pdf_backend", None):
        overrides["pdf"] = {"backend": args.pdf_backend}
    return overrides


def cmd_derive(args: argparse.Namespace) -> None:
    statement = _load_statement(args)
    config = load_config(args.config).apply_overrides(**_build_overrides(args))
    result = derive_mod.derive(
        statement,
        refs=args.ref or None,
        config=config,
        cli_workdir=args.workdir,
    )
    _print_json(result)


def cmd_resume(args: argparse.Namespace) -> None:
    config = load_config(args.config).apply_overrides(**_build_overrides(args))
    result = derive_mod.derive(
        statement="",
        refs=None,
        config=config,
        cli_workdir=args.workdir,
        resume_id=args.id,
        extra_iterations=args.extra_iterations,
        add_refs=args.add_ref or None,
    )
    _print_json(result)


def cmd_status(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    workdir = config.resolve_workdir(args.workdir)
    ws = Workspace(workdir, args.id)
    cp = ws.load_checkpoint()
    _print_json(
        {
            "id": args.id,
            "workdir": str(workdir),
            "exists": ws.exists(),
            "checkpoint": cp.to_dict() if cp else None,
            "blueprint_exists": ws.blueprint_path.exists(),
            "verified_exists": ws.blueprint_verified_path.exists(),
        }
    )


def cmd_list(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    workdir = config.resolve_workdir(args.workdir)
    items: List[Dict[str, Any]] = []
    if workdir.exists():
        for d in sorted(workdir.iterdir()):
            if not d.is_dir() or not (d / "checkpoint.json").exists():
                continue
            ws = Workspace(workdir, d.name)
            cp = ws.load_checkpoint()
            items.append(
                {
                    "id": d.name,
                    "status": cp.status if cp else "unknown",
                    "iterations_used": cp.iterations_used if cp else 0,
                    "verified": ws.blueprint_verified_path.exists(),
                    "updated_at": cp.updated_at if cp else None,
                }
            )
    _print_json({"workdir": str(workdir), "items": items})


def cmd_clean(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    workdir = config.resolve_workdir(args.workdir)
    ws = Workspace(workdir, args.id)
    if not ws.exists():
        raise SystemExit(f"命题 {args.id} 不存在于 {workdir}")
    _print_json(ws.cleanup(args.target, keep_checkpoint=args.keep_checkpoint))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="derive", description="命题推导工具")
    parser.add_argument("--config", default=None, help="config.yaml 路径（默认找工具根目录 config.yaml）")
    parser.add_argument("--workdir", default=None, help="覆盖配置文件的工作目录")
    sub = parser.add_subparsers(dest="command", required=True)

    SUPPRESS = argparse.SUPPRESS

    def add_common(p: argparse.ArgumentParser) -> None:
        # SUPPRESS：子命令未显式给时，不覆盖主 parser 上的全局值
        p.add_argument("--config", default=SUPPRESS, help=argparse.SUPPRESS)
        p.add_argument("--workdir", default=SUPPRESS, help=argparse.SUPPRESS)

    p_derive = sub.add_parser("derive", help="对完整命题表述进行推导")
    add_common(p_derive)
    p_derive.add_argument("--statement", default=None, help="完整命题表述（支持 LaTeX）")
    p_derive.add_argument("--statement-file", default=None, help="命题表述文件路径")
    p_derive.add_argument("--ref", action="append", default=[], help="参考文件路径（pdf/tex/md，可多次）")
    p_derive.add_argument("--max-iterations", type=int, default=None)
    p_derive.add_argument("--download-format", choices=["tex", "pdf"], default=None)
    p_derive.add_argument("--search-backend", choices=["theoremsearch", "leansearch"], default=None)
    p_derive.add_argument("--pdf-backend", choices=["mineru", "pymupdf"], default=None)
    p_derive.set_defaults(func=cmd_derive)

    p_resume = sub.add_parser("resume", help="按 id + checkpoint 续推（追加迭代次数/参考资料）")
    add_common(p_resume)
    p_resume.add_argument("id", help="命题 id（derive 返回的 id）")
    p_resume.add_argument("--extra-iterations", type=int, default=1, help="追加迭代次数")
    p_resume.add_argument("--add-ref", action="append", default=[], help="追加参考文件（可多次）")
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser("status", help="查看命题推导状态")
    add_common(p_status)
    p_status.add_argument("id")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="列出工作目录下所有命题")
    add_common(p_list)
    p_list.set_defaults(func=cmd_list)

    p_clean = sub.add_parser("clean", help="清理推导产物")
    add_common(p_clean)
    p_clean.add_argument("id")
    p_clean.add_argument("--target", choices=["intermediate", "failed", "success", "all"], required=True)
    p_clean.add_argument("--keep-checkpoint", action="store_true", help="清理 failed 时保留 checkpoint 以便续推")
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
