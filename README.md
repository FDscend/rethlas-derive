# 命题推导工具（Rethlas-MCP）

把 `ref\Rethlas` 的「命题 → 搜索 → 生成推导 → 验证 → 迭代」流程封装为独立 CLI（封装成 skill）：
主 agent 直接传入完整命题表述与参考资料，工具自动搜索、推导、验证、迭代，返回推导结果（JSON + md 路径）。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

前置：`codex` 可用（Windows 上 npm 安装的 `.cmd` shim 也可，工具会自动兼容）。

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

stdout 统一输出 JSON。完整说明见 `skill/SKILL.md`。

## 配置

单文件 `config.yaml`（默认模型 / 推理强度 / 迭代次数 / 工作目录 / 搜索与 PDF 后端等）。
所有默认值均可被 CLI 参数覆盖（`--max-iterations`、`--workdir`、`--download-format`、
`--search-backend`、`--pdf-backend`）。

## 结构

```
cli.py                 # CLI 入口
core/                  # 核心库
  config.py            # 配置加载 + CLI 覆盖
  workspace.py         # 命题 id / checkpoint / 目录
  codex.py             # codex exec 封装（Windows 兼容）
  search.py            # TheoremSearch + arXiv TeX 源下载
  pdf.py               # PDF 提取（MinerU -> .env python -> PyMuPDF）
  verify.py            # 自然语言验证（独立 codex 会话）
  derive.py            # 推导循环编排
  agent_mcp.py         # 内部 MCP server（memory/search/download）
templates/             # codex 配置与 AGENTS 模板
skill/SKILL.md         # 主 agent 使用的 skill
tests/                 # 冒烟测试 + 推导循环逻辑测试
```

## 测试

```powershell
.\.venv\Scripts\python tests\smoke.py            # 冒烟测试（含网络）
.\.venv\Scripts\python tests\smoke.py --offline  # 跳过网络
.\.venv\Scripts\python tests\derive_loop_test.py # 推导循环逻辑（fake codex）
```
