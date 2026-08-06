---
name: search-math-results
description: Find relevant math results, constructions, examples, counterexamples, and background references from the materials already prepared by the tool (downloads/ and refs/). Use when you need context for a new problem, supporting references, or external results while proving subgoals.
---

# Search Math Results

Use this skill as the default retrieval workflow for mathematical background and related results.

## Input Contract

Read:

- the current target statement, subgoal, lemma, or claim
- the search intent: `theorem` / `construction` / `example` / `counterexample` / `background`
- `downloads/search_summary.md`（工具自动搜索的定理/论文摘要，含多轮结果）
- `downloads/*.tex`（工具自动下载的 arXiv TeX 源，全文）

## Procedure

1. Start with `downloads/search_summary.md`：按当前子目标/卡点挑选相关结果。
2. 若摘要不够，打开对应的 `downloads/<arxiv_id>.tex` 读全文（用 grep/rg 定位相关定理/证明）。
3. Inspect the items and decide whether they are useful for the current need.
4. If a useful theorem/example/counterexample is found and it comes from a paper, read its proof and extract techniques, constructions, reductions, or proof patterns that may help.
5. Expand the definitions and concepts appearing in that theorem using the surrounding context of the paper, and check carefully whether the theorem is actually applicable to the current situation. Be explicit about terminology that may shift across contexts.
6. If the theorem is only a partial result for the current problem, analyze why its method does not immediately prove the full target statement. If it assumes extra hypotheses, do not merely try to force the current object to satisfy them; instead record why those hypotheses are used, where the proof breaks without them, and what obstruction or difficulty this reveals.
7. Record not only what the theorem says, but also what its proof suggests for the current problem.
8. 若本工作区材料不足：你**不能**在线检索（除非本会话开启了 web search），请深入推理推进；如果卡在缺背景上，明确记到 `memory/events.jsonl`（`event_type="search_math_results_stalled"`）供后续轮次补充检索。

## Usefulness Test

Treat retrieved results as useful only if they do at least one of the following:

- provide a theorem/lemma/definition close to the target statement
- provide a construction/example/counterexample that can be adapted
- suggest a standard technique or reformulation relevant to the current branch
- expose a meaningful obstruction or extra hypothesis in a partial result that clarifies why the full problem is harder

## Output Contract

Append a summary record to `memory/events.jsonl`：

```json
{
  "event_type": "search_math_results",
  "query": "...",
  "search_intent": "theorem|construction|example|counterexample|background",
  "results_summary": ["..."],
  "useful_references": [
    {
      "title": "...",
      "complete_statement": "...",
      "arxiv_id": "...",
      "local_tex_path": "optional",
      "expanded_definitions": ["..."],
      "applicability_check": ["..."],
      "partial_result_analysis": ["..."],
      "proof_insights": ["..."],
      "why_useful": "..."
    }
  ],
  "branch_id": "optional",
  "subgoal_id": "optional"
}
```
