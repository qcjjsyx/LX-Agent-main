"""Prompts for Manual IR semantic enrichment."""

from __future__ import annotations

import json
from typing import Any, Dict


SEMANTIC_MODULE_CARD_SCHEMA: Dict[str, Any] = {
    "id": "semantic_module:<module_name>",
    "kind": "semantic_module_card",
    "module_name": "<module_name>",
    "top_module": "<top_module>",
    "purpose": {
        "text": "",
        "confidence": "low|medium|high",
        "evidence": [],
    },
    "key_behaviors": [
        {
            "name": "",
            "description": "",
            "signals": [],
            "instances": [],
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "important_signals": [
        {
            "signal": "",
            "role": "",
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "payload_semantics": [],
    "handshake_notes": [],
    "control_flow_notes": [],
    "state_or_register_behavior": [],
    "evidence_gaps": [],
    "input_hash": "<filled_by_tool>",
}


def build_module_enrichment_messages(context: Dict[str, Any]) -> list[Dict[str, str]]:
    """Return chat messages for a module-level semantic card request."""

    schema_text = json.dumps(SEMANTIC_MODULE_CARD_SCHEMA, ensure_ascii=False, indent=2)
    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    module_name = context.get("module_name", "")

    system_prompt = (
        "You are an RTL/Verilog semantic enrichment engine for a Manual IR layer. "
        "You do not write user-facing manuals. You only return one strict JSON object. "
        "Every semantic conclusion must be grounded in the supplied parser artifacts, "
        "Manual IR objects, or RTL source excerpt. Use confidence high, medium, or low. "
        "If evidence is missing or ambiguous, put that issue in evidence_gaps instead "
        "of guessing. Do not invent modules, signals, state machines, registers, "
        "pipeline stages, opcodes, exceptions, jumps, memory behavior, or writeback "
        "behavior unless the provided evidence supports it."
    )

    user_prompt = (
        f"Build a semantic_module_card JSON object for module {module_name}.\n\n"
        "Required output rules:\n"
        "- Output JSON only. No Markdown, no code fence, no prose outside JSON.\n"
        "- Preserve the schema shape shown below.\n"
        "- Use id `semantic_module:<module_name>` and kind `semantic_module_card`.\n"
        "- Each claim object in purpose, key_behaviors, important_signals, "
        "payload_semantics, handshake_notes, control_flow_notes, and "
        "state_or_register_behavior must include confidence and non-empty evidence.\n"
        "- Evidence entries should identify parser JSON paths, Manual IR object ids, "
        "or RTL file/line ranges from the provided excerpt.\n"
        "- Put unsupported but useful questions in evidence_gaps.\n\n"
        "Schema:\n"
        f"{schema_text}\n\n"
        "Input evidence context:\n"
        f"{context_text}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
