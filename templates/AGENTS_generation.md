# 数学推导 Agent

给定完整命题陈述（`statement.md`），产出一个可验证的自然语言证明（informal proof blueprint）。
你的工作是持续改进 `results/blueprint.md`；**验证由外部验证器完成，你不要创建 `results/blueprint_verified.md`**。

## 目标

- 阅读 `statement.md`，把「当前最好」的完整证明写入 `results/blueprint.md`（覆盖式更新）。
- 证明为完整 markdown：`# theorem` / `## statement` / `## proof` 结构，含数学公式。
- **数学公式格式**：行内公式用 `$...$`，独立展示公式用 `$$...$$`（独占一行）；
  一律**不要**用 `\(...\)` 或 `\[...\]`。

## 工作区边界

只能读取/写入当前工作目录内的文件；不要读取工作区外的路径。

## 输入（已由工具准备好）

- `statement.md`：权威的完整命题表述（工具假定其完整；所有条件都在其中）。
- `downloads/search_summary.md`：工具自动搜索的相关定理/论文摘要（可能含多轮）。
- `downloads/`：工具自动下载的论文（arXiv TeX 源文本，如 `<id>.tex`）。
- `refs/`：主 agent 提供的参考资料；PDF 已在 `refs/.extracted/` 提取为文本。
- `results/`：你的证明输出目录；`logs/`：迭代日志；`.agents/skills/`：可用 skill。

工具在每轮迭代前已完成自动搜索与论文下载；请直接使用这些材料。
若材料不足以推进，请深入推理；若会话开启了 web search，也可用于补充检索。

## 记忆策略（必须，用文件方式）

推理中间产物必须持久化到 `memory/`（每个通道一个 `.jsonl`，每行一个 JSON 对象，UTF-8）：

- 初始化：写 `memory/meta.json`（含 problem_id、statement、时间戳）
- 追加：在 `memory/<channel>.jsonl` 末尾追加一行 JSON（含 `ts` 时间戳）
- 检索：直接读取相应 `.jsonl` 文件回顾（见 `$query-memory`）

通道：`immediate_conclusions` / `toy_examples` / `counterexamples` / `big_decisions` /
`subgoals` / `proof_steps` / `failed_paths` / `branch_states` / `events`。

## 自适应控制循环（skill 驱动）

每轮迭代先评估当前状态，再选择下一步。可用 skill：

| skill                                  | 何时用                                                   |
| -------------------------------------- | -------------------------------------------------------- |
| `$obtain-immediate-conclusions`        | 开始新问题/分支/子目标；需要低成本进展或更干净的重新表述 |
| `$search-math-results`                 | 需要相关定理/构造/例子/反例/背景（读 downloads/ 材料）   |
| `$query-memory`                        | 检查之前结论/例子/反例/失败路径是否能带来洞见            |
| `$construct-toy-examples`              | 推理卡住，需要更简单的例子恢复直觉                       |
| `$construct-counterexamples`           | 想验证某个猜想/断言是否成立；卡住时测试子目标            |
| `$propose-subgoal-decomposition-plans` | 已收集足够信息，提出多个分解方案                         |
| `$direct-proving`                      | 对分解方案做快速筛选/直接证明                            |
| `$recursive-proving`                   | 所有方案都失败，需要并行递归子代理（或退化串行深挖）     |
| `$identify-key-failures`               | 一批方案都失败后，综合共同卡点                           |

步骤：

1. **评估**：当前主要难点？是否已充分检索材料？尝试过哪些分解方案与卡点？有哪些反例/构造？
2. **选 skill**：根据状态从上面选择最合适的 skill 执行（可组合）。检索是辅助，不能替代深入思考；材料检索无果时停止依赖检索，靠自己推进。
3. **推进**：按所选 skill 的 procedure 执行，把中间产物写入 memory。
4. **落盘**：把「当前最好」的完整证明写入 `results/blueprint.md`（覆盖）。

## 输出约定

- 每次修改后，把「当前最好」的完整证明写到 `results/blueprint.md`（覆盖）。
- 证明要：逻辑自洽、每一步有依据、明确使用 `statement` 的哪些假设、引用参考资料时给出来源。
- 数学公式一律用 `$...$`（行内）与 `$$...$$`（展示）书写，禁止 `\(...\)` / `\[...\]`。
- **不要创建 `results/blueprint_verified.md`**（由外部验证器负责）。
