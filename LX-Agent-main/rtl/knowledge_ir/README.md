# Knowledge IR 产物命令行说明

本文档说明 RTL 手册生成上下文链路中的四类产物如何生成和使用。

默认从仓库根目录执行：

```bash
cd /Users/huangyuan/qcjjsyx/AI_Agent/LX-Agent-main/LX-Agent-main
export PYTHONPATH=backend/skills/catalog/rtl-manual-generation/packages
```

当前示例使用：

```bash
export TOP_MODULE=arm_soc_top
export PARSER_ROOT=rtl/parser_pipeline_rtl
export KNOWLEDGE_DIR=rtl/knowledge_ir/$TOP_MODULE
export MANUAL_CONTEXT_DIR=rtl/manual_context/$TOP_MODULE
```

## 1. 确定性 Knowledge IR

作用：从 parser 产物生成确定性事实层。这里不调用 LLM。

输入：

- `rtl/parser_pipeline_rtl/project_index.json`
- `rtl/parser_pipeline_rtl/modules/*.json`
- `rtl/parser_pipeline_rtl/components/*.json`

命令：

```bash
python -m knowledge.knowledge_ir \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --output-root rtl/knowledge_ir
```

主要输出：

- `rtl/knowledge_ir/$TOP_MODULE/manifest.json`
- `rtl/knowledge_ir/$TOP_MODULE/project.json`
- `rtl/knowledge_ir/$TOP_MODULE/modules/*.json`

模块事实 JSON 主要包含：

- `interface`
- `interface_data_contract`
- `internal_event_flow`
- `assignment_facts`
- `key_instances`
- `component_families`
- `evidence_gaps`

默认会重建 `rtl/knowledge_ir/$TOP_MODULE/`。如果想保留已有文件，可加：

```bash
python -m knowledge.knowledge_ir \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --output-root rtl/knowledge_ir \
  --no-clean
```

## 2. AI Context

作用：把确定性 Knowledge IR 压缩成 LLM 更容易消费的上下文。这里仍然不调用 LLM。

前置条件：已经生成第 1 步的 `rtl/knowledge_ir/$TOP_MODULE/manifest.json`。

命令：

```bash
python -m knowledge.ai_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT"
```

主要输出：

- `rtl/knowledge_ir/$TOP_MODULE/ai_context/index.json`
- `rtl/knowledge_ir/$TOP_MODULE/ai_context/modules/<module>.json`
- `rtl/knowledge_ir/$TOP_MODULE/ai_context/modules/<module>/flows/<flow_id>.json`

使用方式：

- module context 用于判断模块结构性职责、接口分组、关键组件和 assign 影响。
- flow context 用于单独解释一条 drive-centered flow。
- `ai_context` 是 LLM 输入视图，不是权威事实源；权威事实仍然是 `modules/*.json`。

默认会重建 `ai_context/`。如果想保留已有文件，可加：

```bash
python -m knowledge.ai_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT" \
  --no-clean
```

## 3. Semantic Layer

作用：调用 LLM，从 `ai_context` 生成可审查的语义 claim。它不应该重复端口、实例、flow step 等确定性事实。

前置条件：

- 已经生成第 1 步 Knowledge IR。
- 已经生成第 2 步 AI Context。
- 已配置 OpenAI-compatible LLM key。

可用环境变量：

```bash
export KNOWLEDGE_IR_API_KEY=<your_api_key>
export KNOWLEDGE_IR_BASE_URL=https://api.deepseek.com
export KNOWLEDGE_IR_SEMANTIC_MODEL=deepseek-chat
```

也可以通过命令行传入：

```bash
python -m knowledge.semantic_layer \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --model deepseek-chat \
  --base-url https://api.deepseek.com \
  --api-key <your_api_key>
```

推荐先小范围运行：

```bash
python -m knowledge.semantic_layer \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --modules execute,lsu,fetch \
  --max-flows-per-module 3 \
  --skip-failed
```

只生成模块级语义，不生成 flow 语义：

```bash
python -m knowledge.semantic_layer \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --modules execute,lsu,fetch \
  --no-flows \
  --skip-failed
```

只检查计划，不调用 LLM：

```bash
python -m knowledge.semantic_layer \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --modules execute \
  --max-flows-per-module 1 \
  --dry-run
```

主要输出：

- `rtl/knowledge_ir/$TOP_MODULE/semantic/index.json`
- `rtl/knowledge_ir/$TOP_MODULE/semantic/semantic_report.json`
- `rtl/knowledge_ir/$TOP_MODULE/semantic/modules/<module>.json`
- `rtl/knowledge_ir/$TOP_MODULE/semantic/flows/<module>/<flow_id>.json`

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

每条 claim 都应带：

- `scope`
- `confidence`
- `evidence`
- `doc_priority`
- `requires_rtl_source_review`

## 4. Manual Context

作用：把 `Knowledge IR`、`AI Context`、可选的 `Semantic Layer` 和 parser artifacts 组织成最终代码手册 LLM 可直接消费的页面级上下文。

前置条件：

