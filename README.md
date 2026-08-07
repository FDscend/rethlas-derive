# rethlas-derive（命题推导工具）

把「命题 → 搜索 → 生成推导 → 验证 → 迭代」流程（受 [Rethlas](https://github.com/FDscend/Rethlas-Windows) 启发）封装为独立 CLI（封装成 skill）：
主 agent 直接传入完整命题表述与参考资料，工具自动搜索、推导、验证、迭代，返回推导结果（JSON + md 路径）。

## 安装

### 1. 安装 codex（npm，全局）

```bash
npm install -g @openai/codex
```

> codex 安装后需完成**认证**才能调用：`codex login` 登录 ChatGPT 账号，或配置 API key（如环境变量 `OPENAI_API_KEY`）。
> Windows 上 npm 安装的 codex 是 `.cmd` shim，工具会自动兼容（`shutil.which` 解析 + `cmd /c` 调用）。

### 2. 创建虚拟环境并安装依赖

Windows（PowerShell，可执行文件在 `.venv\Scripts\`）：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux（bash，可执行文件在 `.venv/bin/`）：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> 后文命令统一用 `python cli.py ...`，默认已激活 venv（或直接使用上面的 `python` 路径调用）。

## 用法

```powershell
# 推导
python cli.py derive --statement "<完整命题表述>" [--ref 论文.pdf ...] [--max-iterations 8]
python cli.py derive --statement-file s.md --workdir ./workspace

# 失败后判断 & 续推（追加迭代次数 / 追加参考资料）
python cli.py resume <id> --extra-iterations 2
python cli.py resume <id> --extra-iterations 2 --add-ref 论文.pdf

# 状态与清理
python cli.py list
python cli.py status <id>
python cli.py clean <id> --target intermediate|failed|success|all [--keep-checkpoint]
```

stdout 统一输出 JSON。完整说明见根目录 `SKILL.md`。

## 配置

单文件 `config.yaml`（默认模型 / 推理强度 / 迭代次数 / 工作目录 / 搜索与 PDF 后端等）。
所有默认值均可被 CLI 参数覆盖（`--max-iterations`、`--workdir`、`--download-format`、
`--search-backend`、`--pdf-backend`）。

## 结构

```
cli.py                 # CLI 入口
config.yaml            # 配置（默认模型 / 迭代次数 / 搜索后端等，可被 CLI 覆盖）
.env.example           # 环境变量模板；安装后复制为 .env 并填写（见 INSTALL.md）
.gitignore             # 忽略 .env / .venv / workspace 等
core/                  # 核心库
  config.py            # 配置加载 + CLI 覆盖
  workspace.py         # 命题 id / checkpoint / 目录
  codex.py             # codex exec 封装（Windows 兼容 + stdin 传提示词）
  search.py            # TheoremSearch + arXiv TeX 源下载
  pdf.py               # PDF 提取（MinerU -> .env python -> PyMuPDF）
  verify.py            # 自然语言验证（独立 codex 会话）
  derive.py            # 推导循环编排（纯文件方式，不依赖 codex MCP）
  agent_mcp.py         # 可选：内部 MCP server（memory/search/download，备用/未来 MCP 包装用）
templates/             # AGENTS 模板（生成 / 验证）
SKILL.md               # 主 agent 使用的 skill（根目录即 skill 目录，clone 即用，见 INSTALL.md）
tests/                 # 冒烟测试 + 推导循环逻辑测试
```

## 测试

Windows（PowerShell）：

```powershell
.\.venv\Scripts\python tests\smoke.py            # 冒烟测试（含网络）
.\.venv\Scripts\python tests\smoke.py --offline  # 跳过网络
.\.venv\Scripts\python tests\derive_loop_test.py # 推导循环逻辑（fake codex）
```

macOS / Linux（bash）：

```bash
.venv/bin/python tests/smoke.py            # 冒烟测试（含网络）
.venv/bin/python tests/smoke.py --offline  # 跳过网络
.venv/bin/python tests/derive_loop_test.py # 推导循环逻辑（fake codex）
```
