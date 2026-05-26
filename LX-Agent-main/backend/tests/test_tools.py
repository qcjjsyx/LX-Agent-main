import unittest
from unittest.mock import patch

from backend import tools


class ToolsTimeoutTest(unittest.TestCase):
    def test_parser_tool_passes_timeout_to_script(self):
        captured = {}

        def fake_run_skill_script(script_name, args, timeout):
            captured["script_name"] = script_name
            captured["args"] = args
            captured["timeout"] = timeout
            return "ok"

        with patch.dict(tools.os.environ, {"RTL_MANUAL_PARSER_TIMEOUT": "300"}, clear=False):
            with patch.object(tools, "run_skill_script", fake_run_skill_script):
                result = tools.run_parser_tool(project_root=".", rtl_inputs="rtl")

        self.assertEqual(result, "ok")
        self.assertEqual(captured["script_name"], "run_parser_tool.py")
        self.assertEqual(captured["timeout"], 330)
        self.assertIn("--timeout", captured["args"])
        timeout_index = captured["args"].index("--timeout")
        self.assertEqual(captured["args"][timeout_index + 1], "300")

    def test_knowledge_tool_passes_timeout_to_script(self):
        captured = {}

        def fake_run_skill_script(script_name, args, timeout):
            captured["script_name"] = script_name
            captured["args"] = args
            captured["timeout"] = timeout
            return "ok"

        with patch.dict(tools.os.environ, {
            "RTL_MANUAL_KNOWLEDGE_TIMEOUT": "1800",
            "RTL_MANUAL_KNOWLEDGE_WRAPPER_TIMEOUT": "1920",
        }, clear=False):
            with patch.object(tools, "run_skill_script", fake_run_skill_script):
                result = tools.run_knowledge_tool(project_root=".", top_module="top")

        self.assertEqual(result, "ok")
        self.assertEqual(captured["script_name"], "run_knowledge_tool.py")
        self.assertEqual(captured["timeout"], 1920)
        self.assertIn("--timeout", captured["args"])
        timeout_index = captured["args"].index("--timeout")
        self.assertEqual(captured["args"][timeout_index + 1], "1800")

    def test_knowledge_tool_force_disables_semantic_cache(self):
        captured = {}

        def fake_run_skill_script(script_name, args, timeout):
            captured["script_name"] = script_name
            captured["args"] = args
            captured["timeout"] = timeout
            return "ok"

        with patch.object(tools, "run_skill_script", fake_run_skill_script):
            result = tools.run_knowledge_tool(project_root=".", top_module="top", force=True)

        self.assertEqual(result, "ok")
        self.assertEqual(captured["script_name"], "run_knowledge_tool.py")
        self.assertIn("--no-semantic-cache", captured["args"])


if __name__ == "__main__":
    unittest.main()
