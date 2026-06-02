---
name: rtl-manual-generation
description: Generate structured code manuals for RTL or source-code projects using parser artifacts, Knowledge IR, AI Context, Semantic Layer claims, and Manual Context. Use when the user asks to generate a code manual, module manual, project manual, documentation from RTL, parser output, knowledge output, Knowledge IR, Semantic Layer, Manual Context, or legacy Manual IR artifacts.
---

# RTL Manual Generation

Use this skill to generate a structured Markdown manual for RTL or source-code projects. Do not summarize RTL directly when parser and Manual Context artifacts are available; use the generated evidence chain.

## Core Rules

1. Do not inspect parser or knowledge implementation files unless the user explicitly asks to analyze or modify those tools.
2. Treat `scripts/run_parser_tool.py` and `scripts/run_knowledge_tool.py` as skill-owned implementation scripts.
3. Use the exposed tools `run_parser_tool` and `run_knowledge_tool`; `run_knowledge_tool` is now a compatibility wrapper around `python -m knowledge.pipeline`.
4. Base final manuals on `manual_context/<top_module>` evidence, especially `project_context.json`, module `module_context.json`, `module_doc_card.json`, `interfaces.json`, `flows/*.json`, and `evidence_index.json`.
5. Treat legacy `manual_ir/<top_module>` and ContextPack artifacts as legacy only. Do not use them as the main structure for new manuals.
6. Clearly mark evidence gaps as insufficient evidence instead of guessing.
7. Controlled RTL source review is allowed only through Manual Context `source_review_context` and only for port grouping, one-line module purpose hints, or reviewing evidence gaps. It must not introduce new connections, flows, FSM behavior, always-block behavior, register updates, timing guarantees, or deterministic design intent.

## Workflow

1. Read available reference files listed by the skill metadata.
2. Summarize the parser tool, knowledge pipeline, inputs, outputs, and evidence boundary.
3. If `project_root` is missing, use `.`.
4. If the user says the test files are RTL but does not provide `rtl_inputs`, use `rtl`.
5. If `top_module` is missing, ask the user for it before running the knowledge pipeline.
6. Run `run_parser_tool(project_root, rtl_inputs)` when parser artifacts are missing or regeneration is requested.
7. Run `run_knowledge_tool(project_root, top_module, enrich=True)` to execute:
   `parser_pipeline_rtl -> knowledge_ir -> ai_context -> semantic_layer -> manual_context`.
8. Semantic Layer is the default AI claim stage. Disable it only when the user asks for a deterministic-only or fast structural run.
9. Build the main evidence index from `manual_context/<top_module>`.
10. Run the controlled Source Review stage for priority `requires_rtl_source_review`, `review_status=needs_review`, `source_review_request`, and `evidence_gap` items, then write `source_review_claims` and `source_review_report` back to Manual Context.
11. For a complete project manual, use:
    `project_context.json`, `system_topology.json`, `interface_index.json`, `flow_index.json`, `evidence_index.json`, `validation_report.json`, and all reachable `modules/<module>/...` files.
12. Do not make the final manual LLM read parser JSON, Knowledge IR JSON, AI Context JSON, or Semantic Layer JSON broadly. Those layers are only evidence-reference backtrace targets.
13. Plan the manual outline before writing the full manual.
14. Describe what each chapter will contain and which Manual Context evidence supports it.
15. Generate the final Markdown manual with the Manual Context evidence-bound renderer. Do not use a free-form LLM draft as the authoritative manual body.
16. Review the generated manual with the Manual Context checker before relying on any model-assisted review.
17. If the user asks to save it, write the main manual to `docs/manuals/<top_module>_generated.md` and module pages to `docs/manuals/<top_module>_generated_modules/<module>.md`.

## Stage Restart / Regeneration Requests

If the user asks to regenerate, rerun, restart, force, overwrite, or rebuild a specific stage, do not improvise the pipeline manually. Treat it as a workflow-control request handled by `manual_workflow`.

Supported stages:

- `references`
- `parser`
- `knowledge`
- `evidence`
- `source_review`
- `outline`
- `chapter_plan`
- `manual`
- `review`

Expected behavior:

- Restart from the requested stage.
- Force that stage to run even if artifacts already exist.
- Mark downstream stages as stale.
- Continue automatically if the workflow is in auto-run mode or the user requested continuation.
- Do not delete source RTL files.
- Do not invent stage outputs outside the workflow.

Examples:

- "重新生成 parser 阶段"
- "从 knowledge 阶段开始重跑，然后继续"
- "强制重新生成 manual 和 review"
- "rerun source_review and continue"

