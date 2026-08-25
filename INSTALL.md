# Installing the rethlas-derive Skill (Agent / User Guide)

> **The repo root is the skill directory itself.** `SKILL.md` sits alongside `cli.py`, `core/`, `config.yaml`, `templates/`, and `.env.example`.
> Install = clone / extract this repo into the target agent's skills directory → install dependencies → copy `.env.example` to `.env` and fill in your keys.
> No file copying or path editing is needed — `core/config.py` and `core/env.py` resolve config relative to `__file__`, so the layout just needs to stay intact.

## 1. Place the repo in the skills directory

**Project-level** (committed to the repo; collaborators get the skill when they clone):

```powershell
# Run from the target repo root
git clone https://github.com/FDscend/rethlas-derive.git .github/skills/rethlas-derive
```

**User-level** (available globally):

```powershell
git clone https://github.com/FDscend/rethlas-derive.git ~/.codex/skills/rethlas-derive    # OpenAI Codex CLI
git clone https://github.com/FDscend/rethlas-derive.git ~/.copilot/skills/rethlas-derive  # GitHub Copilot
```

> - When downloading a zip, the extracted folder is usually named `rethlas-derive-main` — rename it to `rethlas-derive` before placing it in the skills directory.
> - Directory conventions: project-level Copilot reads `.github/skills/` (also `.claude/skills/`, `.agents/skills/`); Codex reads `.codex/skills/`.
>   User-level Copilot reads `~/.copilot/skills/`; Codex reads `~/.codex/skills/`.
> - Agents scan the skills directory at startup. After adding or modifying a skill, restart the session or reload for changes to take effect.
> - The frontmatter only needs `name` and `description` (agentskills.io generic format) — no platform-specific tweaks required.

## 2. Install dependencies (inside skills/rethlas-derive)

```powershell
npm install -g @openai/codex          # 1) codex (npm global)
python -m venv .venv                  # 2) Python venv + dependencies
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux:

```bash
npm install -g @openai/codex
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> After installing codex, **authenticate**: `codex login` (ChatGPT account) or set the API key via an environment variable (`OPENAI_API_KEY`).
> On Windows, npm installs codex as a `.cmd` shim — `cli.py` handles this automatically (`shutil.which` + `cmd /c`).

## 3. Copy `.env.example` to `.env` and fill in your keys

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Open `.env` and fill in the keys you need (`.env` is gitignored and won't be committed; leaving values empty is fine — the tool degrades gracefully):

| Variable         | Required | Description                                                                               |
| ---------------- | -------- | ----------------------------------------------------------------------------------------- |
| `MINERU_TOKEN`   | Optional | Token for MinerU full-mode + VLM; falls back to offline PyMuPDF PDF extraction if omitted |
| `TAVILY_API_KEY` | Optional | Tavily web search key; falls back to codex built-in web search if omitted                 |
| `DERIVE_CONFIG`  | Optional | Path to `config.yaml`; defaults to the one in the tool root directory                     |

## 4. Verify the installation

```powershell
.\.venv\Scripts\python tests\smoke.py --offline    # Smoke test (skips network)
.\.venv\Scripts\python cli.py list                 # Should print a JSON proposition list
```

Optional: run a minimal derivation (invokes codex, takes a while):

```powershell
.\.venv\Scripts\python cli.py derive --statement "1+1=2" --max-iterations 1
```

If all of the above pass, the installation is complete and the skill is ready for agent discovery and invocation.

## Troubleshooting

| Symptom                            | Fix                                                                                                                                       |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| codex not found / invocation fails | Verify `npm install -g @openai/codex` succeeded and that your `PATH` includes the npm global bin (on Windows the `.cmd` shim is expected) |
| "Failed to read config.yaml"       | Confirm the relative layout of `core/`, `config.yaml`, and `SKILL.md` is intact                                                           |
| Missing `.env` / cannot read keys  | Copy `.env.example` to `.env` (see step 3) and fill in the corresponding variables                                                        |
| Agent cannot find the skill        | Confirm `SKILL.md` is in the platform-required skills directory and that the filename / frontmatter is not corrupted                      |
