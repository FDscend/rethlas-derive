# 命题推导工具（Rethlas-MCP）项目说明

> 把 `ref\Rethlas` 的「命题 → 搜索 → 生成推导 → 验证 → 迭代」流程，封装成**独立 CLI（封装成 skill）**：主 agent 直接传入完整命题表述和参考资料（而非放入指定文件夹），工具自动搜索、推导、验证、迭代，最后返回推导结果（JSON + md 路径）。

# 参考项目

- `ref\Rethlas`：将命题放入指定文件夹，gen agent 自动搜索相关命题和论文、生成推导，ver agent 验证推导，不断迭代直至验证通过或达到最大迭代次数。流程、产物结构（blueprint / blueprint_verified / memory / logs）与「生成-验证」循环沿用其设定。
- `ref\TheoremSearch-MCP`：数学命题/论文搜索（TheoremSearch，约 927 万条定理）。本项目只用其**官方远程服务**（与官方远程 MCP 同一后端），不维护本地包装 server。
- `ref\mineru-document-extractor`：更准确的 PDF→MD 工具（完整转换模式 + VLM）。

# 核心流程

1. 主 agent 调用 CLI（或直接使用封装好的 skill）
2. 工具**提示主 agent 先写出完整命题表述**——命题条件常分散在论文各章节；工具假定传入的表述是完整的
3. 工具自动搜索相关命题和论文（TheoremSearch），下载的论文存入该命题文件夹的 `downloads/`
4. 工具内部循环：生成推导（`codex exec`）→ 自然语言验证 → 未通过则进入下一轮迭代
5. 验证通过或达到最大迭代次数后，返回 JSON 结果
6. 失败时主 agent 查看结果判断：可**续推**（追加迭代次数 / 追加参考资料），或清理后重来

# 接口形态：CLI 为主（封装成 skill）

结论：**用 CLI，不用 MCP**（核心逻辑做成独立库，未来如需要可加一层薄 MCP 包装复用）。

理由：

- **长任务**：单次推导可达数十分钟～数小时。MCP 工具调用受客户端超时约束，长任务需异步任务 + 轮询，复杂且脆弱；CLI 在终端运行没有此问题。
- **中途判断**：关键场景是「先跑 8 次 → 主 agent 看结果判断 → 追加 2 次 → 成功」，这是多轮决策流程。用 skill 可以把整个工作流（含判断点、命令示例、返回 JSON 字段说明）写清楚，主 agent 照 skill 执行即可；MCP 每次调用是黑盒单发，承载不了中间判断环节。
- **底层一致**：底层就是 `codex exec`（命令行工具），外壳用 CLI 最顺。
- 主 agent 可另行注册**官方 TheoremSearch 远程 MCP**（`https://api.theoremsearch.com/mcp`）用于自己辅助搜索。

# 输入

- **命题**：完整表述（支持 LaTeX），用 `--statement`（字符串）或 `--statement-file`（文件）传入
- **参考资料（可选）**：本地 PDF / TeX / Markdown 路径列表（`--ref`），工具将其纳入该命题的 `refs/`
- **覆盖参数**：`--max-iterations N`、`--workdir <dir>`（覆盖配置文件默认值）
- **配置**：单文件 `config.yaml`（见「配置」节）

# 输出（JSON + md）

CLI 在 stdout 打印 JSON，同时把推导结果写入 md 文件：

```json
{
  "id": "命题稳定ID（表述内容哈希）",
  "success": true,
  "status": "verified | failed",
  "iterations_used": 8,
  "max_iterations": 8,
  "checkpoint": 8,
  "result_md_path": "<工作目录>/<id>/results/blueprint_verified.md",
  "draft_md_path": "<工作目录>/<id>/results/blueprint.md",
  "log_dir": "<工作目录>/<id>/logs/iter/",
  "verification": { "is_correct": true, "summary": "…" },
  "summary": "供主 agent 判断是否续推的简要说明（失败时含失败原因、接近程度）"
}
```