## Bundled Resources

- `scripts/run_parser_tool.py`: runs the parser pipeline and checks parser artifacts.
- `scripts/run_knowledge_tool.py`: runs Knowledge IR, AI Context, Semantic Layer, and Manual Context through `knowledge.pipeline`.
- `packages/parser/`: parser implementation used by `run_parser_tool.py`.
- `packages/knowledge/`: Knowledge IR, AI Context, Semantic Layer, Manual Context, and legacy Manual IR implementation.
- `packages/tools/`: support package used by parser code.
- `references/skill_script_reference.md`: script and workflow reference for this skill.

The scripts set `PYTHONPATH` to `packages/` before invoking module commands, so use the exposed tools instead of importing these packages from application code.

## CLI Debug Entry

For app-free local debugging, run the layered manual workflow through:

```bash
python -m backend.manual_cli build \
  --project-root ./rtl \
  --rtl-inputs rtl \
  --top-module arm_soc_top

python -m backend.manual_cli compose \
  --project-root ./rtl \
  --top-module arm_soc_top
```

Useful options:

- `build --force`: regenerate parser, knowledge, evidence, outline, chapter plan, and base artifacts.
- `source-review`: run the explicit controlled source-review step only for `evidence_gap`, `needs_review`, or `requires_rtl_source_review` targets, write back Manual Context, and mark enhanced fragments stale.
- `enhance --main-manual`: enhance the whole base main manual as one fragment with a compact Manual Context digest.
- `enhance --target-module <module>`: enhance exactly one base module page.
- `compose`: write the public final manual from valid enhanced fragments, falling back to base when needed.
- `--no-llm`: skip source-review model calls and keep flagged claims as evidence gaps. `enhance` requires a model client.
- `--require-llm`: fail if no OpenAI-compatible API key is configured.
- `--knowledge-timeout 3600`: allow long full Semantic Layer regeneration runs.

## Evidence Boundary

Manual Context is the main input to final manual generation. It preserves field-level `certainty`, `source_layers`, `evidence_refs`, `doc_priority`, `manual_importance`, and `review_status`. The public final manual must not print evidence refs or metadata fields; those belong in the review report. AI wording may only appear as labeled claims already present in Manual Context.

Writing rules:

- `deterministic_fact`: may be stated directly.
- `derived_fact`: must be described as derived from the provided context.
- `ai_inferred`: must be marked as inferred, likely, possible, or review-needed; do not present it as a proven RTL fact.
- `human_asserted`: must be marked as a human assertion when present.
- `evidence_gap`: must be written as insufficient evidence or an explicit review item.

Never add connections, interfaces, flows, timing guarantees, FSM behavior, always-block behavior, or register update conditions that are not present in Manual Context. If a controlled RTL source review slice is used, keep the resulting text labeled as `ai_inferred` or `evidence_gap` unless the same fact is already present as parser/Knowledge IR evidence.

The project’s main event/control pattern is drive-centered. Free signals may be recorded, but final manuals should emphasize them only when they affect drive availability or backpressure.

## Review Checklist

After drafting a manual, review it for:

- conversational preambles or execution promises in the Markdown body;
- nonexistent modules, signals, interfaces, or flows;
- AI inferences promoted to deterministic facts;
- missing evidence gaps or review questions;
- missing module-page coverage for any reachable module;
- sample-only hierarchy or sample-only responsibility tables replacing full hierarchy/module index coverage;
- invented timing, FSM, always-block, or register behavior;
- over-explained free signals that do not affect drive availability or backpressure;
- direct dependence on legacy Manual IR / ContextPack as the main manual structure.
- public manual leakage of `evidence_refs`, `confidence`, `review_status`, `requires_rtl_source_review`, or raw Evidence columns.
- review report coverage of evidence gaps, review questions, and source-review results.

## Required Manual Shape

Use a main manual plus module pages:

- Project overview: one sentence of project purpose, the RTL directory, and the top-level source file only.
- Top module: direct child modules and natural-language external port group summaries, not a raw dump of every port.
- Complete module hierarchy: all hierarchy edges, not a sample.
- Subsystem and module index: every reachable module links to a module page; do not show detail level.
- Do not include a top-level Drive-centered flow index in the main manual; detailed flow text belongs in module pages.
- Do not include evidence gaps, review questions, or evidence-boundary writing rules in the public manual; place them in the review report.

Each module page must include responsibility, hierarchy position, input/output summary, drive/data/free contract, key flows, and internal components/assignment impact. Detailed modules are expanded; helper or leaf modules may use compact cards. Evidence gaps and source-review audit details go to the review report.
