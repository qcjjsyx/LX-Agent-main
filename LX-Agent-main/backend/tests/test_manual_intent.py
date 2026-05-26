import unittest
from pathlib import Path

from backend.manual_intent import MANUAL_STAGE_ORDER, parse_manual_intent
from backend.manual_planner import build_manual_plan
from backend.manual_workflow import should_handle_manual_workflow


def make_state(stage="knowledge"):
    return {
        "active": True,
        "stage": stage,
        "project_root": ".",
        "rtl_inputs": "rtl",
        "top_module": "arm_soc_top",
        "audience": "newcomer",
        "evidence_mode": "project",
        "auto_run": True,
        "completed_stages": [],
    }


class ManualIntentPlannerTest(unittest.TestCase):
    def build_plan(self, text, state=None):
        intent = parse_manual_intent(text, state)
        plan = build_manual_plan(intent, state, Path("."))
        return intent, plan

    def test_rerun_from_source_review_forces_downstream(self):
        intent, plan = self.build_plan(
            "从 source_review 阶段开始重跑，然后继续后续步骤",
            make_state("done"),
        )

        self.assertEqual(intent.start_stage, "source_review")
        self.assertEqual(intent.rerun_policy, "force_from_stage")
        self.assertEqual(
            plan.force_stages,
            ["source_review", "outline", "chapter_plan", "manual", "review"],
        )

    def test_rerun_from_references_forces_all_stages(self):
        intent, plan = self.build_plan(
            "从 references 阶段开始重跑，强制重新生成所有阶段",
            make_state("done"),
        )

        self.assertEqual(intent.start_stage, "references")
        self.assertIn(intent.rerun_policy, {"force_from_stage", "clean_all_and_run"})
        self.assertEqual(plan.force_stages, list(MANUAL_STAGE_ORDER))

    def test_from_scratch_without_reuse_is_clean_all(self):
        intent, plan = self.build_plan(
            "从头再跑一遍，不要复用旧结果",
            make_state("done"),
        )

        self.assertEqual(intent.start_stage, "references")
        self.assertEqual(intent.rerun_policy, "clean_all_and_run")
        self.assertEqual(plan.force_stages, list(MANUAL_STAGE_ORDER))

    def test_regenerate_final_manual_is_manual_only(self):
        intent, plan = self.build_plan("重新生成最终手册", make_state("done"))

        self.assertEqual(intent.start_stage, "manual")
        self.assertEqual(intent.rerun_policy, "manual_only")
        self.assertEqual(plan.force_stages, ["manual", "review"])

    def test_only_generate_markdown_body_is_manual_only(self):
        intent, plan = self.build_plan("只生成 Markdown 正文", make_state("done"))

        self.assertEqual(intent.start_stage, "manual")
        self.assertEqual(intent.rerun_policy, "manual_only")
        self.assertEqual(plan.force_stages, ["manual", "review"])

    def test_generate_manual_does_not_force_manual_stage(self):
        intent, plan = self.build_plan(
            "生成代码手册 project_root=. rtl_inputs=rtl top_module=arm_soc_top 自动完整跑完",
            None,
        )

        self.assertEqual(intent.intent, "generate_manual")
        self.assertEqual(plan.start_stage, "references")
        self.assertTrue(plan.auto_run)
        self.assertEqual(plan.force_stages, [])

    def test_continue_uses_previous_stage_without_forcing(self):
        intent, plan = self.build_plan("继续", make_state("knowledge"))

        self.assertEqual(intent.intent, "continue_workflow")
        self.assertEqual(plan.start_stage, "knowledge")
        self.assertEqual(plan.force_stages, [])

    def test_continue_and_full_rerun_requires_confirmation(self):
        intent, plan = self.build_plan("继续，但全量重来", make_state("knowledge"))

        self.assertTrue(intent.confirmation_required)
        self.assertTrue(intent.conflicts)
        self.assertTrue(plan.confirmation_required)
        self.assertEqual(plan.stages, [])

    def test_no_reuse_without_start_stage_requires_confirmation(self):
        intent, plan = self.build_plan("不要复用旧结果", None)

        self.assertTrue(intent.confirmation_required)
        self.assertTrue(plan.confirmation_required)
        self.assertEqual(plan.stages, [])

    def test_source_review_with_space_is_one_stage(self):
        intent, plan = self.build_plan("从 source review 开始重跑", make_state("done"))

        self.assertEqual(intent.start_stage, "source_review")
        self.assertEqual(plan.start_stage, "source_review")

    def test_rerun_from_review_forces_only_review(self):
        intent, plan = self.build_plan("从 review 开始重跑", make_state("done"))

        self.assertEqual(intent.start_stage, "review")
        self.assertEqual(plan.force_stages, ["review"])

    def test_done_state_rerun_request_routes_to_manual_workflow(self):
        self.assertTrue(
            should_handle_manual_workflow(
                "请从 source_review 阶段开始重跑",
                make_state("done"),
            )
        )

    def test_bare_module_name_is_preserved_for_awaiting_top_module(self):
        state = make_state("awaiting_top_module")
        state["top_module"] = ""

        intent, plan = self.build_plan("arm_soc_top", state)

        self.assertEqual(intent.top_module, "arm_soc_top")
        self.assertEqual(plan.top_module, "arm_soc_top")

    def test_audience_text_preserves_reading_path_evidence_mode(self):
        intent, plan = self.build_plan(
            "生成代码手册 project_root=. rtl_inputs=rtl top_module=arm_soc_top 新读者指南",
            None,
        )

        self.assertEqual(intent.evidence_mode, "reading_path")
        self.assertEqual(plan.audience, "newcomer")
        self.assertEqual(plan.evidence_mode, "reading_path")

    def test_manual_generation_mode_explicit_llm_polish_is_planned(self):
        intent, plan = self.build_plan(
            "manual_generation_mode=llm_polish 重新生成最终手册",
            make_state("done"),
        )

        self.assertEqual(intent.manual_generation_mode, "llm_polish")
        self.assertEqual(plan.manual_generation_mode, "llm_polish")
        self.assertEqual(plan.start_stage, "manual")
        self.assertEqual(plan.force_stages, ["manual", "review"])
        self.assertTrue(should_handle_manual_workflow("manual_generation_mode=llm_polish 重新生成最终手册", make_state("done")))

    def test_manual_generation_mode_natural_deterministic_is_planned(self):
        intent, plan = self.build_plan(
            "不用 LLM 润色，确定性生成手册",
            make_state("manual"),
        )

        self.assertEqual(intent.manual_generation_mode, "deterministic")
        self.assertEqual(plan.manual_generation_mode, "deterministic")

    def test_manual_generation_mode_section_with_page_polish_is_planned(self):
        intent, plan = self.build_plan(
            "用 LLM 生成章节内容，并润色模块页 llm_module_page_scope=allowlist llm_module_page_limit=3 llm_module_page_allowlist=top,child",
            make_state("manual"),
        )

        self.assertEqual(intent.manual_generation_mode, "llm_section_generate_with_page_polish")
        self.assertEqual(plan.manual_generation_mode, "llm_section_generate_with_page_polish")
        self.assertEqual(plan.llm_module_page_scope, "allowlist")
        self.assertEqual(plan.llm_module_page_limit, 3)
        self.assertEqual(plan.llm_module_page_allowlist, "top,child")

    def test_manual_generation_mode_section_generation_natural_language(self):
        intent, plan = self.build_plan(
            "章节内容用 LLM 生成，重新生成最终手册",
            make_state("done"),
        )

        self.assertEqual(intent.manual_generation_mode, "llm_section_generate")
        self.assertEqual(plan.manual_generation_mode, "llm_section_generate")


if __name__ == "__main__":
    unittest.main()
