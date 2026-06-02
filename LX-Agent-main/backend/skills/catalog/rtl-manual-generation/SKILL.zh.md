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
   - `modules/<module>/module_doc_card.json`
   - `modules/<module>/interfaces.json`
   - `modules/<module>/flows/*.json`
   - `modules/<module>/gaps.json`
5. 旧 `manual_ir/<top_module>` 和 ContextPack 只作为 legacy 兼容产物，不再作为新手册主结构。
6. 遇到证据不足时必须明确写“证据不足”或“需要 review”，不能补猜。
7. 允许通过 Manual Context 中的 `source_review_context` 做受控 RTL 源码复核，但只能用于端口分组、模块一句话用途提示和证据缺口复核；不得据此新增连接、flow、FSM、always、寄存器更新、时序保证或确定性设计意图。

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
10. 对优先级内的 `requires_rtl_source_review=true`、`review_status=needs_review`、`source_review_request` 和 `evidence_gap` 执行受控 Source Review，并把 `source_review_claims` / `source_review_report` 写回 Manual Context。
11. 生成手册前，先规划目录和每章使用的证据来源。
12. 最终手册必须由 Manual Context 证据边界渲染器生成，不把自由发挥式 LLM 初稿作为权威正文。
13. 生成后必须先做 Manual Context checker，再考虑任何模型辅助审查。

## 阶段重跑规则

当用户要求“重新生成 / 重跑 / 强制生成 / 覆盖 / 从某阶段开始继续”时，不要让模型自己手动调用零散工具，必须交给 `manual_workflow` 的阶段控制逻辑处理。

用户可以指定这些阶段：

- `references`：读取 skill/reference
- `parser`：解析 RTL
- `knowledge`：生成 Knowledge IR / Manual Context
- `evidence`：建立证据摘要
- `source_review`：源码复核
- `outline`：生成目录
- `chapter_plan`：章节规划
- `manual`：生成手册正文
- `review`：生成审查报告

如果用户指定某一阶段，则 workflow 应：

1. 将当前 stage 设置为该阶段。
2. 强制该阶段重新执行，即使已有产物。
3. 将该阶段之后的阶段标记为需要重跑。
4. 用户要求继续或当前是自动执行模式时，自动执行后续阶段。
5. 不删除 RTL 源文件，不在 workflow 之外编造阶段产物。

## 证据分层

- parser：RTL 结构事实来源。
- Knowledge IR：确定性事实权威层。
- AI Context：给 LLM 的压缩输入视图，不是权威事实源。
- Semantic Layer：AI 语义 claim 层，必须保留 evidence、confidence、doc_priority 和 review 标记。
- Manual Context：最终手册渲染器和必要模型辅助写作的主输入层。
- Source Review：只读取被标记为需要源码复核的关键项和白名单 RTL 切片，复核结论必须写回 Manual Context 后才能进入手册或 review 文档。

## 命令行调试入口

不启动 `app.py` 时，可以直接用分层 CLI 生成手册：

```bash
python -m backend.manual_cli build \
  --project-root ./rtl \
  --rtl-inputs rtl \
  --top-module arm_soc_top

python -m backend.manual_cli compose \
  --project-root ./rtl \
  --top-module arm_soc_top
```

常用参数：

- `build --force`：不复用已有 parser / knowledge / evidence / outline / chapter plan / base 产物，强制重跑。
- `source-review`：只对 `evidence_gap` / `needs_review` / `requires_rtl_source_review` 显式标记项执行受控源码复核，写回 Manual Context，并标记增强片段过期。
- `enhance --main-manual`：把整篇 base 主手册作为一个 fragment 增强，并注入紧凑 Manual Context digest。
- `enhance --target-module <module>`：只增强一个 base 模块页。
- `compose`：用有效增强片段生成公开最终手册；缺失、失败或 stale 时回退 base。
- `--no-llm`：不调用 source-review 模型，被标记项保留为证据缺口；`enhance` 需要模型 client。
- `--require-llm`：没有 OpenAI-compatible API key 时直接失败。
- `--knowledge-timeout 3600`：给全量 Semantic Layer 重跑更长时间。

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

如果使用受控 RTL 源码复核切片，复核得到的文字只能作为 `ai_inferred` 或 `evidence_gap` 进入手册；除非同一事实已经存在于 parser / Knowledge IR / Manual Context 的确定性字段中，否则不能写成 `deterministic_fact`。

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
- 是否遗漏 `evidence_gap` 或 `review_questions` 中的问题。
- 是否为每个 reachable module 提供主手册入口和模块页。
- 是否仍用“样本”层级或“样本”职责表替代完整层级 / 完整模块索引。
- 是否编造 FSM、always、寄存器更新或时序保证。
- 是否过度解释 free 信号。
- 是否把 legacy `manual_ir` / ContextPack 当作主结构。

## 固定手册形态

使用“主手册 + 模块页”：

- 项目总览：只写一句项目用途推断、RTL 目录、顶层文件。
- 顶层模块：写直接子模块和外部端口分组自然语言摘要，不要原样倾倒全部端口。
- 完整模块层级结构：列出全部 hierarchy edges，不写样本。
- 子系统与模块索引：每个 reachable module 都必须有模块页入口，不展示详情级别。
- 主手册不写关键 Drive-centered flow 索引，flow 细节下沉到模块页。
- 主手册和模块页不展示 `evidence_refs`、`confidence`、`review_status`、`requires_rtl_source_review` 或 Evidence 列。
- 证据缺口、review 问题、证据边界和 Source Review 审计信息统一写入 review 文档。

每个模块页固定包含：职责、层级位置、输入/输出摘要、drive/data/free 契约、主要 flow、内部组件/assign 影响。关键模块详写，helper/leaf 模块可以使用压缩卡片。
