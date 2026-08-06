---
name: obtain-immediate-conclusions
description: Derive immediate mathematical consequences from a theorem statement or subgoal. Use when starting a new problem, branch, or subgoal, or when cheap progress or a cleaner reformulation is needed before deeper proof search.
---

# Obtain Immediate Conclusions

Extract direct implications before speculative reasoning.

## Input Contract

Read from memory and current context:

- `problem_id`
- current theorem/subgoal statement
- `memory/`（已有结论/反例等）

## Procedure

1. Normalize notation and restate the claim in equivalent forms.
2. List direct consequences that follow from definitions and basic algebraic/logical manipulations.
3. Split consequences into necessary conditions and candidate sufficient conditions.
4. Mark each consequence with confidence and justification type.
5. For every conclusion, explicitly decide whether it is likely fragile and should be stress-tested by counterexample.
6. If a conclusion is fragile, record why it is fragile and indicate that `$construct-counterexamples` should be considered next.

## Output Contract

Append each conclusion to `memory/immediate_conclusions.jsonl` (每行一个 JSON 对象，UTF-8，含 `ts` 时间戳)：

```json
{
  "statement": "...",
  "justification_type": "by_definition|calculation|known_fact|logical_equivalence",
  "confidence": 0.0,
  "is_fragile": false,
  "fragility_reason": "",
  "suggested_followup": "none|construct-counterexamples",
  "scope": "global|branch|subgoal",
  "branch_id": "optional",
  "subgoal_id": "optional"
}
```