- `success=false` 时 `result_md_path` 指向草稿，`summary` 给出失败原因与接近程度，供主 agent 决定是否续推。

# id 与 checkpoint

- **id**：由命题表述内容哈希生成（稳定），同一命题多次运行 id 相同，对应一个命题文件夹。
- **checkpoint**：记录推导进度（已完成迭代轮数、codex 会话 id、各产物路径），每轮迭代后更新，写入 `checkpoint.json`。
- **续推**：`resume <id> [--from-checkpoint N] [--extra-iterations M] [--add-ref ...]`，从上次进度继续，不重新开始。
  - 设计初衷：先跑 8 次失败 → 主 agent 判断已很接近 → 追加 2 次 → 成功。不必一开始就要求 10 次。
  - 续推时可**追加参考资料**（主 agent 发现工具没搜到的论文，传入文件路径）。
  - 注意：**续推的前提是命题表述不变**；若遗漏条件、需要修改表述，属于新命题（id 变化），需重新推导。

# 文件夹结构（重新规划）

工具主程序目录可放在任意位置（skill / PATH / MCP 配置指向即可），与命题数据（工作目录）分离：

```
<工具安装目录>/               # 主程序（放哪都行）
  cli.py                       # CLI 入口
  core/                        # 核心库：推导循环 / codex 封装 / 验证 / 搜索 / PDF
  skill/SKILL.md               # skill 封装（供主 agent 使用）
  config.yaml                  # 统一配置（默认模型、迭代次数、输出路径等）
  requirements.txt

<工作目录>/                    # 命题数据（默认 ./workspace，可用配置/参数覆盖）
  <命题id>/
    statement.md               # 完整命题表述
    refs/                      # 主 agent 传入的参考资料（pdf/tex/md）
    refs/.extracted/           # 参考 PDF 提取出的 md
    downloads/                 # 工具自动搜索下载的论文（arXiv TeX 源，解压拼接后的 .tex 文本）
    logs/iter/                 # 每轮迭代日志
    memory/                    # 推导记忆（沿用 Rethlas 结构）
    results/
      blueprint.md             # 当前推导草稿
      blueprint_verified.md    # 验证通过的最终结果
    checkpoint.json            # id / checkpoint 元数据
```

# 清理工具

按 id 清理，与 checkpoint 对应：

- `clean <id> --target intermediate`：清中间产物（logs/、memory/、downloads/），保留 statement.md、refs/、results/、checkpoint
- `clean <id> --target failed`：清失败推导产物（未验证的草稿）；`--keep-checkpoint` 可保留 checkpoint 以便续推
- `clean <id> --target success`：清已验证结果（blueprint_verified.md），用于重新推导
- `clean <id> --all`：整目录清理
- `list` / `status <id>`：查看现有命题与推导状态

# 配置（单文件 config.yaml）

所有默认值均可被 CLI 参数覆盖（如 `--max-iterations`、`--workdir`；嵌套字段也有对应参数，如 `--download-format`、`--search-backend`、`--pdf-backend`）。字段清单：

