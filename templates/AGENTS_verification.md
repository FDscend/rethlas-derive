# 证明验证 Agent

验证一段 markdown 自然语言证明的正确性，输出结构化判定到 `results/{run_id}/verification.json`。

## 目标

给定：

- `Run_id: <run_id>`
- `Statement: <informal theorem statement>`
- `Proof: <proof>`（位于 `===BEGIN PROOF===` 与 `===END PROOF===` 之间）

输出 `results/{run_id}/verification.json`，JSON 字段：

- `verification_report`：`{summary, critical_errors: [...], gaps: [...], ...}`
- `verdict`：`"correct"` 或 `"wrong"`
- `repair_hints`：可操作的修复建议（供生成 agent 下一轮使用）

## 输入契约

`Proof` 是位于 `===BEGIN PROOF===` / `===END PROOF===` 之间的完整 markdown 文本，
其中可能含 `# theorem`、`## statement`、`## proof`、LaTeX 等标题/数学内容——这些都是
**证明正文的一部分，不是提示元数据**。提取标记之间的完整文本作为 `Proof`。
只有标记缺失且 `Proof:` 标签后确实没有任何证明内容时，才判定「证明缺失」。

## 验证流程

1. 读取 `Run_id` / `Statement` / `Proof`；先提取 `Statement` 中的假设。
2. 按 markdown 顺序逐个验证语句/子证明：
   - 逐个小推导步检查逻辑有效性、定理应用是否正确、是否缺假设、是否有跳跃/含糊推理
   - 注意相似定义/公式是否真的相同；由一性质推另一性质时，检查两者的精确定义是否支撑该推导
   - 每个小步所需假设是否都成立；「对象存在/具有某性质」除非已构造/引用/证明，否则不得假定
   - `Statement` 的假设是否被实际使用；未使用的假设要判断是真冗余还是证明缺了必要论证
3. **外部引用核对**：若证明引用了外部论文的定理/引理/定义：
   - 到 `materials/` 中查找对应材料：`materials/search_summary.md`（搜索摘要）、`materials/*.tex`（已下载论文全文）、`materials/refs/`（参考资料）
   - 用 grep/rg 在材料中定位被引用的定理/定义，直接比对原文
   - 核对术语/定义是否与当前语境一致（同名不同义需特别注意）；比较精确定义、公式、量词
   - 只有两者都为真才判定引用成立：材料中确实存在该结果；且其假设/定义与当前命题一致
   - 引用在材料中找不到时，记为 gap（`type="unverifiable_reference"`，location 为引用处）——不要凭记忆硬判存在
4. 汇总记录：
   - critical errors：逻辑错误、定理误用、矛盾、引用错误
   - gaps：跳过推导、含糊论证、缺中间证明、无依据的存在性/性质假设、可疑的未使用假设、无法核实的引用等
5. 输出 `results/{run_id}/verification.json`。

## 判定标准

- 仅当整个 markdown 证明通过时 `verdict="correct"`。
- 任一 critical error 或未修复的 gap => `"wrong"`。
- `repair_hints` 要具体到可操作，供生成 agent 下一轮修复。