- 已经生成第 1 步 Knowledge IR。
- 建议已经生成第 2 步 AI Context。
- 如果希望手册包含 AI 语义解释，建议已经生成第 3 步 Semantic Layer。

命令：

```bash
python -m knowledge.manual_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT"
```

指定输出目录：

```bash
python -m knowledge.manual_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT" \
  --output-dir "$MANUAL_CONTEXT_DIR"
```

不消费 Semantic Layer，只基于确定性事实和 AI Context 生成：

```bash
python -m knowledge.manual_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT" \
  --no-semantic
```

主要输出：

- `rtl/manual_context/$TOP_MODULE/manifest.json`
- `rtl/manual_context/$TOP_MODULE/project_context.json`
- `rtl/manual_context/$TOP_MODULE/system_topology.json`
- `rtl/manual_context/$TOP_MODULE/interface_index.json`
- `rtl/manual_context/$TOP_MODULE/flow_index.json`
- `rtl/manual_context/$TOP_MODULE/evidence_index.json`
- `rtl/manual_context/$TOP_MODULE/validation_report.json`
- `rtl/manual_context/$TOP_MODULE/modules/<module>/module_context.json`
- `rtl/manual_context/$TOP_MODULE/modules/<module>/interfaces.json`
- `rtl/manual_context/$TOP_MODULE/modules/<module>/flows/<flow_id>.json`
- `rtl/manual_context/$TOP_MODULE/modules/<module>/gaps.json`

`Manual Context` 是推荐给最终手册生成 LLM 的主输入层。它保留字段级 `certainty`、`source_layers`、`evidence_refs` 和 `review_status`，用于区分确定性事实、派生事实、AI 推断和证据不足。

## 5. 一键四阶段流水线

作用：从 parser 产物出发，依次运行：

1. `knowledge.knowledge_ir`
2. `knowledge.ai_context`
3. `knowledge.semantic_layer`
4. `knowledge.manual_context`

命令：

```bash
python -m knowledge.pipeline \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --knowledge-output-root rtl/knowledge_ir \
  --manual-context-output-root rtl/manual_context \
  --skip-failed-semantic
```

如果只想先对部分模块运行 Semantic Layer：

```bash
python -m knowledge.pipeline \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --knowledge-output-root rtl/knowledge_ir \
  --manual-context-output-root rtl/manual_context \
  --semantic-modules execute,lsu,fetch \
  --max-flows-per-module 3 \
  --skip-failed-semantic
```

传入 LLM 配置：

```bash
python -m knowledge.pipeline \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --knowledge-output-root rtl/knowledge_ir \
  --manual-context-output-root rtl/manual_context \
  --semantic-model deepseek-chat \
  --semantic-base-url https://api.deepseek.com \
  --semantic-api-key <your_api_key> \
  --skip-failed-semantic
```

调试时可以跳过 Semantic Layer：

```bash
python -m knowledge.pipeline \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --knowledge-output-root rtl/knowledge_ir \
  --manual-context-output-root rtl/manual_context \
  --skip-semantic
```

注意：`--skip-semantic` 只会生成确定性 `Knowledge IR`、`AI Context` 和 `Manual Context`，不会生成完整四产物链路。

默认输出：

- `rtl/knowledge_ir/$TOP_MODULE/`
- `rtl/knowledge_ir/$TOP_MODULE/ai_context/`
- `rtl/knowledge_ir/$TOP_MODULE/semantic/`
- `rtl/manual_context/$TOP_MODULE/`

## 推荐完整顺序

```bash
cd /Users/huangyuan/qcjjsyx/AI_Agent/LX-Agent-main/LX-Agent-main
export PYTHONPATH=backend/skills/catalog/rtl-manual-generation/packages
export TOP_MODULE=arm_soc_top
export PARSER_ROOT=rtl/parser_pipeline_rtl
export KNOWLEDGE_DIR=rtl/knowledge_ir/$TOP_MODULE
export MANUAL_CONTEXT_DIR=rtl/manual_context/$TOP_MODULE

python -m knowledge.knowledge_ir \
  --artifacts-root "$PARSER_ROOT" \
  --top-module "$TOP_MODULE" \
  --output-root rtl/knowledge_ir

python -m knowledge.ai_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT"

python -m knowledge.semantic_layer \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --modules execute,lsu,fetch \
  --max-flows-per-module 3 \
  --skip-failed

python -m knowledge.manual_context \
  --knowledge-dir "$KNOWLEDGE_DIR" \
  --parser-artifacts-root "$PARSER_ROOT" \
  --output-dir "$MANUAL_CONTEXT_DIR"
```

## 产物边界

- `modules/*.json`：确定性事实层，后续手册生成应把它作为事实权威。
- `ai_context/*`：给 LLM 的压缩输入，不作为最终证据权威。
- `semantic/*`：LLM 语义 claim 层，只存解释、意图、文档重点和证据不足，不存重复事实。
- `manual_context/*`：最终手册 LLM 的主输入层，按 system/module/flow/interface 页面组织事实、语义 claim 和证据引用。
