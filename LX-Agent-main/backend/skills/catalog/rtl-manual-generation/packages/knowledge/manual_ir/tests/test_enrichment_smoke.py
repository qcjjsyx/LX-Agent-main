from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from knowledge.manual_ir.context_pack import build_context_pack
from knowledge.manual_ir.enrichment import EnrichmentError, enrich_manual_ir


class FakeLLMClient:
    def __init__(self):
        self.messages = []

    def complete_text(self, messages):
        self.messages = messages
        return """[PURPOSE]
text: Accepts fetch payload and drives a decoded event toward launch.
confidence: medium
evidence: modules/decoder.json@interface_summary.signal_groups

[KEY_BEHAVIOR]
name: decode handoff
description: Uses i_driveFromIF and o_driveToLaunch as the event handoff boundary.
signals: i_driveFromIF, o_driveToLaunch
instances:
confidence: medium
evidence: modules/decoder.json@interface.ports

[IMPORTANT_SIGNAL]
signal: i_pcAndIns_64
role: fetch payload carrying PC/instruction bits.
confidence: medium
evidence: rtl/decoder.v:2-8

[PAYLOAD_FIELD_SEMANTIC]
payload: i_pcAndIns_64
fields: instruction and PC payload bits are visible but not decomposed in the fixture
description: Carries fetch payload into decoder.
confidence: low
evidence: rtl/decoder.v:4

[PROCESS_SEMANTIC]
process_id: process:8
kind: always
summary: Registers the output drive when input drive is observed.
reads: i_driveFromIF
writes: drive_q
confidence: medium
evidence: rtl/decoder.v:8-12

[ASSIGN_SEMANTIC]
lhs: o_driveToLaunch
rhs_summary: Driven from drive_q.
role: event output
confidence: medium
evidence: rtl/decoder.v:13
"""


class PartialTaggedLLMClient:
    def complete_text(self, messages):
        return """[KEY_BEHAVIOR]
name: decode handoff
description: Uses the parser-visible event ports as a local handoff.
signals: i_driveFromIF, o_driveToLaunch
confidence: medium
evidence: modules/decoder.json@interface.ports
"""


class EnrichmentSmokeTest(unittest.TestCase):
    def test_enrich_decoder_and_pack_semantic_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parser_root = root / "parser_pipeline_rtl"
            manual_root = root / "manual_ir" / "arm_soc_top"
            _write_fixture(parser_root, manual_root, root)
            fake_client = FakeLLMClient()

            report = enrich_manual_ir(
                manual_root,
                parser_root,
                modules=["decoder"],
                llm_client=fake_client,
            )

            self.assertEqual(report["status"], "passed")
            semantic_path = manual_root / "semantic_module_cards" / "decoder.json"
            self.assertTrue(semantic_path.is_file())

            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            self.assertEqual(semantic["id"], "semantic_module:decoder")
            self.assertEqual(semantic["kind"], "semantic_module_card")
            self.assertTrue(semantic["purpose"]["evidence"])
            self.assertTrue(semantic["input_hash"])
            self.assertTrue(semantic["process_semantics"])
            self.assertTrue(semantic["assign_semantics"])
            self.assertIn("rtl_semantic_slices", fake_client.messages[-1]["content"])

            context_pack = build_context_pack(manual_root, audience="newcomer")
            overlays = context_pack["sections"][0]["semantic_overlays"]
            self.assertEqual([item["id"] for item in overlays], ["semantic_module:decoder"])

    def test_bad_tagged_text_does_not_write_semantic_card(self):
        class BadLLMClient:
            def complete_text(self, messages):
                return "plain text without tags"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parser_root = root / "parser_pipeline_rtl"
            manual_root = root / "manual_ir" / "arm_soc_top"
            _write_fixture(parser_root, manual_root, root)

            with self.assertRaises(EnrichmentError):
                enrich_manual_ir(
                    manual_root,
                    parser_root,
                    modules=["decoder"],
                    llm_client=BadLLMClient(),
                )

            self.assertFalse((manual_root / "semantic_module_cards" / "decoder.json").exists())

    def test_missing_purpose_gets_deterministic_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parser_root = root / "parser_pipeline_rtl"
            manual_root = root / "manual_ir" / "arm_soc_top"
            _write_fixture(parser_root, manual_root, root)
            client = PartialTaggedLLMClient()

            report = enrich_manual_ir(
                manual_root,
                parser_root,
                modules=["decoder"],
                llm_client=client,
            )

            self.assertEqual(report["status"], "passed")
            semantic_path = manual_root / "semantic_module_cards" / "decoder.json"
            self.assertTrue(semantic_path.is_file())
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            self.assertEqual(semantic["purpose"]["confidence"], "low")
            self.assertEqual(semantic["key_behaviors"][0]["name"], "decode handoff")
            self.assertTrue(semantic["evidence_gaps"])


