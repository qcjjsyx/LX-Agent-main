# Skill Script Reference: Parser, Knowledge IR, Manual Context

本文档说明 `rtl-manual-generation` skill 当前推荐调用的 parser 与 knowledge 脚本。主流程已经从 legacy `manual_ir` 迁移到 `manual_context`。

## 总体定位

新主线是把 RTL 工程转换成最终手册生成 LLM 可消费的页面级上下文：

1. `parser.pipeline` 读取 RTL 工程，生成 parser artifacts。
2. `knowledge.knowledge_ir` 从 parser artifacts 生成确定性事实层。
3. `knowledge.ai_context` 把确定性事实压缩成 LLM 输入视图。
4. `knowledge.semantic_layer` 从 AI Context 生成可审查的语义 claims。
5. `knowledge.manual_context` 组织最终手册生成需要的页面级上下文。

推荐 skill 优先调用包装脚本，而不是直接拼装底层函数：

```bash
python backend/skills/catalog/rtl-manual-generation/scripts/run_parser_tool.py \
  --project-root <project_root> \
  --rtl-inputs <rtl_inputs>

python backend/skills/catalog/rtl-manual-generation/scripts/run_knowledge_tool.py \
  --project-root <project_root> \
  --top-module <top_module>
```

`run_knowledge_tool.py` 是兼容入口，内部调用：

```bash
python -m knowledge.pipeline \
  --artifacts-root <parser_artifacts_root> \
  --top-module <top_module> \
  --knowledge-output-root <artifact_base>/knowledge_ir \
  --manual-context-output-root <artifact_base>/manual_context \
  --skip-failed-semantic
```

## 目录约定

当前工程推荐目录：

- RTL 源码：`rtl/rtl`
- parser artifacts：`rtl/parser_pipeline_rtl`
- Knowledge IR：`rtl/knowledge_ir/<top_module>`
- Manual Context：`rtl/manual_context/<top_module>`

如果用户以 `project_root=rtl` 运行，包装脚本会使用：

- parser artifacts：`rtl/parser_pipeline_rtl`
- Knowledge IR：`rtl/knowledge_ir/<top_module>`
- Manual Context：`rtl/manual_context/<top_module>`

如果用户以普通源码仓库运行，且 parser artifacts 位于 `<project_root>/parser_pipeline_rtl`，则输出为：

- `<project_root>/knowledge_ir/<top_module>`
- `<project_root>/manual_context/<top_module>`

## Parser Tool

入口脚本：

```bash
python backend/skills/catalog/rtl-manual-generation/scripts/run_parser_tool.py \
  --project-root ./rtl \
  --rtl-inputs rtl
```

底层命令：

```bash
python -m parser.pipeline build \
  --inputs <rtl_inputs> \
  --output parser_pipeline_rtl
```

主要输出：

- `project_index.json`
- `build_report.json`
- `modules/*.json`
- `components/*.json`

parser artifacts 是后续 Knowledge IR 的结构事实来源。

## Knowledge Pipeline

入口脚本：

```bash
python backend/skills/catalog/rtl-manual-generation/scripts/run_knowledge_tool.py \
  --project-root ./rtl \
  --top-module arm_soc_top
```

可选参数：

- `--no-enrich`：跳过 Semantic Layer，只生成确定性 Knowledge IR、AI Context 和 Manual Context。
- `--enrich-modules execute,lsu,fetch`：兼容旧参数，映射到 Semantic Layer 的模块选择。
- `--max-flows-per-module 3`：限制每个模块生成 flow claims 的数量。
- `--semantic-model` / `--semantic-base-url` / `--semantic-api-key`：传入 OpenAI-compatible LLM 配置。

## Knowledge IR

作用：从 parser artifacts 生成确定性事实层，不调用 LLM。

独立命令：

```bash
python -m knowledge.knowledge_ir \
  --artifacts-root rtl/parser_pipeline_rtl \
  --top-module arm_soc_top \
  --output-root rtl/knowledge_ir
```

主要输出：

- `rtl/knowledge_ir/<top_module>/manifest.json`
- `rtl/knowledge_ir/<top_module>/project.json`
- `rtl/knowledge_ir/<top_module>/modules/*.json`

模块事实 JSON 主要包含：

- `interface`
- `interface_data_contract`
- `internal_event_flow`
- `assignment_facts`
- `key_instances`
- `component_families`
- `evidence_gaps`