```yaml
# ---- 模型（生成/验证统一）----
model: gpt-5.6-terra # 默认模型
reasoning_effort: xhigh # 推理强度

# ---- 推导循环 ----
max_iterations: 8 # 默认最大迭代次数（--max-iterations 覆盖）

# ---- 路径 ----
workdir: ./workspace # 命题数据工作目录（--workdir 覆盖）

# ---- codex（底层生成/验证）----
codex:
  bin: codex # codex 可执行文件路径（Windows npm 安装的是 .cmd shim，需用 shutil.which 解析）
  timeout_seconds: 0 # 单次 codex exec 超时（秒），0=不限制
  # Windows 兼容：二进制为 .cmd/.bat 时经 cmd /c 调用（同 Rethlas 验证端 server.py）

# ---- 定理搜索 ----
search:
  backend: theoremsearch # theoremsearch（默认）| leansearch（预留）
  max_search_rounds: 3 # 推导循环内最多自动搜索几轮
  download_papers: true # 搜索到的论文是否下载到 <命题>/downloads/
  download:
    format: tex # tex（默认，下载 arXiv TeX 源，免 PDF 转换）| pdf
    timeout_seconds: 60 # 单个文件下载超时
    ratelimit_seconds: 2 # 下载间隔（arXiv 限速）
  theoremsearch:
    api_base: https://api.theoremsearch.com
    n_results: 5 # 每次搜索返回条数
    timeout_seconds: 120

# ---- PDF 提取 ----
pdf:
  backend: mineru # mineru（默认）| pymupdf（强制离线）
  mineru:
    mode: extract # 完整转换模式（忽略快速模式）
    model: vlm
    auth: npm-cli # npm-cli（默认）| python（读 .env 的 MINERU_TOKEN）
    timeout_seconds: 900
  pymupdf:
    layout: true # 保留版面（类似 pdftotext -layout）

# ---- 验证 ----
verify:
  enabled: true # false 则只生成草稿、不做验证
  # 模型/推理强度与生成统一，无需单独配置

# ---- 日志 ----
logging:
  level: INFO # DEBUG / INFO / WARNING
```

# 其他要求

- 统一用 python，不写 sh；`codex exec` 作为外部二进制由 python subprocess 调用（同 Rethlas）
- codex 调用需处理平台兼容：Windows npm 安装的 codex 是 `.cmd` shim，需用 `shutil.which` 解析 bin，且 `.cmd`/`.bat` 经 `cmd /c` 调用（同 Rethlas 验证端 `server.py`）
- 推导与验证沿用 Rethlas 设定：**自然语言**，不做 Lean 形式化；生成与验证共用同一模型与推理强度
- 推导过程有日志输出（`logs/iter/` + CLI 进度），方便调试与主 agent 判断
- 每一个命题有 id 和 checkpoint，失败后可通过 id + checkpoint 续推（追加迭代次数），而非重新开始
- 清理工具：中间文件 / 失败 md / 成功 md（按需重新推导）

# 工具选择

- **搜索**：默认 TheoremSearch 官方服务（与官方远程 MCP 同一后端，直接调 REST API，不维护本地包装 server）；可通过配置切换。
  - **论文下载由工具自身实现**（参考项目无现成下载工具）：用搜索结果里的 arXiv ID 构造 `https://arxiv.org/e-print/{id}` 下载 **TeX 源**到 `<命题>/downloads/`，**跳过 PDF→MD 转换**。
  - e-print 返回的是 tar.gz（含多个 .tex）或单 .tex；解压后拼接所有 `.tex` 为 `<id>.tex` 文本直接作参考（LLM 原生读 LaTeX，公式无损）。tar.gz 按 `Content-Type: application/gzip` 处理（非 Content-Encoding，requests 不会自动解压）。
  - 仅当 e-print 不可用（如 PDF-only 投稿）时降级到 PDF 链；本地 PDF 参考与降级仍走 PDF 提取（见下）。
  - TheoremSearch 返回 `paper.paper_id`（如 `1011.0038v1`，可能带版本号）；leansearch 返回 `arxiv_id`。两个后端都能提供 arXiv ID。
  - 仅 `source: arXiv` 的结果可下载；Stacks Project / ProofWiki 等来源跳过并记日志。下载需限速、设超时，失败跳过（不强求全文）。
- **PDF 提取**（用于主 agent 传入的本地 PDF，以及 arXiv TeX 下载失败 / PDF-only 投稿的降级）：默认 MinerU（**完整转换模式 + VLM，忽略快速模式**）。按以下顺序降级：
  1. **npm CLI**：`mineru-open-api extract`（本地 npm 已认证 token）——默认
  2. **python 实现**：CLI 不可用/失败时，检查 `.env` 中的 mineru key，用 python 客户端调用（参考 mineru API 文档实现）
  3. **离线降级**：两者都没有时，降级到 PyMuPDF（纯 python 库、无外部二进制依赖，比调用 pdftotext 更适合 python 工具）
     可通过配置切换（如强制离线模式）。
