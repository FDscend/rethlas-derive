---
name: construct-counterexamples
description: Construct candidate counterexamples to test a proposed conjecture, lemma, or intermediate claim by keeping the assumptions true while making the claimed conclusion fail. Use when you are stuck in reasoning and want to see where the assumptions take effect and gain intuition, when a proposed conjecture/claim feels fragile or unproved, or when you want to test whether the assumptions can hold while the claimed conclusion fails.
---

# Construct Counterexamples

Actively falsify proposed conjectures or intermediate claims by finding examples that satisfy the assumptions but violate the claimed conclusion.

## Input Contract

Read:

- the specific conjecture/claim to test
- active branch assumptions
- candidate lemmas/proof steps
- `memory/immediate_conclusions.jsonl` 与 `memory/toy_examples.jsonl`
- `memory/counterexamples.jsonl`（已有反例可复用）

## Procedure

1. Identify the assumptions that must hold and the conclusion to fail.
2. Use reasoning, decomposition, and `$search-math-results` to search for standard obstructions, pathological constructions, or previously known counterexamples.
3. Decide status:
   - `refuted`: assumptions hold and the claim fails
   - `not_refuted`: no counterexample found yet
   - `inconclusive`: search space unclear or partially explored
4. If the search produces a concrete example that is informative but is not actually a counterexample, save that example as well in `memory/toy_examples.jsonl`.
5. If refuted, store the counterexample for reuse against future claims and mark impacted branches/lemmas as invalid.
6. If no counterexample is found, treat that only as evidence that the claim may be correct, not as a proof.

## Output Contract

Append to `memory/counterexamples.jsonl`（每行一个 JSON，含 `ts`）：

```json
{
  "target_claim": "...",
  "candidate_counterexample": "...",
  "status": "refuted|not_refuted|inconclusive",
  "assumptions_satisfied": ["..."],
  "failed_conclusion": "...",
  "impact": "...",
  "branch_id": "optional",
  "subgoal_id": "optional"
}
```

If `status="refuted"`, also append to `memory/failed_paths.jsonl` when it kills a branch.

If the search produced a concrete non-refuting example, also append a record to `memory/toy_examples.jsonl`:

```json
{
  "example": "...",
  "why_relevant": "constructed while testing the claim ...",
  "assumptions_satisfied": ["..."],
  "conclusion_verified": true,
  "where_assumptions_take_effect": "...",
  "observed_pattern": "...",
  "supports_branch_ids": ["optional"],
  "subgoal_id": "optional"
}
```
