---
name: rtl-manual-generation
description: 基于 parser 产物、Knowledge IR、AI Context、Semantic Layer claims 和 Manual Context，为 RTL 或源码项目生成结构化代码手册。
---

# RTL 代码手册生成 Skill（中文）

本 skill 用于为 RTL 或源码项目生成结构化 Markdown 代码手册。只要已有 parser / knowledge / manual context 产物，就不要直接凭 RTL 源码总结；必须沿着结构化证据链生成手册。

## 核心规则

1. 除非用户明确要求分析或修改工具实现，否则不要阅读 parser / knowledge 实现细节。
2. `scripts/run_parser_tool.py` 和 `scripts/run_knowledge_tool.py` 是 skill 自有脚本。
3. 使用暴露出来的 `run_parser_tool` 和 `run_knowledge_tool`。其中 `run_knowledge_tool` 现在是 `python -m knowledge.pipeline` 的兼容封装。
4. 新手册必须以 `manual_context/<top_module>` 为主输入，优先读取：
   - `project_context.json`
   - `system_topology.json`
   - `interface_index.json`
   - `flow_index.json`
   - `evidence_index.json`
   - `validation_report.json`
   - `modules/<module>/module_context.json`
   - `modules/<module>/interfaces.json`
   - `modules/<module>/flows/*.json`
   - `modules/<module>/gaps.json`
5. 旧 `manual_ir/<top_module>` 和 ContextPack 只作为 legacy 兼容产物，不再作为新手册主结构。
6. 遇到证据不足时必须明确写“证据不足”或“需要 review”，不能补猜。

## 主流程

1. 读取 skill metadata 中列出的 reference 文件。
2. 总结 parser、knowledge pipeline、输入、输出和证据边界。
3. 如果用户没有提供 `project_root`，默认使用 `.`。
4. 如果用户说输入是 RTL 但没有提供 `rtl_inputs`，默认使用 `rtl`。
5. 如果用户没有提供 `top_module`，先询问顶层模块名。
6. parser 产物缺失或用户要求重跑时，执行：
   `run_parser_tool(project_root, rtl_inputs)`。
7. 执行：
   `run_knowledge_tool(project_root, top_module, enrich=True)`。
8. Knowledge 阶段的新主链路是：
   `parser_pipeline_rtl -> knowledge_ir -> ai_context -> semantic_layer -> manual_context`。
9. 生成目录前，先从 `manual_context/<top_module>` 建立证据索引。
10. 生成手册前，先规划目录和每章使用的证据来源。
11. 最终手册必须由 Manual Context 证据边界渲染器生成，不把自由发挥式 LLM 初稿作为权威正文。
12. 生成后必须先做 Manual Context checker，再考虑任何模型辅助审查。

## 证据分层

- parser：RTL 结构事实来源。
- Knowledge IR：确定性事实权威层。
- AI Context：给 LLM 的压缩输入视图，不是权威事实源。
- Semantic Layer：AI 语义 claim 层，必须保留 evidence、confidence、doc_priority 和 review 标记。
- Manual Context：最终手册渲染器和必要模型辅助写作的主输入层。

## 写作规则

- `deterministic_fact`：可以直接陈述。
- `derived_fact`：必须说明是从上下文派生。
- `ai_inferred`：必须标注“推断 / 可能 / 需要 review”，不能写成确定事实。
- `human_asserted`：必须标注为人工断言。
- `evidence_gap`：必须写入证据不足或待审查章节。

禁止补充 Manual Context 中没有的：

- 模块
- 信号
- 接口
- 连接
- flow
- 时序保证
- FSM 行为
- always block 行为
- 寄存器更新条件

## RTL 文档重点

当前项目的主要控制模式是基于数据事件绑定的 drive-centered flow。

- `drive` 是核心事件信号，应作为 flow 解释重点。
- `free` 可以记录。
- 只有当 `free` 影响 drive availability 或 backpressure 时，才在最终文档中重点解释。

## Review / Checker 规则

手册生成后必须检查：

- Markdown 正文是否包含寒暄、执行承诺等对话式开场。
- 是否引用不存在的模块、信号、接口或 flow。
- 是否把 AI 推断写成确定事实。
- 是否遗漏 `evidence_gap`、`review_questions` 或 `validation_report` 中的问题。
- 是否编造 FSM、always、寄存器更新或时序保证。
- 是否过度解释 free 信号。
- 是否把 legacy `manual_ir` / ContextPack 当作主结构。

## 推荐章节

根据 Manual Context 动态取舍，不强行套模板：

- 项目总览
- 顶层模块
- 模块层级结构
- 关键模块职责
- 接口与数据事件契约
- Drive-centered flow
- 内部组件与 assign 影响
- backpressure / free 说明（仅在影响 drive 可用性时）
- 证据缺口与 review 问题
- 维护建议
- 证据边界
