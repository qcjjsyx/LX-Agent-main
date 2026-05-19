# RTL 代码手册审查报告

- 审查目标：`arm_soc_top`
- 审查方式：Manual Context 结构化约束检查
- 总体结论：通过

## 检查结果
- 未发现确定性结构检查项违规。

## 已检查约束
- final manual 不应包含对话式开场。
- final manual 不应把 `manual_ir` 或 ContextPack 作为主证据结构。
- `ai_inferred` 内容必须在手册中标注为 AI 推断。
- `evidence_gap` 必须进入证据缺口或 review 章节。
- `deterministic_fact` 行不得混入“可能/推断/需要 review”等不确定措辞。
- `free` 只作为影响 drive availability/backpressure 的参考，不作为主流程解释入口。

## 剩余风险
- 本审查器只做结构化和文本边界检查；复杂 RTL 语义仍以 Manual Context 的 evidence_refs 和后续人工 RTL review 为准。
