# 安装 rethlas-derive skill（面向 agent / 用户的安装说明）

> 本仓库**根目录就是 skill 目录**：`SKILL.md` 与 `cli.py`、`core/`、`config.yaml`、`templates/`、`.env.example` 同级。
> 安装 = 把本仓库 clone / 解压到目标 agent 的 skills 目录 → 装依赖 → 复制 `.env.example` 为 `.env` 并填写。
> 不需要复制文件、不需要改路径：`core/config.py` / `core/env.py` 按 `__file__` 相对定位配置，结构不变即可用。

## 1. 把仓库放到 skills 目录

项目级（随仓库提交，协作者 clone 主仓库时即自带 skill）：

```powershell
# 在目标仓库根目录执行
git clone https://github.com/FDscend/rethlas-derive.git .github/skills/rethlas-derive
```

个人级（全局可用）：

```powershell
git clone https://github.com/FDscend/rethlas-derive.git ~/.codex/skills/rethlas-derive    # OpenAI Codex CLI
git clone https://github.com/FDscend/rethlas-derive.git ~/.copilot/skills/rethlas-derive  # GitHub Copilot
```

> - 下载 zip 时，解压出的目录名通常是 `rethlas-derive-main`，请重命名为 `rethlas-derive` 再放入 skills 目录。
> - 目录约定：项目级 Copilot 认 `.github/skills/`（也认 `.claude/skills/`、`.agents/skills/`），Codex 认 `.codex/skills/`；
>   个人级 Copilot 认 `~/.copilot/skills/`，Codex 认 `~/.codex/skills/`。
> - agent 启动时扫描 skills 目录；新增/修改 skill 后需重启会话或重新加载才能生效。
> - frontmatter 仅含 `name` 与 `description`（agentskills.io 通用格式），无需按平台改动。

## 2. 安装依赖（在 skills/rethlas-derive 目录内）

```powershell
npm install -g @openai/codex          # 1) codex（npm 全局）
python -m venv .venv                  # 2) Python 虚拟环境 + 依赖
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux：

```bash
npm install -g @openai/codex
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> codex 安装后需**认证**：`codex login`（ChatGPT 账号）或配置 API key（如环境变量 `OPENAI_API_KEY`）。
> Windows 上 npm 安装的 codex 是 `.cmd` shim，`cli.py` 会自动兼容（`shutil.which` + `cmd /c`）。

## 3. 复制 `.env.example` 为 `.env` 并填写

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

打开 `.env` 按需填写密钥（`.env` 已被 gitignore，不会提交；留空也能跑，会自动降级）：

| 变量             | 是否必填 | 说明                                                            |
| ---------------- | -------- | --------------------------------------------------------------- |
| `MINERU_TOKEN`   | 可选     | MinerU 完整模式 + VLM 的 token；无则降级到离线 PyMuPDF PDF 提取 |
| `TAVILY_API_KEY` | 可选     | Tavily 网络搜索 key；无则降级到 codex 内置 web search           |
| `DERIVE_CONFIG`  | 可选     | 指定 config.yaml 路径；默认自动查找工具根目录的 config.yaml     |

## 4. 验证安装

```powershell
.\.venv\Scripts\python tests\smoke.py --offline    # 冒烟测试（跳过网络）
.\.venv\Scripts\python cli.py list                 # 应输出 JSON 命题列表
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
| 报"读取 config.yaml 失败"    | 确认 `core/`、`config.yaml` 的相对位置未被破坏（与 `SKILL.md` 同级）                               |
| 提示缺少 `.env` / 读不到 key | 确认已复制 `.env.example` 为 `.env`（见步骤 3），密钥填在对应变量下                                |
| agent 找不到 skill           | 确认 `SKILL.md` 已放到平台要求的 skills 目录，且文件名/frontmatter 未损坏                          |
