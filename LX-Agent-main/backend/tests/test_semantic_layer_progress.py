from __future__ import annotations

import json
from pathlib import Path

from backend.tests.module_loader import load_semantic_layer


semantic_layer = load_semantic_layer()


MODULE_RESPONSE = """[MODULE_ROLE]
summary: 模块语义说明
confidence: high
evidence: ai_context/modules/{module}.json@compact_context
"""

FLOW_RESPONSE = """[FLOW_INTENT]
summary: flow 语义说明
confidence: high
evidence: ai_context/modules/{module}/flows/{flow}.json@compact_context.flow
"""


class FakeSemanticLLM:
    model = "deepseek-v4-flash"

    def __init__(self):
        self.calls = []

    def complete_text(self, messages):
        prompt = messages[-1]["content"]
        self.calls.append(prompt)
        if "flow f1" in prompt:
            return FLOW_RESPONSE.format(module="m1", flow="f1")
        if "module m2" in prompt:
            return MODULE_RESPONSE.format(module="m2")
        return MODULE_RESPONSE.format(module="m1")


def test_semantic_layer_writes_progress_log(tmp_path):
    root = make_knowledge_root(tmp_path)
    client = FakeSemanticLLM()

    report = semantic_layer.enrich_semantic_layer(
        root,
        include_flows=True,
        max_workers=2,
        llm_client=client,
    )

    progress_path = root / "semantic" / "semantic_progress.jsonl"
    progress_events = [
        json.loads(line)
        for line in progress_path.read_text(encoding="utf-8").splitlines()
    ]
    index = semantic_layer.read_json(root / "semantic" / "index.json")

    assert report["status"] == "passed"
    assert report["workers"] == 2
    assert report["progress_log"] == str(progress_path)
    assert report["count"]["modules"] == 2
    assert report["count"]["flows"] == 1
    assert len(client.calls) == 3
    assert index["files"]["progress_log"] == "semantic/semantic_progress.jsonl"
    assert progress_events[0]["event_type"] == "semantic_layer_start"
    assert progress_events[-1]["event_type"] == "semantic_layer_end"
    assert count_events(progress_events, "semantic_task_start") == 3
    assert count_events(progress_events, "semantic_task_end") == 3
    assert progress_events[-1]["claims"] == 3


def test_cached_semantic_card_is_reused_and_logged(tmp_path):
    root = make_knowledge_root(tmp_path, include_flow=False)
    context = semantic_layer.read_json(root / "ai_context/modules/m1.json")
    cached = semantic_layer.parse_module_semantic_card(
        MODULE_RESPONSE.format(module="m1"),
        context,
    )
    semantic_layer.write_json(root / "semantic/modules/m1.json", cached)

    report = semantic_layer.enrich_semantic_layer(
        root,
        modules=["m1"],
        include_flows=False,
        max_workers=1,
        llm_client=FakeSemanticLLM(),
    )

    progress_path = Path(report["progress_log"])
    events = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()]
    task_end = [event for event in events if event["event_type"] == "semantic_task_end"][0]

    assert report["count"]["skipped_modules"] == 1
    assert task_end["skipped"] is True
    assert task_end["status"] == "success"


def make_knowledge_root(tmp_path: Path, *, include_flow: bool = True) -> Path:
    root = tmp_path / "knowledge_ir" / "top"
    semantic_layer.write_json(root / "manifest.json", {
        "schema": "knowledge_ir_manifest",
        "top_module": "top",
        "files": {},
        "counts": {},
    })
    semantic_layer.write_json(root / "ai_context/modules/m1.json", module_context("m1"))
    semantic_layer.write_json(root / "ai_context/modules/m2.json", module_context("m2"))

    flow_files = {}
    if include_flow:
        flow_rel = "ai_context/modules/m1/flows/f1.json"
        flow_files["m1"] = [flow_rel]
        semantic_layer.write_json(root / flow_rel, {
            "top_module": "top",
            "module": "m1",
            "flow_id": "f1",
            "source": {},
            "evidence_index": [],
        })

    semantic_layer.write_json(root / "ai_context/index.json", {
        "top_module": "top",
        "files": {
            "modules": {
                "m1": "ai_context/modules/m1.json",
                "m2": "ai_context/modules/m2.json",
            },
            "flows": flow_files,
        },
    })
    return root


def module_context(module_name: str) -> dict:
    return {
        "top_module": "top",
        "module": module_name,
        "source": {},
        "evidence_index": [],
    }


def count_events(events: list[dict], event_type: str) -> int:
    return sum(1 for event in events if event.get("event_type") == event_type)
