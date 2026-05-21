import unittest

from backend.skills.registry import score_skills_for_task, select_tool_names_for_task


class SkillRegistryScoringTest(unittest.TestCase):
    def test_python_files_select_python_code_analysis(self):
        tool_names, skill_names, _instructions, _refs = select_tool_names_for_task(
            "Please explain backend/app.py and backend/agent_core.py"
        )

        self.assertIn("python-code-analysis", skill_names)
        self.assertIn("read_file", tool_names)
        self.assertIn("parse_python_code", tool_names)
        self.assertNotIn("rtl-manual-generation", skill_names)

    def test_rtl_manual_request_selects_manual_skill(self):
        tool_names, skill_names, _instructions, _refs = select_tool_names_for_task(
            "Generate an RTL manual for top_module=arm_soc_top"
        )

        self.assertIn("rtl-manual-generation", skill_names)
        self.assertIn("run_parser_tool", tool_names)
        self.assertIn("run_knowledge_tool", tool_names)

    def test_plain_file_read_does_not_trigger_rtl_manual_skill(self):
        tool_names, skill_names, _instructions, _refs = select_tool_names_for_task(
            "read rtl/rtl/Decode/decoder_16.v and summarize it"
        )

        self.assertNotIn("rtl-manual-generation", skill_names)

    def test_score_details_are_stable(self):
        scored = score_skills_for_task("Please explain backend/agent_core.py")
        self.assertEqual(scored[0]["skill"].name, "python-code-analysis")
        self.assertGreater(scored[0]["score"], 0)


if __name__ == "__main__":
    unittest.main()
