"""codex exec 封装。

平台兼容（参考 Rethlas 验证端 server.py）：
- Windows npm 安装的 codex 是 .cmd/.ps1 shim，裸名无法被 CreateProcess 拉起；
  用 shutil.which 解析（按 PATHEXT 找到 shim）。
- Windows 下二进制为 .cmd/.bat 时，经 cmd /c 调用；
  且提示词改经 stdin 传递（codex 用 `-` 从 stdin 读），避免 cmd/批处理 shim
  截断/转义多行提示词（含 LaTeX、引号、% 等特殊字符）。
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence


def resolve_codex_bin(configured: str) -> str:
    configured = (configured or "").strip()
    if configured and configured != "codex":
        return configured
    found = shutil.which("codex")
    return found or "codex"


def _prompt_via_stdin(binary: str) -> bool:
    # Windows 且经 cmd /c + .cmd/.bat shim 时，多行提示词作为参数会被截断
    return os.name == "nt" and binary.lower().endswith((".cmd", ".bat"))


def build_codex_command(
    binary: str,
    cwd: str,
    model: str,
    reasoning_effort: str,
    prompt: str,
    resume_session_id: Optional[str] = None,
    extra_configs: Optional[Sequence[str]] = None,
) -> List[str]:
    """构造 codex exec 命令（列表形式，避免 shell 转义问题）。"""
    if resume_session_id:
        args: List[str] = [
            binary, "exec", "resume", resume_session_id,
            "-m", model,
            "--config", f"model_reasoning_effort={reasoning_effort}",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
    else:
        args = [
            binary, "exec",
            "-C", cwd,
            "-m", model,
            "--config", f"model_reasoning_effort={reasoning_effort}",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
    for cfg in extra_configs or ():
        args += ["--config", cfg]
    if os.name == "nt" and args[0].lower().endswith((".cmd", ".bat")):
        args = ["cmd", "/c"] + args
    # 经 cmd/批处理 shim 时用 stdin 传提示词，避免截断；否则作为参数
    args.append("-" if _prompt_via_stdin(binary) else prompt)
    return args


SESSION_ID_RE = re.compile(r"session id[:= ]+(\S+)", re.IGNORECASE)


def extract_session_id(text: str) -> Optional[str]:
    match = SESSION_ID_RE.search(text)
    return match.group(1) if match else None


class CodexResult:
    def __init__(
        self,
        returncode: int,
        session_id: Optional[str],
        log_path: Optional[Path] = None,
    ):
        self.returncode = returncode
        self.session_id = session_id
        self.log_path = log_path


def run_codex(
    cwd: Path,
    model: str,
    reasoning_effort: str,
    prompt: str,
    log_path: Path,
    timeout_seconds: int = 0,
    bin_name: str = "codex",
    resume_session_id: Optional[str] = None,
    extra_configs: Optional[Sequence[str]] = None,
) -> CodexResult:
    """运行一次 codex exec，stdout/stderr 写入 log_path，返回退出码与会话 id。"""
    binary = resolve_codex_bin(bin_name)
    cmd = build_codex_command(
        binary=binary,
        cwd=str(cwd),
        model=model,
        reasoning_effort=reasoning_effort,
        prompt=prompt,
        resume_session_id=resume_session_id,
        extra_configs=extra_configs,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timeout = timeout_seconds or None
    via_stdin = _prompt_via_stdin(binary)
    input_text = prompt if via_stdin else None
    with log_path.open("w", encoding="utf-8") as fh:
        fh.write(f"command: {shlex.join(cmd)}\n\n")
        if via_stdin:
            fh.write("--- prompt (stdin) ---\n")
            fh.write(prompt)
            fh.write("\n--- end prompt ---\n\n")
        fh.flush()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(cwd),
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                input=input_text,
                encoding="utf-8",  # 关键：stdin 必须以 UTF-8 编码（Windows 默认区域编码会破坏非 ASCII 提示词）
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"codex exec 超时（{timeout} 秒）；日志: {log_path}"
            ) from exc
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    session_id = extract_session_id(log_text)
    return CodexResult(
        returncode=completed.returncode,
        session_id=session_id,
        log_path=log_path,
    )
