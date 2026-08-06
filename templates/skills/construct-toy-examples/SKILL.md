---
name: construct-toy-examples
description: Generate and analyze simpler examples that satisfy both the assumptions and the conclusion of a theorem statement or subgoal. Use when you are stuck in reasoning and need simpler examples to regain traction, when you need simpler examples that satisfy both assumptions and conclusion, or when you want to see where the assumptions take effect and gain intuition.
---

# Construct Toy Examples

Use this skill when the agent is stuck in reasoning and needs simpler examples that satisfy both the assumptions and the conclusion in order to understand why the statement works.

## Input Contract

Read:

- current statement/subgoal
- `memory/immediate_conclusions.jsonl`
- `memory/counterexamples.jsonl` 与失败分支记录
- `downloads/`、`refs/` 中相关背景

## Procedure

1. Construct simpler cases (low degree, small dimension, special forms, canonical objects).
2. Ensure the toy example satisfies all assumptions of the target statement or subgoal.
3. Check that the conclusion also holds in the toy example.
4. Study where each assumption takes effect and what mechanism makes the conclusion true.
5. Identify repeated patterns, invariants, or proof ideas suggested by the example.
6. Use `$search-math-results` / 推理 / 分解 as needed to find examples or simplify the situation.

## Output Contract

Append to `memory/toy_examples.jsonl`（每行一个 JSON，含 `ts`）：

```json
{
  "example": "...",
  "why_relevant": "...",
  "assumptions_satisfied": ["..."],
  "conclusion_verified": true,
  "where_assumptions_take_effect": "...",
  "observed_pattern": "...",
  "supports_branch_ids": ["optional"],
  "subgoal_id": "optional"
}
```

## Failure Logging

If generated examples are inconclusive, append an `events` record to `memory/events.jsonl`:

- `event_type="toy_examples_inconclusive"`
- include attempted example families
