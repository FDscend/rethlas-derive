---
name: derive-proposition
description: >
  对数学命题进行自动推导：传入完整命题表述（与可选参考资料），工具自动搜索相关
  定理和论文、生成自然语言证明、验证并迭代，直到验证通过或达到最大迭代次数。
  返回 JSON（推导结果 md 路径、是否成功、checkpoint 等）。适用于写论文时需要
  验证某个命题/引理/定理的场景。
metadata:
  openclaw:
    requires:
      bins: [codex]
    config:
      - ../config.yaml
---

# 命题推导工具（derive-proposition）

> 先决条件：工具目录 `d:\code\WorkSpace_ai\Rethlas-MCP`，已安装 `pip install -r requirements.txt`，
> 且 `codex` 可用（Windows 上 npm 安装的 codex 也可，工具会自动兼容）。

## 何时使用

- 写论文时有一个**命题/引理/定理**需要推导（证明），且条件可能分散在论文不同章节。
- **先写出完整命题表述**：把分散在各章节的条件整合成一条完整、自洽的表述
  （工具假定传入的表述是完整的；遗漏条件=新命题=重新推导）。

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

## 注意事项

- **续推前提是命题表述不变**；修改表述 = 新 id = 重新推导。
- 推导过程完全在工具内完成，不需要干预；推导日志在 `<工作目录>/<id>/logs/iter/`，
  如需调试可查看。
- 论文默认从 arXiv 下载 **TeX 源**（免 PDF 转换）；仅 arXiv 来源可自动下载，
  其它来源或下载失败时，把论文通过 `--ref` / `--add-ref` 传入。
