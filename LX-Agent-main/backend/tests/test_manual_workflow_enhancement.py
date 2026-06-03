from __future__ import annotations

import json

from backend import manual_workflow
from backend.workflows.rtl_manual import composer


class _FakeMessage:
    content = "# arm_soc_top\n\n[CPU2NoC](arm_soc_top_generated_modules/CPU2NoC.md)\n\nAI 推断\n\n证据不足\n"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def __init__(self):
        self.messages = None

    def create(self, *, model, messages):
        self.messages = messages
        return _FakeResponse()


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def test_source_review_collects_all_flagged_modules_without_twenty_module_cap():
    digest = {
        "top_module": "top",
        "project_context": {"top_level": {"direct_modules": {"value": []}}},
        "modules": [
            {
                "module_name": f"mod_{index:02d}",
                "page_policy": {"detail_level": "compact"},
                "evidence_gaps": [{"reason": f"review mod_{index:02d}"}],
                "source_files": [f"rtl/mod_{index:02d}.v"],
            }
            for index in range(25)
        ],
    }

    targets = manual_workflow._collect_source_review_targets(digest)

    assert len(targets) == 25
    assert targets[0]["module"] == "mod_00"
    assert targets[-1]["module"] == "mod_24"


def test_source_review_ignores_plain_review_questions_without_explicit_flags():
    digest = {
        "top_module": "top",
        "project_context": {"top_level": {"direct_modules": {"value": []}}},
        "modules": [
            {
                "module_name": "plain_question_only",
                "review_questions": [{"question": "human can inspect this later"}],
                "source_files": ["rtl/plain_question_only.v"],
            },
            {
                "module_name": "flagged_module",
                "responsibility": {
                    "short_summary": {
                        "value": "Needs RTL review.",
                        "review_status": "needs_review",
                    }
                },
                "source_files": ["rtl/flagged_module.v"],
            },
        ],
    }

    targets = manual_workflow._collect_source_review_targets(digest)

    assert [target["module"] for target in targets] == ["flagged_module"]


def test_main_manual_polish_receives_manual_context_packet():
    draft = "# arm_soc_top\n\n[CPU2NoC](arm_soc_top_generated_modules/CPU2NoC.md)\n\nAI 推断\n\n证据不足\n"
    packet = {
        "top_module": "arm_soc_top",
        "manual_context_available": True,
        "source_review": {"reviewed_modules": 1, "claim_count": 2},
    }
    client = _FakeClient()

    polished = manual_workflow._polish_manual_with_llm(
        {"top_module": "arm_soc_top", "manual_llm_required": True},
        draft,
        client,
        "test-model",
        packet,
    )

    assert polished == draft.strip()
    user_prompt = client.chat.completions.messages[1]["content"]
    assert "Manual Context 摘要" in user_prompt
    assert '"reviewed_modules": 1' in user_prompt


