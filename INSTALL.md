# 在新仓库安装 rethlas-derive skill（面向 agent 的安装说明）

> 本文档是给**被要求"在新仓库安装 rethlas-derive skill"的 agent** 读的逐步说明。
> 请按顺序执行，每步都有验证；任何一步失败就停下来报告，不要跳过。

## 0. 先理解：这个 skill 不是单文件

`rethlas-derive` 是"**可执行工具 + skill 描述**"的组合，不是一段能独立生效的提示词：

```
skill/SKILL.md   # agent 加载的 skill 描述（frontmatter + 使用说明）
cli.py           # CLI 入口
core/            # 推导循环 / codex 封装 / 搜索 / PDF / 验证
config.yaml      # 配置（默认模型 / 迭代次数 / 搜索后端等）
templates/       # 生成 / 验证用的 AGENTS 模板（运行时按需生成）
```

所以"安装 skill"= **搬整个仓库 → 装依赖 → 把 `skill/SKILL.md` 注册到 agent 平台的 skills 目录**。
只拷 `SKILL.md` 是装不起来的。

## 1. 确定前置条件

- Python ≥ 3.10
- Node.js + npm（用于全局安装 codex）
- 目标 agent 平台的 skills 目录位置（Copilot：`.github/skills/` 或 `~/.copilot/skills/`；
  Codex：`.codex/skills/` 或 `~/.codex/skills/`，详见步骤 5）

## 2. 复制整个仓库

把仓库完整复制到目标机器，例如 `<INSTALL_DIR>/rethlas-derive/`。

**必须保持相对结构不变**（`cli.py`、`core/`、`config.yaml`、`skill/`、`templates/` 同级）。
`core/config.py` 按 `__file__` 向上两级找 `config.yaml`，改动相对结构会导致运行时找不到配置。

## 3. 安装依赖

```powershell
# 1) codex（npm 全局）
npm install -g @openai/codex

# 2) Python 虚拟环境 + 依赖（Windows / PowerShell）
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux：

```bash
npm install -g @openai/codex
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> Windows 上 npm 安装的 codex 是 `.cmd` shim，`cli.py` 会自动兼容（`shutil.which` + `cmd /c`）。

## 4. 检查 `skill/SKILL.md` 中的路径引用

当前版本的 `skill/SKILL.md` 使用通用描述（不写死本机路径），通常无需修改。
若拿到的是旧版本（先决条件一节写死了 `d:\code\WorkSpace_ai\Rethlas-MCP`），
请改为步骤 2 的实际安装路径 `<INSTALL_DIR>/rethlas-derive`。

## 5. 把 skill 注册到 agent 平台

**推荐做法**：把整个仓库内容复制到目标 agent 的 skills 目录（`SKILL.md`、`cli.py`、
`core/`、`config.yaml`、`templates/` 同目录）。这样 agent 可在同一目录直接执行
`python cli.py ...`，`core/config.py` 也能按相对位置找到 `config.yaml`。

安装后的目录例子：

### GitHub Copilot（项目级，随仓库提交）

```
<repo>/
└── .github/
    └── skills/
        └── rethlas-derive/
            ├── SKILL.md        # 来自 skill/SKILL.md
            ├── cli.py
            ├── core/
            ├── config.yaml
            └── templates/
```

### OpenAI Codex CLI（个人级，全局可用）

```
~/.codex/skills/
└── rethlas-derive/
    ├── SKILL.md
    ├── cli.py
    ├── core/
    ├── config.yaml
    └── templates/
```

目录约定：

- 项目级：Copilot 认 `.github/skills/`（也认 `.claude/skills/`、`.agents/skills/`）；
  Codex 认 `.codex/skills/`。
- 个人级：Copilot 认 `~/.copilot/skills/`；Codex 认 `~/.codex/skills/`。
- 各 agent 启动时扫描 skills 目录；新增/修改 skill 后需重启会话或重新加载。
- frontmatter 仅含 `name` 与 `description`（agentskills.io 通用格式），无需按平台改动。

## 6. 验证安装

```powershell
# 冒烟测试（跳过网络，验证依赖与核心逻辑）
.\.venv\Scripts\python tests\smoke.py --offline

# 确认 CLI 可用（应输出 JSON 命题列表）
.\.venv\Scripts\python cli.py list
```

可选：跑一条极简命题试推导（会调用 codex，耗时）：

```powershell
.\.venv\Scripts\python cli.py derive --statement "1+1=2" --max-iterations 1
```

全部通过即安装成功；skill 已可被 agent 发现并调用。

## 常见问题

| 现象                         | 处理                                                                                               |
| ---------------------------- | -------------------------------------------------------------------------------------------------- |
| codex 找不到 / 调用失败      | 确认 `npm install -g @openai/codex` 成功，PATH 含 npm 全局 bin（Windows 下为 `.cmd` shim，属正常） |
| 报"读取 config.yaml 失败"    | 确认 `core/`、`config.yaml` 的相对位置未被破坏（见步骤 2）                                         |
| 提示词里说工具目录路径不存在 | 步骤 4 未执行或替换错路径                                                                          |
| agent 找不到 skill           | 确认 `SKILL.md` 已放到平台要求的 skills 目录，且文件名/frontmatter 未损坏                          |