这一层是确定性事实权威。

## AI Context

作用：把 Knowledge IR 压缩成 LLM 更容易消费的上下文。它不是权威事实源。

独立命令：

```bash
python -m knowledge.ai_context \
  --knowledge-dir rtl/knowledge_ir/<top_module> \
  --parser-artifacts-root rtl/parser_pipeline_rtl
```

主要输出：

- `ai_context/index.json`
- `ai_context/modules/<module>.json`
- `ai_context/modules/<module>/flows/<flow_id>.json`

## Semantic Layer

作用：基于 AI Context 生成可审查的语义 claims，不重复确定性事实。

独立命令：

```bash
python -m knowledge.semantic_layer \
  --knowledge-dir rtl/knowledge_ir/<top_module> \
  --modules execute,lsu,fetch \
  --max-flows-per-module 3 \
  --skip-failed
```

semantic claim 类型包括：

- `module_role`
- `structural_responsibility`
- `component_role`
- `assignment_interpretation`
- `interface_intent`
- `flow_intent`
- `data_control_effect`
- `completion_backpressure`
- `documentation_focus`
- `source_review_request`

每条 claim 必须保留：

- `scope`
- `confidence`
- `evidence`
- `doc_priority`
- `requires_rtl_source_review`

## Manual Context

作用：把 Knowledge IR、AI Context、Semantic Layer 和 parser artifacts 组织成最终手册 LLM 的主输入层。

独立命令：

```bash
python -m knowledge.manual_context \
  --knowledge-dir rtl/knowledge_ir/<top_module> \
  --parser-artifacts-root rtl/parser_pipeline_rtl \
  --output-dir rtl/manual_context/<top_module>
```

主要输出：

- `manifest.json`
- `project_context.json`
- `system_topology.json`
- `interface_index.json`
- `flow_index.json`
- `evidence_index.json`
- `validation_report.json`
- `modules/<module>/module_context.json`
- `modules/<module>/interfaces.json`
- `modules/<module>/flows/<flow_id>.json`
- `modules/<module>/gaps.json`

最终代码手册应主要消费这些文件。

## Final Manual Writing Rules

当前后端主流程的最终手册正文应先由 Manual Context 证据边界渲染器生成。不要把自由发挥式 LLM 初稿作为权威正文；LLM 只能消费 Manual Context 中已经带有 `certainty`、`evidence_refs`、`review_status` 的 claim，并且不能把 claim 事实等级升级。

最终手册生成器必须遵守 Manual Context 中的事实等级：

- `deterministic_fact`：可以直接陈述。
- `derived_fact`：必须说明是派生事实。
- `ai_inferred`：必须标注为推断、可能、需要 review，不能写成确定事实。
- `human_asserted`：必须标注为人工断言。
- `evidence_gap`：必须写成证据不足或待审查项。

禁止补写 Manual Context 中没有的：

- 模块、信号、接口、连接。
- flow、跨模块协议、时序保证。
- FSM、always block、寄存器更新条件。

当前 RTL 项目的主要时序/控制模式是 drive-centered event flow。`free` 信号可以记录，但只有当它影响 drive availability 或 backpressure 时才应重点解释。

## Review Checklist

手册生成后必须检查：

- Markdown 正文是否包含寒暄、执行承诺等对话式开场。
- 是否引用不存在的模块、信号、接口或 flow。
- 是否把 AI 推断写成确定事实。
- 是否遗漏 `evidence_gap`、`review_questions` 或 `validation_report` 中的问题。
- 是否编造 FSM、always、寄存器更新或时序保证。
- 是否过度解释 free 信号。
- 是否直接把 legacy Manual IR / ContextPack 当成主结构。

## Legacy Manual IR

`knowledge.manual_ir` 包和旧 split Manual IR / ContextPack 仍保留在代码中，作为历史兼容与回溯参考。

旧入口包括：

```bash
python -m knowledge.manual_ir export ...
python -m knowledge.manual_ir enrich ...
python -m knowledge.manual_ir validate ...
python -m knowledge.manual_ir pack ...
python -m knowledge.manual_ir resolve ...
```

这些入口不再是新手册生成主流程。除非用户明确要求维护 legacy Manual IR，否则不要在旧 `manual_ir` 产物上继续堆新功能。
