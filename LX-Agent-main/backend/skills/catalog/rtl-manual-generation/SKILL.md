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
4. Base final manuals on `manual_context/<top_module>` evidence, especially `project_context.json`, module `module_context.json`, `interfaces.json`, `flows/*.json`, and `evidence_index.json`.
5. Treat legacy `manual_ir/<top_module>` and ContextPack artifacts as legacy only. Do not use them as the main structure for new manuals.
6. Clearly mark evidence gaps as insufficient evidence instead of guessing.

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
10. For a complete project manual, use:
    `project_context.json`, `system_topology.json`, `interface_index.json`, `flow_index.json`, `evidence_index.json`, `validation_report.json`, and selected `modules/<module>/...` files.
11. Do not make the final manual LLM read parser JSON, Knowledge IR JSON, AI Context JSON, or Semantic Layer JSON broadly. Those layers are only evidence-reference backtrace targets.
12. Plan the manual outline before writing the full manual.
13. Describe what each chapter will contain and which Manual Context evidence supports it.
14. Generate the final Markdown manual with the Manual Context evidence-bound renderer. Do not use a free-form LLM draft as the authoritative manual body.
15. Review the generated manual with the Manual Context checker before relying on any model-assisted review.
16. If the user asks to save it, write it to `docs/manuals/<top_module>_generated.md`.

## Bundled Resources

- `scripts/run_parser_tool.py`: runs the parser pipeline and checks parser artifacts.
- `scripts/run_knowledge_tool.py`: runs Knowledge IR, AI Context, Semantic Layer, and Manual Context through `knowledge.pipeline`.
- `packages/parser/`: parser implementation used by `run_parser_tool.py`.
- `packages/knowledge/`: Knowledge IR, AI Context, Semantic Layer, Manual Context, and legacy Manual IR implementation.
- `packages/tools/`: support package used by parser code.
- `references/skill_script_reference.md`: script and workflow reference for this skill.

The scripts set `PYTHONPATH` to `packages/` before invoking module commands, so use the exposed tools instead of importing these packages from application code.

## Evidence Boundary

Manual Context is the main input to final manual generation. It preserves field-level `certainty`, `source_layers`, `evidence_refs`, `doc_priority`, `manual_importance`, and `review_status`. The final manual should be rendered from these fields first; AI wording may only appear as labeled claims already present in Manual Context.

Writing rules:

- `deterministic_fact`: may be stated directly.
- `derived_fact`: must be described as derived from the provided context.
- `ai_inferred`: must be marked as inferred, likely, possible, or review-needed; do not present it as a proven RTL fact.
- `human_asserted`: must be marked as a human assertion when present.
- `evidence_gap`: must be written as insufficient evidence or an explicit review item.

Never add connections, interfaces, flows, timing guarantees, FSM behavior, always-block behavior, or register update conditions that are not present in Manual Context.

The project’s main event/control pattern is drive-centered. Free signals may be recorded, but final manuals should emphasize them only when they affect drive availability or backpressure.

## Review Checklist

After drafting a manual, review it for:

- conversational preambles or execution promises in the Markdown body;
- nonexistent modules, signals, interfaces, or flows;
- AI inferences promoted to deterministic facts;
- missing evidence gaps, review questions, or validation issues;
- invented timing, FSM, always-block, or register behavior;
- over-explained free signals that do not affect drive availability or backpressure;
- direct dependence on legacy Manual IR / ContextPack as the main manual structure.

## Suggested Chapters

Adapt the structure to the evidence instead of forcing every chapter:

- Project overview
- Top module
- Module hierarchy
- Key module responsibilities
- Interfaces and event/data contracts
- Drive-centered flows
- Internal components and assignment impacts
- Backpressure notes where free affects drive availability
- Evidence gaps and review questions
- Maintenance notes
- Evidence boundary