def _write_fixture(parser_root: Path, manual_root: Path, repo_root: Path) -> None:
    (parser_root / "modules").mkdir(parents=True)
    (parser_root / "components").mkdir(parents=True)
    (manual_root / "module_cards").mkdir(parents=True)
    (manual_root / "channel_cards").mkdir(parents=True)
    (manual_root / "component_contracts").mkdir(parents=True)
    (manual_root / "flow_paths").mkdir(parents=True)
    (manual_root / "reading_paths").mkdir(parents=True)
    (repo_root / "rtl").mkdir(parents=True)

    _write_json(
        parser_root / "project_index.json",
        {
            "schema": "parser_pipeline_project_index",
            "repo_root": str(repo_root),
            "top_modules": [{"name": "arm_soc_top", "file": "rtl/arm_soc_top.v", "json_ref": "modules/arm_soc_top.json"}],
            "artifacts": {
                "modules": [{"name": "decoder", "file": "rtl/decoder.v", "json_ref": "modules/decoder.json"}],
                "components": [],
            },
        },
    )
    _write_json(parser_root / "build_report.json", {"schema": "parser_pipeline_build_report"})
    _write_json(
        parser_root / "modules" / "decoder.json",
        {
            "schema": "parser_pipeline_module",
            "name": "decoder",
            "artifact_kind": "module",
            "module_role": "internal",
            "file": "rtl/decoder.v",
            "interface": {
                "ports": [
                    {"name": "i_driveFromIF", "direction": "input", "width_text": "1"},
                    {"name": "o_freeFromIF", "direction": "output", "width_text": "1"},
                    {"name": "i_pcAndIns_64", "direction": "input", "width_text": "[63:0]"},
                    {"name": "o_driveToLaunch", "direction": "output", "width_text": "1"},
                ]
            },
            "local_signals": [],
            "instances": [],
            "transparent_flows": [],
            "interface_summary": {
                "signal_groups": {
                    "event_inputs": ["i_driveFromIF"],
                    "event_outputs": ["o_driveToLaunch"],
                    "payload_inputs": ["i_pcAndIns_64"],
                    "payload_outputs": [],
                    "condition_inputs": [],
                    "condition_outputs": [],
                    "reset_inputs": [],
                    "reset_outputs": [],
                },
                "control_signals": [],
                "backpressure_signals": [],
            },
            "direct_children": {"modules": [], "components": []},
            "flow_graph": {"signals": [], "edges": []},
            "transitive_summary": {"reachable_modules": [], "reachable_components": [], "families_used": []},
            "warnings": [],
        },
    )
    (repo_root / "rtl" / "decoder.v").write_text(
        "module decoder(\n"
        "  input i_driveFromIF,\n"
        "  output o_freeFromIF,\n"
        "  input [63:0] i_pcAndIns_64,\n"
        "  output o_driveToLaunch\n"
        ");\n"
        "reg drive_q;\n"
        "always @(posedge i_driveFromIF) begin\n"
        "  drive_q <= i_driveFromIF;\n"
        "end\n"
        "assign o_driveToLaunch = drive_q;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    _write_json(
        manual_root / "module_cards" / "decoder.json",
        {
            "id": "module:decoder",
            "kind": "module_card",
            "title": "decoder",
            "summary": "deterministic decoder summary",
            "top_module": "arm_soc_top",
            "source_refs": [{"artifact_kind": "module", "artifact_name": "decoder", "json_ref": "modules/decoder.json"}],
            "warnings": [],
            "confidence": "medium",
            "module_name": "decoder",
            "child_components": [],
        },
    )
    _write_json(
        manual_root / "reading_paths" / "reading_newcomer_arm_soc_top.json",
        {
            "id": "reading:newcomer:arm_soc_top",
            "kind": "reading_path",
            "title": "newcomer",
            "summary": "",
            "top_module": "arm_soc_top",
            "audience": "newcomer",
            "goals": [],
            "ordered_sections": [
                {
                    "section_id": "read:newcomer:primary-modules",
                    "title": "Primary Modules",
                    "covers": ["module:decoder"],
                }
            ],
            "must_cover": ["module:decoder"],
            "defer_sections": [],
            "risk_reminders": [],
        },
    )
    _write_json(
        manual_root / "manifest.json",
        {
            "schema": "manual_ir",
            "schema_version": "0.1",
            "top_module": "arm_soc_top",
            "generated_from": {"artifacts_root": str(parser_root), "project_index_ref": "project_index.json"},
            "counts": {
                "system_views": 0,
                "module_cards": 1,
                "channel_cards": 0,
                "component_contracts": 0,
                "flow_paths": 0,
                "reading_paths": 1,
            },
            "files": {
                "system_views": "system_views.json",
                "module_cards": {"decoder": "module_cards/decoder.json"},
                "channel_cards": {},
                "component_contracts": {},
                "flow_paths": {},
                "reading_paths": {"reading:newcomer:arm_soc_top": "reading_paths/reading_newcomer_arm_soc_top.json"},
            },
            "indexes": {
                "by_id": {
                    "module:decoder": "objects.module_cards[0]",
                    "reading:newcomer:arm_soc_top": "objects.reading_paths[0]",
                },
                "by_module": {"decoder": ["module:decoder"]},
                "by_family": {},
                "by_tag": {},
            },
            "warnings": [],
        },
    )
    _write_json(manual_root / "system_views.json", [])


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
