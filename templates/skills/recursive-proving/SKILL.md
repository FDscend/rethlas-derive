---
name: recursive-proving
description: Launch one sub-agent per decomposition plan after direct screening has identified the key stuck points for each plan. Use when all current plans have been screened by direct proving, none fully solves the problem, and parallel recursive work is needed.
---

# Recursive Proving

Use this skill when direct proving has failed on the current decomposition plans.

> 说明：子代理能力取决于 codex 会话是否支持 multi-agent。若当前会话不支持生成子代理，请退化为"串行逐个深入各分解方案"，并把结果汇总到 `$identify-key-failures`。

## Input Contract

Read:

- the current set of decomposition plans
- `memory/proof_steps.jsonl`（direct-proving 报告与各方案关键卡点）
- `memory/failed_paths.jsonl`、`memory/branch_states.jsonl`
- `downloads/search_summary.md` 与相关引用

## Procedure

1. Confirm that all current decomposition plans have already been attempted with `$direct-proving` and that none has fully solved the problem.
2. Spawn one sub-agent per decomposition plan（若支持）。
3. Give each sub-agent:
   - the full target theorem
   - the assigned decomposition plan
   - the key stuck points for its own plan
   - the key stuck points found in the other plans
   - the instruction to follow `AGENTS.md`
4. Tell each sub-agent to tackle the assigned plan under the instructions in `AGENTS.md`, treating that plan as its starting point rather than restarting the search from zero. If new evidence or discoveries justify it, the sub-agent may refine, extend, or locally revise the plan, but it should preserve continuity with the assigned plan instead of discarding it outright.
5. Tell each sub-agent that it may itself spawn sub-agents recursively if that helps its assigned plan.
6. Require each sub-agent to write progress, failures, and any successful proof development back into `memory/`（同一命题的通道文件）using the same `problem_id`.
7. Wait for all sub-agents to finish, then gather their reports.
8. If any plan succeeds, assemble the proof draft from that plan.
9. If all plans fail, hand the collected reports to `$identify-key-failures`.

## Output Contract

Append an `events` record to `memory/events.jsonl` for the recursive round：

```json
{
  "event_type": "recursive_proving_round",
  "plan_ids": ["..."],
  "subagent_ids": ["..."],
  "shared_stuck_points": {
    "plan_id": ["..."]
  },
  "status": "running|completed",
  "successful_plan_ids": ["..."],
  "failed_plan_ids": ["..."]
}
```

Update `memory/branch_states.jsonl` with the recursive round status and per-plan outcomes.