def test_drive_diagram_packet_uses_ordered_path_and_drive_assignments(tmp_path):
    project_root = tmp_path / "rtl_project"
    manual_context_dir = project_root / "manual_context" / "top"
    flow_dir = manual_context_dir / "modules" / "mod_a" / "flows"
    parser_dir = project_root / "parser_pipeline_rtl" / "modules"
    flow_dir.mkdir(parents=True)
    parser_dir.mkdir(parents=True)

    (flow_dir / "flow_000.json").write_text(
        json.dumps(
            {
                "flow_id": "flow_000",
                "title": "i_drive to o_drive",
                "trigger_event": {"signal": "i_drive"},
                "ordered_path": [
                    {"kind": "input_event", "name": "i_drive"},
                    {
                        "kind": "component",
                        "name": "merge0",
                        "module_type": "cMutexMerge2",
                        "input_drives": ["i_drive", "w_drive_other"],
                        "output_drives": ["w_drive_merge"],
                    },
                    {"kind": "output_event", "name": "o_drive"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (parser_dir / "mod_a.json").write_text(
        json.dumps(
            {
                "assignments": [
                    {
                        "assignment_id": "assign_drive_gate",
                        "lhs_signal": "o_drive",
                        "lhs_terms": ["o_drive"],
                        "rhs": "w_drive_merge & w_drive_enable",
                        "rhs_terms": ["w_drive_merge", "w_drive_enable"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    module = {
        "module_name": "mod_a",
        "interfaces": {
            "event_inputs": ["i_drive"],
            "event_outputs": ["o_drive"],
        },
        "key_drive_flows": [{"source_file": "flows/flow_000.json"}],
    }
    digest = {"manual_context_dir": str(manual_context_dir)}

    packet = manual_workflow._build_drive_diagram_packet(
        {"project_root": str(project_root)},
        digest,
        module,
    )

    assert packet["focus"] == "drive_event_only"
    assert packet["flows"][0]["steps"][1]["instance"] == "merge0"
    assert packet["logic_nodes"][0]["output"] == "o_drive"
    assert packet["logic_nodes"][0]["operator"] == "and"
    assert "w_drive_merge" in packet["logic_nodes"][0]["inputs"]


def test_module_page_renders_drive_only_diagram(tmp_path):
    manual_context_dir = tmp_path / "manual_context" / "top"
    flow_dir = manual_context_dir / "modules" / "mod_b" / "flows"
    flow_dir.mkdir(parents=True)
    (flow_dir / "flow_000.json").write_text(
        json.dumps(
            {
                "flow_id": "flow_000",
                "title": "i_drive to o_drive",
                "ordered_path": [
                    {"kind": "input_event", "name": "i_drive"},
                    {
                        "kind": "component",
                        "name": "fifo0",
                        "module_type": "cFifo1",
                        "input_drives": ["i_drive"],
                        "output_drives": ["o_drive"],
                    },
                    {"kind": "output_event", "name": "o_drive"},
                ],
            }
        ),
        encoding="utf-8",
    )
    module = {
        "module_name": "mod_b",
        "source_files": ["rtl/mod_b.v"],
        "page_policy": {"detail_level": "compact"},
        "system_position": {},
        "port_summary": {},
        "responsibility": {"short_summary": {"value": "test module"}},
        "interfaces": {
            "event_inputs": ["i_drive"],
            "event_outputs": ["o_drive"],
        },
        "key_drive_flows": [{"source_file": "flows/flow_000.json"}],
        "internal_components": {"primary_samples": []},
        "assignment_impact_summary": {"primary_samples": []},
    }

    page = manual_workflow._render_module_page({"manual_context_dir": str(manual_context_dir)}, module)

    assert "## 4. Drive 事件流图" in page
    assert "只展示 drive/event 传递" in page
    assert "i_drive -> [fifo0:cFifo1] -> o_drive -> o_drive" in page
    assert "Payload：" in page


def test_compose_injects_mermaid_drive_diagram_from_manual_context(tmp_path):
    project_root = tmp_path / "rtl_project"
    manual_context_dir = project_root / "manual_context" / "top"
    flow_dir = manual_context_dir / "modules" / "CPU2NoC" / "flows"
    parser_dir = project_root / "parser_pipeline_rtl" / "modules"
    flow_dir.mkdir(parents=True)
    parser_dir.mkdir(parents=True)
    (manual_context_dir / "modules" / "CPU2NoC" / "module_context.json").write_text(
        json.dumps(
            {
                "module_identity": {
                    "module_name": "CPU2NoC",
                    "source_files": ["rtl/CPU2NoC.v"],
                },
                "interface_summary": {
                    "event_inputs": ["i_drvFCPU"],
                    "event_outputs": ["o_drv2CPU"],
                },
                "key_drive_flows": [
                    {"source_file": "flows/flow_000.json", "title": "i_drvFCPU to o_drv2CPU"}
                ],
            }
        ),
        encoding="utf-8",
    )
    (flow_dir / "flow_000.json").write_text(
        json.dumps(
            {
                "flow_id": "flow_000",
                "title": "i_drvFCPU to o_drv2CPU",
                "ordered_path": [
                    {"kind": "input_event", "name": "i_drvFCPU"},
                    {
                        "kind": "component",
                        "name": "cfifo0",
                        "module_type": "cFifo1",
                        "input_drives": ["i_drvFCPU"],
                        "output_drives": ["w_drv"],
                    },
                    {
                        "kind": "component",
                        "name": "cfifoOut",
                        "module_type": "cFifo1",
                        "input_drives": ["w_drv"],
                        "output_drives": ["o_drv2CPU"],
                    },
                    {"kind": "output_event", "name": "o_drv2CPU"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (parser_dir / "CPU2NoC.json").write_text(json.dumps({"assignments": []}), encoding="utf-8")
    markdown = """# 模块 `CPU2NoC`

## 3. Drive/Data/Free 契约

| Interface | 方向 | Event | Payload | Free/backpressure |
| --- | --- | --- | --- | --- |
| `i_drvFCPU` | input | `i_drvFCPU` | - | - |

## 4. 主要 Drive 事件流

文字描述。
"""

    result = composer._inject_compose_drive_diagram(markdown, project_root, "top", "CPU2NoC")

    assert "### 3.1 Drive 事件流图" in result
    assert "```mermaid" in result
    assert 'cmp_cfifo0_cFifo1["cfifo0:cFifo1"]' in result
    assert "sig_i_drvFCPU -->|F1| cmp_cfifo0_cFifo1" in result
    assert result.index("### 3.1 Drive 事件流图") < result.index("## 4. 主要 Drive 事件流")
