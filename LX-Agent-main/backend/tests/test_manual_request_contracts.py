from __future__ import annotations

from argparse import Namespace

from backend.agent_runner import parse_explicit_workflow_command
from backend.manual_intent import MANUAL_STAGE_ORDER, parse_manual_intent
from backend.manual_planner import build_manual_plan
from backend.workflows.rtl_manual.cli import _select_model
from backend.workflows.rtl_manual.actions import _bool_param


def test_manual_full_regenerate_prompt_plans_forced_pipeline(tmp_path):
    project_root = tmp_path / "rtl_project"
    project_root.mkdir()
    prompt = f"""
请为当前项目全量重新生成 RTL 代码手册。

project_root={project_root}
rtl_inputs=rtl
top_module=arm_soc_top

请自动连续执行。
请强制重新执行 build，重新生成 parser_pipeline_rtl、knowledge_ir、manual_context 和 base 手册。
"""

    intent = parse_manual_intent(prompt)
    plan = build_manual_plan(intent, base_dir=tmp_path)

    assert intent.intent == "rerun_workflow"
    assert intent.rerun_policy == "clean_all_and_run"
    assert intent.top_module == "arm_soc_top"
    assert plan.confirmation_required is False
    assert plan.auto_run is True
    assert plan.start_stage == "references"
    assert plan.force_stages == list(MANUAL_STAGE_ORDER)
    assert plan.semantic_enrichment is True


def test_explicit_workflow_command_normalizes_aliases():
    command = parse_explicit_workflow_command(
        "workflow rtl_manual enhance-main project_root=./rtl top_module=arm_soc_top target-module=cpu_slot"
    )

    assert command == {
        "workflow_id": "rtl_manual",
        "action": "enhance_main",
        "params": {
            "project_root": "./rtl",
            "top_module": "arm_soc_top",
            "target_module": "cpu_slot",
        },
    }


def test_continue_request_uses_previous_stage(tmp_path):
    project_root = tmp_path / "rtl_project"
    project_root.mkdir()
    previous_state = {
        "active": True,
        "stage": "knowledge",
        "project_root": str(project_root),
        "rtl_inputs": "rtl",
        "top_module": "arm_soc_top",
        "auto_run": False,
        "completed_stages": ["references", "parser"],
    }

    intent = parse_manual_intent("继续", previous_state)
    plan = build_manual_plan(intent, previous_state=previous_state, base_dir=tmp_path)

    assert intent.intent == "continue_workflow"
    assert plan.start_stage == "knowledge"
    assert plan.stages == list(MANUAL_STAGE_ORDER[2:])
    assert plan.force_stages == []
    assert plan.auto_run is False


def test_workflow_force_param_parses_web_values():
    assert _bool_param(True) is True
    assert _bool_param("true") is True
    assert _bool_param("force") is True
    assert _bool_param(False) is False
    assert _bool_param("false") is False
    assert _bool_param("") is False


def test_review_commands_default_to_flash_model(monkeypatch):
    for name in (
        "MANUAL_SOURCE_REVIEW_MODEL",
        "MANUAL_REVIEW_MODEL",
        "DEEPSEEK_REVIEW_MODEL",
        "OPENAI_REVIEW_MODEL",
        "MANUAL_ENHANCE_MODEL",
        "DEEPSEEK_MODEL",
        "MANUAL_WORKFLOW_MODEL",
        "MANUAL_IR_ENRICH_MODEL",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    assert _select_model(Namespace(command="source-review", model="")) == "deepseek-v4-flash"
    assert _select_model(Namespace(command="review", model="")) == "deepseek-v4-flash"
    assert _select_model(Namespace(command="compose", model="")) == "deepseek-v4-flash"
    assert _select_model(Namespace(command="enhance", model="")) == "deepseek-v4-pro"
