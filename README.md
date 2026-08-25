| English | [简体中文](./README.zh.md) |
| ------- | -------------------------- |

# rethlas-derive — Proposition Derivation Tool

A standalone CLI (packaged as a skill) that orchestrates the "proposition → search → derive → verify → iterate" pipeline (inspired by [Rethlas](https://github.com/FDscend/Rethlas-Windows)):
the host agent passes in a full proposition statement and reference materials, and the tool automatically searches, derives, verifies, and iterates, returning the derivation result (JSON + md path).

## Installation

### 1. Install codex (npm, globally)

```bash
npm install -g @openai/codex
```

> After installation you must **authenticate** before codex can be invoked: run `codex login` to sign in with a ChatGPT account, or [configure an API key](https://fdscend.github.io/obsidian_tutorial/section12/02_codex%E5%9C%A8vscode%E4%B8%AD%E7%9A%84%E5%AE%89%E8%A3%85%E4%B8%8E%E9%85%8D%E7%BD%AE#%E6%96%B9%E5%BC%8F-bapi-key%E5%85%8D%E7%BD%91%E9%A1%B5%E7%99%BB%E5%BD%95).
>
> On Windows, npm installs codex as a `.cmd` shim — the tool handles this automatically (`shutil.which` + `cmd /c`).

### 2. Create a virtual environment and install dependencies

Windows (PowerShell, executables in `.venv\Scripts\`):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux (bash, executables in `.venv/bin/`):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> All subsequent commands assume `python cli.py ...` with an activated venv (or use the full path above).

## Usage

```powershell
# Derive
python cli.py derive --statement "<full proposition>" [--ref paper.pdf ...] [--max-iterations 8]
python cli.py derive --statement-file s.md --workdir ./workspace

# Inspect failure & resume (add iterations / add references)
python cli.py resume <id> --extra-iterations 2
python cli.py resume <id> --extra-iterations 2 --add-ref paper.pdf

# Status & cleanup
python cli.py list
python cli.py status <id>
python cli.py clean <id> --target intermediate|failed|success|all [--keep-checkpoint]
```

stdout outputs JSON in all cases. See `SKILL.md` in the repo root for full details.

## Configuration

A single `config.yaml` file controls defaults (model, reasoning intensity, iteration count, working directory, search and PDF backends, etc.).
Every default can be overridden by CLI flags (`--max-iterations`, `--workdir`, `--download-format`,
`--search-backend`, `--pdf-backend`).

## Project Structure

```
cli.py                 # CLI entry point
config.yaml            # Configuration (defaults for model / iterations / search backend; CLI-overridable)
.env.example           # Environment variable template; copy to .env and fill in after install (see INSTALL.md)
.gitignore             # Ignores .env / .venv / workspace / etc.
core/                  # Core library
  config.py            # Config loading + CLI overrides
  workspace.py         # Proposition id / checkpoint / directory management
  codex.py             # Codex exec wrapper (Windows-compatible + stdin prompts)
  search.py            # TheoremSearch + arXiv TeX source download
  pdf.py               # PDF extraction (MinerU → .env python → PyMuPDF)
  verify.py            # Natural-language verification (standalone codex session)
  derive.py            # Derivation loop orchestration (pure-file approach, no codex MCP dependency)
  agent_mcp.py         # Optional: internal MCP server (memory/search/download; reserved / future MCP wrapper)
templates/             # AGENTS templates (generation / verification)
SKILL.md               # Skill consumed by the host agent (repo root = skill dir; clone and go; see INSTALL.md)
tests/                 # Smoke tests + derivation loop logic tests
```

## Testing

Windows (PowerShell):

```powershell
.\.venv\Scripts\python tests\smoke.py            # Smoke test (with network)
.\.venv\Scripts\python tests\smoke.py --offline  # Skip network
.\.venv\Scripts\python tests\derive_loop_test.py # Derivation loop logic (fake codex)
```

macOS / Linux (bash):

```bash
.venv/bin/python tests/smoke.py            # Smoke test (with network)
.venv/bin/python tests/smoke.py --offline  # Skip network
.venv/bin/python tests/derive_loop_test.py # Derivation loop logic (fake codex)
```
