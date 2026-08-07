---
name: rethlas-derive
description: >
  数学命题的自动推导验证（重工具，单次数十分钟到数小时）：传入完整命题表述与
  可选参考资料，自动搜索相关定理/论文，调用 codex 多轮生成并验证证明，直至通过
  或达到最大迭代次数，返回 JSON（结果 md 路径、是否成功、checkpoint）。
  仅在满足以下条件时触发：命题复杂、证明依赖外部文献、需要多轮验证迭代，或用户
  明确要求“推导/验证/证明”某命题且接受长时间运行。
  对简单问题（可一步推导、仅询问概念或思路、无需外部资料）不要触发本工具，
  直接由模型回答。
---

# 命题推导工具（rethlas-derive）

> 先决条件：工具目录（安装后的 `rethlas-derive` 目录，含 `cli.py`、`core/`、`config.yaml`、
> 保持相对结构不变）已就位，已按 `INSTALL.md` 安装依赖（`pip install -r requirements.txt`）、
> 把 `.env.example` 复制为 `.env` 并填写密钥，且 `codex` 可用（Windows 上 npm 安装的 codex 也可，工具会自动兼容。
> 在新仓库安装 / 注册为 skill：见 `INSTALL.md`。

## 安装与注册

本仓库**根目录就是 skill 目录**：`SKILL.md` 与 `cli.py`、`core/`、`config.yaml`、`templates/`、`.env.example` 同级，
`core/config.py` / `core/env.py` 按 `__file__` 相对定位配置，整体 clone / 解压即可用，**无需复制文件、无需改路径**。

安装 = 把本仓库放到目标 agent 的 skills 目录 → 装依赖 → 复制 `.env.example` 为 `.env` 并填写。详细步骤见 `INSTALL.md`。

本文件 frontmatter 仅含 `name` 与 `description`（agentskills.io 通用格式），
GitHub Copilot、OpenAI Codex CLI 等支持 skills 的 agent 均可直接识别，无需按平台改动。

### 以 GitHub Copilot 为例（项目级，随仓库提交）

```powershell
# 在目标仓库根目录执行：协作者 clone 主仓库时即自带 skill
git clone https://github.com/FDscend/rethlas-derive.git .github/skills/rethlas-derive
```

### 以 OpenAI Codex CLI 为例（个人级，全局可用）

```powershell
git clone https://github.com/FDscend/rethlas-derive.git ~/.codex/skills/rethlas-derive
```

> - 下载 zip 时，解压出的目录名通常是 `rethlas-derive-main`，请重命名为 `rethlas-derive` 再放入 skills 目录。
> - 项目级目录：Copilot 认 `.github/skills/`（也认 `.claude/skills/`、`.agents/skills/`）；
>   Codex 认 `.codex/skills/`。
> - 个人级目录：Copilot 认 `~/.copilot/skills/`；Codex 认 `~/.codex/skills/`。
> - 各 agent 启动时扫描 skills 目录；新增/修改 skill 后需重启会话或重新加载才能生效。
> - `core/config.py` 按相对位置找 `config.yaml`、`core/env.py` 按相对位置找 `.env`，此结构下无需额外配置。

## 何时使用

- 写论文时有一个**命题/引理/定理**需要推导（证明），且条件可能分散在论文不同章节。
- **先写出完整命题表述**：把分散在各章节的条件整合成一条完整、自洽的表述
  （工具假定传入的表述是完整的；遗漏条件=新命题=重新推导）。

### 触发前的软降级判断

本工具是重型操作（单次数十分钟到数小时）。即使已自动加载本 skill，也请先判断：

- **应当运行工具**：命题复杂、证明依赖外部文献、需要多轮验证迭代，或用户明确要求
  “推导/验证/证明”且接受长时间运行。
- **不运行工具，直接回答**：可一步给出推导、仅询问数学概念/思路、无需外部资料。
  直接回答，并在末尾注明“未使用推导工具”。

## 工作流

### 1. 首次推导

```powershell
python cli.py derive --statement "<完整命题表述，支持 LaTeX>" [--ref 论文.pdf|.tex|.md ...] [--max-iterations 8] [--workdir ./workspace]
```

- `--ref` 可多次：传入本地参考资料（PDF/TeX/Markdown）。PDF 会自动提取。
- `--max-iterations` / `--workdir` 可覆盖配置文件默认值。
- 推导可能耗时数十分钟到数小时（每轮迭代都调用 codex）。可先跑少量迭代试探。

返回 JSON（stdout）：
```json
{
  "id": "prop_<hash>",
  "success": true,
  "status": "verified | failed",
  "iterations_used": 8,
  "max_iterations": 8,
  "checkpoint": 8,
  "result_md_path": "<工作目录>/<id>/results/blueprint_verified.md",
  "draft_md_path": "<工作目录>/<id>/results/blueprint.md",
  "log_dir": "<工作目录>/<id>/logs/iter/",
  "verification": { "verdict": "correct", "verification_report": {...} },
  "summary": "供判断是否续推的简要说明"
}
```

### 2. 失败后判断 & 续推

`success=false` 时，先**读 `result_md_path`（草稿）和 `summary`** 判断：

- 若推导已接近成功 → 追加迭代次数：
  ```powershell
  python cli.py resume <id> --extra-iterations 2
  ```
- 若发现工具没搜到的参考资料 → 追加参考资料后续推：
  ```powershell
  python cli.py resume <id> --extra-iterations 2 --add-ref 论文.pdf
  ```
- 若遗漏了条件 → 修正完整表述后重新 `derive`（id 会变化，属新命题）。

### 3. 状态与清理

```powershell
python cli.py list                                   # 列出所有命题
python cli.py status <id>                            # 查看某命题状态
python cli.py clean <id> --target intermediate       # 清中间产物（logs/memory/downloads）
python cli.py clean <id> --target failed [--keep-checkpoint]  # 清失败产物（默认重置，可保留以便续推）
python cli.py clean <id> --target success            # 清已成功结果（重新推导用）
python cli.py clean <id> --all                       # 整目录清理
```

## 输出约定

- 生成的推导文档（`blueprint_verified.md` / `blueprint.md`）中，数学公式统一用
  `$...$`（行内）和 `$$...$$`（独立展示），不使用 `\(...\)` / `\[...\]`。
- 传入的命题表述建议同样用 `$...$` / `$$...$$` 书写（工具不强制，但保持一致更利于渲染）。

## 注意事项

- **续推前提是命题表述不变**；修改表述 = 新 id = 重新推导。
- 推导过程完全在工具内完成，不需要干预；推导日志在 `<工作目录>/<id>/logs/iter/`，
  如需调试可查看。
- 论文默认从 arXiv 下载 **TeX 源**（免 PDF 转换）；仅 arXiv 来源可自动下载，
  其它来源或下载失败时，把论文通过 `--ref` / `--add-ref` 传入。
