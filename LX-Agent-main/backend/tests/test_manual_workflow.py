import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import manual_cli
from backend import manual_timing
from backend import manual_workflow as mw


class FakeCompletions:
    def create(self, **kwargs):
        payload = {
            "claims": [
                {
                    "subject": "模块职责",
                    "summary": "该模块根据输入驱动信号生成输出驱动响应。",
                    "explanation": "源码切片显示 i_drive 参与输出赋值。",
                    "certainty": "ai_inferred",
                    "signals": ["i_drive", "o_drive"],
                    "instances": [],
                    "source_refs": [{"file": "rtl/rtl/foo.v", "line_start": 1, "line_end": 5}],
                }
            ],
            "open_questions": [],
        }
        message = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())


class FakePolishCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakePolishClient:
    def __init__(self, content):
        self.completions = FakePolishCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeSequencePolishCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        index = len(self.calls) - 1
        content = self.contents[index] if index < len(self.contents) else self.contents[-1]
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeSequencePolishClient:
    def __init__(self, contents):
        self.completions = FakeSequencePolishCompletions(contents)
        self.chat = SimpleNamespace(completions=self.completions)


def make_minimal_manual_context(root):
    manual_context_dir = root / "manual_context" / "top"
    (manual_context_dir / "modules" / "top").mkdir(parents=True)
    (manual_context_dir / "modules" / "child").mkdir(parents=True)

    def write_json(path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    write_json(
        manual_context_dir / "manifest.json",
        {
            "top_module": "top",
            "counts": {"modules": 2},
            "files": {"modules": {"top": {}, "child": {}}},
        },
    )
    write_json(
        manual_context_dir / "project_context.json",
        {
            "top_level": {
                "source_file": "rtl/top.v",
                "direct_modules": {"value": ["child"]},
                "external_port_groups": [],
            },
            "project_purpose": {"value": "top integrates child", "certainty": "deterministic_fact"},
            "major_modules": [{"module": "child"}],
        },
    )
    write_json(
        manual_context_dir / "system_topology.json",
        {
            "module_count": 2,
            "hierarchy_edges": [
                {"parent": "top", "child": "child", "relationship": "instantiates"}
            ],
        },
    )
    write_json(manual_context_dir / "interface_index.json", {"counts": {}, "interfaces": []})
    write_json(manual_context_dir / "flow_index.json", {"counts": {}, "flows": []})
    write_json(manual_context_dir / "evidence_index.json", {"evidence_policy": {}, "evidence": []})
    write_json(manual_context_dir / "validation_report.json", {"status": "ok", "issues": [], "checked_files": []})

    for module_name in ("top", "child"):
        module_dir = manual_context_dir / "modules" / module_name
        write_json(
            module_dir / "module_context.json",
            {
                "module_identity": {
                    "module_name": module_name,
                    "source_files": [f"rtl/{module_name}.v"],
                },
                "system_position": {
                    "parents": {"value": [] if module_name == "top" else ["top"]},
                    "children": {"value": ["child"] if module_name == "top" else []},
                    "component_children": {"value": []},
                },
                "module_responsibility": {
                    "short_summary": {
                        "value": f"{module_name} responsibility",
                        "certainty": "deterministic_fact",
                    }
                },
                "interface_summary": {},
                "internal_components": [],
                "assignment_impact_summary": [],
            },
        )
        write_json(module_dir / "module_doc_card.json", {"page_policy": {"detail_level": "standard"}})
        write_json(module_dir / "interfaces.json", {"interfaces": []})
        write_json(module_dir / "gaps.json", {"gaps": []})

    return manual_context_dir


def make_context_state(root, stage):
    manual_context_dir = make_minimal_manual_context(root)
    return {
        "active": True,
        "stage": stage,
        "project_root": str(root),
        "rtl_inputs": "rtl",
        "top_module": "top",
        "manual_context_dir": str(manual_context_dir),
        "knowledge_dir": str(root / "knowledge_ir" / "top"),
        "evidence_digest": {},
        "outline": [],
        "chapter_plan": [],
        "force_stages": [stage],
    }


def make_page_polish_digest():
    top_module = {
        "module_name": "top",
        "source_files": ["rtl/top.v"],
        "system_position": {"parents": [], "children": ["child"], "component_children": []},
        "port_summary": {"external_port_groups": [{"signals": [{"name": "clk"}, {"name": "rst_n"}]}]},
        "interfaces": {"interface_groups": []},
        "internal_components": {"primary_samples": [{"instance_name": "u_child", "module_type": "child"}]},
        "assignment_impact_summary": {"primary_samples": []},
        "key_drive_flows": [],
        "evidence_gaps": [],
    }
    child_module = {
        "module_name": "child",
        "source_files": ["rtl/child.v"],
        "system_position": {"parents": ["top"], "children": [], "component_children": []},
        "port_summary": {"external_port_groups": [{"signals": [{"name": "i_data"}]}]},
        "interfaces": {"interface_groups": []},
        "internal_components": {"primary_samples": []},
        "assignment_impact_summary": {"primary_samples": []},
        "key_drive_flows": [],
        "evidence_gaps": [],
    }
    other_module = {
        "module_name": "other",
        "source_files": ["rtl/other.v"],
        "system_position": {"parents": [], "children": [], "component_children": []},
        "port_summary": {"external_port_groups": []},
        "interfaces": {"interface_groups": []},
        "internal_components": {"primary_samples": []},
        "assignment_impact_summary": {"primary_samples": []},
        "key_drive_flows": [],
        "evidence_gaps": [],
    }
    return {
        "top_module": "top",
        "project_context": {"top_level": {"direct_modules": {"value": ["child"]}}},
        "modules": [top_module, child_module, other_module],
    }


class ManualWorkflowRenderingTest(unittest.TestCase):
    def test_manual_usage_request_returns_help_without_starting_workflow(self):
        text = "请说明代码手册生成器的使用方式"

        self.assertTrue(mw.should_handle_manual_workflow(text, None))
        reply, state = mw.handle_manual_workflow(
            text,
            None,
            Path("."),
            client=None,
            model=None,
        )

        self.assertIn("代码手册生成器使用说明", reply)
        self.assertIn("project_root", reply)
        self.assertIn("从 knowledge 阶段开始重跑", reply)
        self.assertFalse(state.get("active"))
        self.assertEqual(state.get("stage"), "collect_params")

    def test_manual_stage_reloads_existing_context_when_state_lacks_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manual_context_dir = root / "manual_context" / "top"
            (manual_context_dir / "modules" / "top").mkdir(parents=True)
            (manual_context_dir / "modules" / "child").mkdir(parents=True)

            def write_json(path, payload):
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            write_json(
                manual_context_dir / "manifest.json",
                {
                    "top_module": "top",
                    "counts": {"modules": 2},
                    "files": {"modules": {"top": {}, "child": {}}},
                },
            )
            write_json(
                manual_context_dir / "project_context.json",
                {
                    "top_level": {
                        "source_file": "rtl/top.v",
                        "direct_modules": {"value": ["child"]},
                        "external_port_groups": [],
                    },
                    "project_purpose": {"value": "top integrates child", "certainty": "deterministic_fact"},
                    "major_modules": [{"module": "child"}],
                },
            )
            write_json(
                manual_context_dir / "system_topology.json",
                {
                    "module_count": 2,
                    "hierarchy_edges": [
                        {"parent": "top", "child": "child", "relationship": "instantiates"}
                    ],
                },
            )
            write_json(manual_context_dir / "interface_index.json", {"counts": {}, "interfaces": []})
            write_json(manual_context_dir / "flow_index.json", {"counts": {}, "flows": []})
            write_json(manual_context_dir / "evidence_index.json", {"evidence_policy": {}, "evidence": []})
            write_json(manual_context_dir / "validation_report.json", {"status": "ok", "issues": [], "checked_files": []})

            for module_name in ("top", "child"):
                module_dir = manual_context_dir / "modules" / module_name
                write_json(
                    module_dir / "module_context.json",
                    {
                        "module_identity": {
                            "module_name": module_name,
                            "source_files": [f"rtl/{module_name}.v"],
                        },
                        "system_position": {
                            "parents": {"value": [] if module_name == "top" else ["top"]},
                            "children": {"value": ["child"] if module_name == "top" else []},
                            "component_children": {"value": []},
                        },
                        "module_responsibility": {
                            "short_summary": {
                                "value": f"{module_name} responsibility",
                                "certainty": "deterministic_fact",
                            }
                        },
                        "interface_summary": {},
                        "internal_components": [],
                        "assignment_impact_summary": [],
                    },
                )
                write_json(module_dir / "module_doc_card.json", {"page_policy": {"detail_level": "standard"}})
                write_json(module_dir / "interfaces.json", {"interfaces": []})
                write_json(module_dir / "gaps.json", {"gaps": []})

            state = {
                "active": True,
                "stage": "manual",
                "project_root": str(root),
                "rtl_inputs": "rtl",
                "top_module": "top",
                "manual_context_dir": str(manual_context_dir),
                "knowledge_dir": str(root / "knowledge_ir" / "top"),
                "evidence_digest": {},
                "outline": [],
                "chapter_plan": [],
                "force_stages": ["manual"],
            }

            reply = mw._run_manual_stage(state, client=None, model=None, user_input="")

            self.assertIn("top", state["evidence_digest"]["known_modules"])
            self.assertGreaterEqual(state["manual_module_page_count"], 2)
            self.assertTrue((root / "docs" / "manuals" / "top_generated.md").exists())
            self.assertTrue((root / "docs" / "manuals" / "top_generated_modules" / "child.md").exists())
            self.assertIn("阶段8", reply)

    def test_default_manual_generation_mode_does_not_call_llm(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n\nAI 推断：x\n证据不足：y\n"
        client = FakePolishClient("# should not be used")
        state = {}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft)
        self.assertEqual(state["manual_generation_mode"], "deterministic")
        self.assertEqual(state["manual_llm_polish_status"], "not_requested")
        self.assertEqual(client.completions.calls, [])

    def test_explicit_deterministic_manual_generation_mode_does_not_call_llm(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n"
        client = FakePolishClient("# should not be used")
        state = {"manual_generation_mode": "deterministic"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft)
        self.assertEqual(client.completions.calls, [])

    def test_llm_polish_calls_model_and_returns_valid_markdown(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n\nAI 推断：x\n证据不足：y\n"
        polished = (
            "# top\n\n"
            "这是一版更连贯的主手册。\n\n"
            "[child](top_generated_modules/child.md)\n\n"
            "AI 推断：x\n\n证据不足：y\n"
        )
        client = FakePolishClient(polished)
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, polished.strip())
        self.assertEqual(state["manual_llm_polish_status"], "success")
        self.assertEqual(len(client.completions.calls), 1)
        self.assertEqual(client.completions.calls[0]["model"], "fake-model")

    def test_llm_polish_strips_outer_markdown_fence(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n\nAI 推断：x\n证据不足：y\n"
        polished_body = (
            "# top\n\n"
            "这是一版更连贯的主手册。\n\n"
            "[child](top_generated_modules/child.md)\n\n"
            "AI 推断：x\n\n证据不足：y\n"
        )
        client = FakePolishClient(f"```markdown\n{polished_body}\n```")
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, polished_body.strip())
        self.assertFalse(manual.startswith("```"))
        self.assertEqual(state["manual_llm_polish_status"], "success")

    def test_llm_polish_strips_unclosed_outer_markdown_fence(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n\nAI 推断：x\n证据不足：y\n"
        polished_body = (
            "# top\n\n"
            "这是一版更连贯的主手册。\n\n"
            "[child](top_generated_modules/child.md)\n\n"
            "AI 推断：x\n\n证据不足：y\n"
        )
        client = FakePolishClient(f"```markdown\n{polished_body}")
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, polished_body.strip())
        self.assertFalse(manual.startswith("```"))
        self.assertEqual(state["manual_llm_polish_status"], "success")

    def test_llm_polish_rejects_unbalanced_internal_fence(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n\nAI 推断：x\n证据不足：y\n"
        polished = (
            "# top\n\n"
            "[child](top_generated_modules/child.md)\n\n"
            "```verilog\n"
            "module top;\n"
            "AI 推断：x\n\n证据不足：y\n"
        )
        client = FakePolishClient(polished)
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft)
        self.assertEqual(state["manual_llm_polish_status"], "failed_validation_fallback_to_draft")
        self.assertIn("unbalanced markdown code fences", state["manual_llm_validation_error"])

    def test_llm_polish_model_unavailable_falls_back_to_draft(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n"
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, None, None)

        self.assertEqual(manual, draft)
        self.assertEqual(state["manual_llm_polish_status"], "skipped_model_unavailable")

    def test_llm_polish_validation_failure_falls_back_to_draft(self):
        draft = "# top\n\n[child](top_generated_modules/child.md)\n\nAI 推断：x\n"
        client = FakePolishClient("好的，下面是")
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft)
        self.assertEqual(state["manual_llm_polish_status"], "failed_validation_fallback_to_draft")
        self.assertTrue(state["manual_llm_validation_error"])

    def test_llm_polish_must_keep_all_module_page_links(self):
        draft = (
            "# top\n\n"
            "[foo](top_generated_modules/foo.md)\n"
            "[bar](top_generated_modules/bar.md)\n"
        )
        polished = "# top\n\n[foo](top_generated_modules/foo.md)\n\n只保留了一个链接。\n"
        client = FakePolishClient(polished)
        state = {"manual_generation_mode": "llm_polish"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft)
        self.assertEqual(state["manual_llm_polish_status"], "failed_validation_fallback_to_draft")
        self.assertIn("bar.md", state["manual_llm_validation_error"])

    def test_llm_section_generate_calls_model_per_section(self):
        draft = (
            "# arm_soc_top RTL 代码手册\n\n"
            "front arm_soc_top\n\n"
            "## 项目总览\n\n"
            "[child](modules/child.md)\n\nAI 推断：x\n\n"
            "## 子系统与模块索引\n\n"
            "[foo](modules/foo.md)\n\n证据不足：y\n"
        )
        outputs = [
            "# arm_soc_top RTL 代码手册\n\nfront arm_soc_top polished\n",
            "## 项目总览\n\n[child](modules/child.md)\n\nAI 推断：x\n\n更清晰的描述。\n",
            "## 子系统与模块索引\n\n[foo](modules/foo.md)\n\n证据不足：y\n\n更清晰的描述。\n",
        ]
        client = FakeSequencePolishClient(outputs)
        state = {"manual_generation_mode": "llm_section_generate", "top_module": "arm_soc_top"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertIn("front arm_soc_top polished", manual)
        self.assertEqual(len(client.completions.calls), 3)
        self.assertEqual(
            {item["status"] for item in state["manual_llm_section_status"].values()},
            {"success"},
        )

    def test_llm_section_generate_model_unavailable_falls_back_to_draft(self):
        draft = "# top\n\n## A\n\nbody\n"
        state = {"manual_generation_mode": "llm_section_generate"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, None, None)

        self.assertEqual(manual, draft)
        self.assertEqual(
            state["manual_llm_section_status"]["__all__"]["status"],
            "skipped_model_unavailable",
        )

    def test_llm_section_generate_missing_link_falls_back_for_that_section(self):
        draft = "## 子系统与模块索引\n\n[foo](modules/foo.md)\n\n证据不足：y\n"
        client = FakeSequencePolishClient(["## 子系统与模块索引\n\n证据不足：y\n\n缺少链接。\n"])
        state = {"manual_generation_mode": "llm_section_generate"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft.strip())
        status = state["manual_llm_section_status"]["## 子系统与模块索引"]
        self.assertEqual(status["status"], "failed_validation_fallback_to_draft")
        self.assertIn("foo.md", status["reason"])

    def test_llm_section_generate_conversational_output_falls_back(self):
        draft = "## 项目总览\n\n没有链接的 deterministic section 内容足够长。\n"
        client = FakeSequencePolishClient(["好的，下面是润色后的章节。" + "内容" * 40])
        state = {"manual_generation_mode": "llm_section_generate"}

        with patch.object(mw, "_render_manual_context_markdown", return_value=draft):
            manual = mw._generate_manual_markdown(state, client, "fake-model")

        self.assertEqual(manual, draft.strip())
        status = state["manual_llm_section_status"]["## 项目总览"]
        self.assertEqual(status["status"], "failed_validation_fallback_to_draft")
        self.assertIn("conversational", status["reason"])

    def test_llm_section_generate_with_page_polish_writes_polished_module_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            digest = make_page_polish_digest()
            module = digest["modules"][0]
            draft_page = mw._render_module_page(digest, module)
            polished_page = draft_page + "\n\n润色后说明：保留 clk、rst_n 和 u_child。\n"
            state = {
                "manual_generation_mode": "llm_section_generate_with_page_polish",
                "top_module": "top",
                "evidence_digest": digest,
                "llm_module_page_scope": "top_only",
                "llm_module_page_limit": 20,
            }
            output_path = root / "manual.md"
            client = FakeSequencePolishClient([polished_page])

            paths = mw._write_module_pages(state, output_path, client=client, model="fake-model")

            top_page = output_path.with_name("manual_modules") / "top.md"
            self.assertIn(top_page, paths)
            self.assertIn("润色后说明", top_page.read_text(encoding="utf-8"))
            self.assertEqual(state["manual_llm_page_status"]["top"]["status"], "success")
            self.assertEqual(len(client.completions.calls), 1)

    def test_llm_module_page_missing_port_falls_back_to_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            digest = make_page_polish_digest()
            module = digest["modules"][0]
            draft_page = mw._render_module_page(digest, module)
            bad_page = draft_page.replace("clk", "clock_removed")
            state = {
                "manual_generation_mode": "llm_section_generate_with_page_polish",
                "top_module": "top",
                "evidence_digest": digest,
                "llm_module_page_scope": "top_only",
                "llm_module_page_limit": 20,
            }
            output_path = root / "manual.md"
            client = FakeSequencePolishClient([bad_page])

            mw._write_module_pages(state, output_path, client=client, model="fake-model")

            top_page_text = (output_path.with_name("manual_modules") / "top.md").read_text(encoding="utf-8")
            self.assertEqual(top_page_text.strip(), draft_page)
            self.assertEqual(
                state["manual_llm_page_status"]["top"]["status"],
                "failed_validation_fallback_to_draft",
            )
            self.assertIn("clk", state["manual_llm_page_status"]["top"]["reason"])

    def test_llm_module_page_scope_selection(self):
        digest = make_page_polish_digest()
        modules = digest["modules"]
        base_state = {"top_module": "top", "evidence_digest": digest, "llm_module_page_limit": 20}

        self.assertEqual(
            mw._select_modules_for_llm_page_polish({**base_state, "llm_module_page_scope": "top_only"}, modules),
            {"top"},
        )
        self.assertEqual(
            mw._select_modules_for_llm_page_polish({**base_state, "llm_module_page_scope": "top_and_direct"}, modules),
            {"top", "child"},
        )
        self.assertEqual(
            mw._select_modules_for_llm_page_polish({
                **base_state,
                "llm_module_page_scope": "allowlist",
                "llm_module_page_allowlist": "child,other",
            }, modules),
            {"child", "other"},
        )
        no_direct_state = {
            "top_module": "top",
            "evidence_digest": {"top_module": "top", "project_context": {}, "modules": modules},
            "llm_module_page_scope": "top_and_direct",
            "llm_module_page_limit": 20,
        }
        self.assertEqual(mw._select_modules_for_llm_page_polish(no_direct_state, modules), {"top"})

    def test_no_llm_page_polish_records_skipped_and_uses_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            digest = make_page_polish_digest()
            state = {
                "manual_generation_mode": "llm_section_generate_with_page_polish",
                "top_module": "top",
                "evidence_digest": digest,
                "llm_module_page_scope": "top_only",
                "llm_module_page_limit": 20,
            }
            output_path = root / "manual.md"

            mw._write_module_pages(state, output_path, client=None, model=None)

            self.assertEqual(
                state["manual_llm_page_status"]["top"]["status"],
                "skipped_model_unavailable",
            )
            self.assertTrue((output_path.with_name("manual_modules") / "top.md").exists())

    def test_outline_stage_reloads_existing_context_when_state_lacks_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = make_context_state(root, "outline")

            reply = mw._run_outline_stage(state)

            self.assertIn("child", state["evidence_digest"]["known_modules"])
            self.assertTrue(state["outline"])
            self.assertEqual(state["chapter_plan"], [])
            self.assertEqual(state["stage"], "chapter_plan")
            self.assertIn("阶段6", reply)

    def test_chapter_plan_stage_reloads_existing_context_when_state_lacks_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = make_context_state(root, "chapter_plan")
            state["outline"] = [{"title": "stale", "evidence": []}]

            reply = mw._run_chapter_plan_stage(state)

            self.assertIn("child", state["evidence_digest"]["known_modules"])
            self.assertTrue(state["outline"])
            self.assertNotEqual(state["outline"][0]["title"], "stale")
            self.assertTrue(state["chapter_plan"])
            self.assertEqual(state["stage"], "manual")
            self.assertIn("阶段7", reply)

    def test_source_review_stage_reports_missing_context_without_exception(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = {
                "active": True,
                "stage": "source_review",
                "project_root": str(root),
                "rtl_inputs": "rtl",
                "top_module": "top",
                "manual_context_dir": str(root / "manual_context" / "top"),
                "evidence_digest": {},
            }

            reply = mw._run_source_review_stage(state, client=None, model=None)

            self.assertIn("Manual Context", reply)
            self.assertTrue(state["last_error"])
            self.assertEqual(state["stage"], "source_review")

    def test_public_manual_filters_internal_metadata(self):
        digest = {
            "top_module": "top",
            "project_context": {
                "project_purpose": {
                    "value": "顶层集成模块。",
                    "certainty": "ai_inferred",
                    "confidence": "medium",
                    "review_status": "needs_review",
                    "requires_rtl_source_review": True,
                    "evidence_refs": ["ev:top"],
                },
                "top_level": {
                    "source_file": "rtl/rtl/top.v",
                    "direct_modules": {"value": ["child"], "evidence_refs": ["ev:top"]},
                    "external_port_groups": [
                        {
                            "group": "clock_reset_init",
                            "signals": [{"name": "clk", "direction": "input"}],
                            "direction_counts": {"input": 1},
                            "evidence_refs": ["ev:ports"],
                        }
                    ],
                },
            },
            "system_topology": {
                "module_count": 2,
                "edges": [
                    {
                        "parent": "top",
                        "child": "child",
                        "relationship": "instantiates",
                        "certainty": "deterministic_fact",
                        "evidence_refs": ["ev:edge"],
                    }
                ],
            },
            "modules": [
                {
                    "module_name": "child",
                    "source_files": ["rtl/rtl/child.v"],
                    "page_policy": {"detail_level": "detailed"},
                    "system_position": {"region": {"value": "cpu"}},
                    "responsibility": {
                        "short_summary": {
                            "value": "子模块职责。",
                            "certainty": "ai_inferred",
                            "confidence": "high",
                            "review_status": "ready",
                            "evidence_refs": ["ev:child"],
                        }
                    },
                    "port_summary": {},
                    "interfaces": {"interface_groups": []},
                    "key_drive_flows": [],
                    "internal_components": {"primary_samples": []},
                    "assignment_impact_summary": {"primary_samples": []},
                }
            ],
        }
        state = {"top_module": "top", "_manual_output_stem": "top_generated", "evidence_digest": digest}

        manual = mw._render_manual_context_markdown(state)
        module_page = mw._render_module_page(digest, digest["modules"][0])
        public_text = manual + "\n" + module_page

        for forbidden in (
            "confidence=",
            "review_status",
            "requires_rtl_source_review",
            "| Evidence |",
            "evidence=",
            "evidence_refs",
            "详情级别",
            "关键 Drive-centered Flow 索引",
            "证据缺口与 Review 问题",
            "证据边界与写作规则",
        ):
            self.assertNotIn(forbidden, public_text)

    def test_review_report_carries_gaps_and_source_review(self):
        digest = {
            "top_module": "top",
            "known_modules": ["child"],
            "source_review_report": {
                "target_count": 1,
                "reviewed_modules": 1,
                "claim_count": 1,
                "unresolved_count": 0,
                "modules": [
                    {
                        "module": "child",
                        "status": "reviewed",
                        "claim_count": 1,
                        "open_question_count": 0,
                        "report_file": "modules/child/source_review_report.json",
                    }
                ],
            },
            "evidence_boundary": ["公开手册不展示内部证据字段。"],
            "modules": [
                {
                    "module_name": "child",
                    "responsibility": {
                        "short_summary": {"value": "子模块职责。", "certainty": "ai_inferred"}
                    },
                    "source_review_claims": [
                        {
                            "subject": "模块职责",
                            "summary": "源码复核后的中文职责。",
                            "certainty": "ai_inferred",
                            "source_refs": [{"file": "rtl/rtl/child.v", "line_start": 1, "line_end": 8}],
                            "evidence_refs": ["ev:child:semantic_module"],
                        }
                    ],
                    "source_review_report": {"open_questions": []},
                    "evidence_gaps": [
                        {
                            "field": "reset behavior",
                            "reason": "reset polarity needs confirmation",
                            "evidence_refs": ["ev:gap"],
                        }
                    ],
                    "gap_file": {"gaps": []},
                    "review_questions": [
                        {
                            "subject": "reset behavior",
                            "question": "Confirm reset polarity.",
                            "evidence_refs": ["ev:review"],
                        }
                    ],
                }
            ],
        }
        state = {"top_module": "top", "evidence_digest": digest}
        manual = "[打开](top_generated_modules/child.md)\nAI 推断：子模块职责。"
        review = mw._build_manual_sanity_review(state, manual, {"child": "AI 推断：子模块职责。"})

        self.assertIn("Source Review 结果", review)
        self.assertIn("ev:child:semantic_module", review)
        self.assertIn("rtl/rtl/child.v:1-8", review)
        self.assertIn("reset polarity needs confirmation", review)
        self.assertIn("ev:gap", review)

    def test_manual_renders_top_structure_diagram_from_topology(self):
        digest = {
            "top_module": "top",
            "project_context": {
                "project_purpose": {"value": "顶层集成模块。", "certainty": "ai_inferred"},
                "top_level": {
                    "source_file": "rtl/rtl/top.v",
                    "direct_modules": {"value": ["child"]},
                    "external_port_groups": [],
                },
            },
            "system_topology": {
                "module_count": 3,
                "edges": [
                    {"parent": "top", "child": "child", "relationship": "instantiates"},
                    {"parent": "child", "child": "leaf", "relationship": "instantiates"},
                ],
            },
            "modules": [],
        }
        state = {"top_module": "top", "_manual_output_stem": "top_generated", "evidence_digest": digest}

        manual = mw._render_manual_context_markdown(state)

        self.assertIn("## 如何阅读本手册", manual)
        self.assertIn("### 2.3 顶层结构图", manual)
        self.assertIn("```mermaid", manual)
        self.assertIn('top["top"] --> child["child"]', manual)
        self.assertIn("`-- child", manual)
        self.assertIn("`-- leaf", manual)

    def test_module_page_renders_local_structure_diagram(self):
        module = {
            "module_name": "parent",
            "source_files": ["rtl/parent.v"],
            "page_policy": {"detail_level": "standard"},
            "system_position": {
                "parents": ["top"],
                "children": ["child"],
                "component_children": ["helper"],
                "upstream_modules": [],
                "downstream_modules": [],
            },
            "responsibility": {
                "short_summary": {"value": "父模块。", "certainty": "ai_inferred"}
            },
            "port_summary": {},
            "interfaces": {"interface_groups": []},
            "key_drive_flows": [],
            "internal_components": {
                "primary_samples": [
                    {"instance_name": "u_child", "module_type": "child"},
                ]
            },
            "assignment_impact_summary": {"primary_samples": []},
        }

        page = mw._render_module_page({"modules": [module]}, module)

        self.assertIn("### 1.1 本模块结构图", page)
        self.assertIn("```mermaid", page)
        self.assertIn('parent["parent"] -->|instance| u_child_child["u_child: child"]', page)
        self.assertIn("|-- u_child: child", page)

    def test_source_review_writes_claims_back_to_manual_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "rtl" / "rtl" / "foo.v"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                "module foo(input i_drive, output o_drive);\n"
                "assign o_drive = i_drive;\n"
                "endmodule\n",
                encoding="utf-8",
            )
            manual_context_dir = root / "rtl" / "manual_context" / "top"
            module_dir = manual_context_dir / "modules" / "foo"
            module_dir.mkdir(parents=True)
            (module_dir / "module_context.json").write_text("{}", encoding="utf-8")
            (module_dir / "module_doc_card.json").write_text("{}", encoding="utf-8")

            state = {"project_root": str(root), "manual_context_dir": str(manual_context_dir)}
            target = {
                "module": "foo",
                "source_file": "rtl/rtl/foo.v",
                "items": [
                    {
                        "kind": "module_responsibility",
                        "subject": "模块职责",
                        "summary": "Needs review",
                        "signals": ["i_drive", "o_drive"],
                        "instances": [],
                        "evidence_refs": ["ev:foo"],
                    }
                ],
            }

            report = mw._review_source_for_module(state, target, FakeClient(), "fake-model")
            mw._write_source_review_module_report(state, report)

            module_context = json.loads((module_dir / "module_context.json").read_text(encoding="utf-8"))
            self.assertEqual(module_context["source_review_report"]["status"], "reviewed")
            self.assertEqual(module_context["source_review_claims"][0]["summary"], "该模块根据输入驱动信号生成输出驱动响应。")

    def test_manual_output_override_is_used_by_cli_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "debug_manual.md"
            state = mw._ensure_state({"manual_output_override": str(output_path)})

            self.assertEqual(mw._manual_output_path(state, "继续"), output_path)

    def test_cli_builds_manual_workflow_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = manual_cli.build_parser().parse_args([
                "--project-root",
                temp_dir,
                "--top-module",
                "top",
                "--output",
                str(Path(temp_dir) / "manual.md"),
                "--force",
                "--no-llm",
            ])

            state = manual_cli.build_initial_state(args)

            self.assertEqual(state["top_module"], "top")
            self.assertEqual(state["stage"], "references")
            self.assertFalse(state["force_regenerate"])
            self.assertEqual(state["force_stages"], list(mw.MANUAL_STAGE_ORDER))
            self.assertEqual(state["manual_output_override"], str((Path(temp_dir) / "manual.md").resolve()))

    def test_cli_force_start_stage_uses_planned_force_stages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            args = manual_cli.build_parser().parse_args([
                "--project-root",
                temp_dir,
                "--top-module",
                "top",
                "--start-stage",
                "source_review",
                "--force",
                "--no-llm",
            ])

            state = manual_cli.build_initial_state(args)

            self.assertEqual(state["stage"], "source_review")
            self.assertFalse(state["force_regenerate"])
            self.assertEqual(state["force_stages"], ["source_review", "outline", "chapter_plan", "manual", "review"])

    def test_cli_applies_tool_timeouts_to_environment(self):
        args = manual_cli.build_parser().parse_args([
            "--top-module",
            "top",
            "--no-llm",
            "--parser-timeout",
            "300",
            "--knowledge-timeout",
            "1800",
        ])
        old_values = {
            key: manual_cli.os.environ.get(key)
            for key in (
                "RTL_MANUAL_PARSER_TIMEOUT",
                "RTL_MANUAL_KNOWLEDGE_TIMEOUT",
                "RTL_MANUAL_KNOWLEDGE_WRAPPER_TIMEOUT",
            )
        }
        try:
            for key in old_values:
                manual_cli.os.environ.pop(key, None)
            manual_cli.apply_runtime_env(args)
            self.assertEqual(manual_cli.os.environ["RTL_MANUAL_PARSER_TIMEOUT"], "300")
            self.assertEqual(manual_cli.os.environ["RTL_MANUAL_KNOWLEDGE_TIMEOUT"], "1800")
            self.assertEqual(manual_cli.os.environ["RTL_MANUAL_KNOWLEDGE_WRAPPER_TIMEOUT"], "1920")
        finally:
            for key, value in old_values.items():
                if value is None:
                    manual_cli.os.environ.pop(key, None)
                else:
                    manual_cli.os.environ[key] = value

    def test_cli_reuses_manual_workflow_stage_order(self):
        self.assertEqual(manual_cli.STAGE_ORDER, mw.MANUAL_STAGE_ORDER)

    def test_unknown_stage_falls_back_to_references(self):
        state = mw._ensure_state({"stage": "unknown_stage", "top_module": "top"})
        reply = mw._run_current_stage(state, Path("."), None, None, "continue")

        self.assertEqual(state["stage"], "parser")
        self.assertIn("references", state["completed_stages"])
        self.assertTrue(reply)

    def test_restart_stage_resets_requested_stage_and_downstream(self):
        state = mw._ensure_state({
            "stage": "done",
            "completed_stages": list(mw.MANUAL_STAGE_ORDER),
            "top_module": "top",
            "evidence_digest": {"old": True},
            "outline": [{"title": "old"}],
            "chapter_plan": [{"title": "old"}],
            "manual_summary": {"old": True},
            "review_report": "old",
        })

        mw._reset_from_stage(state, "knowledge")

        self.assertEqual(state["stage"], "knowledge")
        self.assertEqual(state["restart_stage"], "knowledge")
        self.assertEqual(state["force_stages"], list(mw.MANUAL_STAGE_ORDER[2:]))
        self.assertIn("parser", state["completed_stages"])
        self.assertNotIn("knowledge", state["completed_stages"])
        self.assertEqual(state["evidence_digest"], {})
        self.assertEqual(state["outline"], [])
        self.assertEqual(state["chapter_plan"], [])
        self.assertEqual(state["manual_summary"], {})
        self.assertEqual(state["review_report"], "")
        self.assertTrue(state["manual_needs_regenerate"])

    def test_restart_stage_parser_ignores_negated_mentions(self):
        stage = mw._extract_restart_stage("只重新生成 manual 和 review，不要重跑 parser 和 knowledge")
        self.assertEqual(stage, "manual")

    def test_restart_stage_prefers_stage_near_rerun_word(self):
        text = (
            "Please generate the RTL code manual.\n"
            "project_root=.\n"
            "rtl_inputs=rtl\n"
            "top_module=arm_soc_top\n\n"
            "From references stage, rerun all stages and continue."
        )

        stage = mw._extract_restart_stage(text)

        self.assertEqual(stage, "references")

    def test_restart_stage_does_not_choose_manual_from_task_intro(self):
        text = (
            "Please generate the RTL manual.\n"
            "From source_review stage, rerun and continue."
        )

        stage = mw._extract_restart_stage(text)

        self.assertEqual(stage, "source_review")

    def test_force_stage_is_cleared_when_stage_completes(self):
        state = mw._ensure_state({"force_stages": ["manual", "review"], "restart_stage": "manual"})

        self.assertTrue(mw._should_force_stage(state, "manual"))
        mw._mark_stage_done(state, "manual")

        self.assertFalse(mw._should_force_stage(state, "manual"))
        self.assertTrue(mw._should_force_stage(state, "review"))
        self.assertEqual(state["restart_stage"], "manual")

        mw._mark_stage_done(state, "review")
        self.assertEqual(state["force_stages"], [])
        self.assertEqual(state["restart_stage"], "")

    def test_tool_timeout_is_treated_as_failure(self):
        self.assertTrue(mw._tool_failed("工具脚本执行超时：run_parser_tool.py"))
        self.assertTrue(mw._tool_failed("Parser failed: execution timed out after 300s."))

    def test_parser_stage_refreshes_artifact_paths_after_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = mw._ensure_state({
                "project_root": str(root),
                "rtl_inputs": "rtl",
                "top_module": "top",
                "stage": "parser",
            })
            mw._update_state_from_user_input(state, "")
            self.assertEqual(Path(state["manual_context_dir"]), root / "manual_context" / "top")

            def fake_run_parser_tool(project_root, rtl_inputs):
                parser_dir = Path(project_root) / "rtl" / "parser_pipeline_rtl"
                (parser_dir / "modules").mkdir(parents=True)
                (parser_dir / "components").mkdir()
                (parser_dir / "project_index.json").write_text("{}", encoding="utf-8")
                (parser_dir / "build_report.json").write_text("{}", encoding="utf-8")
                return "Parser Tool execution succeeded"

            with patch.object(mw, "run_parser_tool", fake_run_parser_tool):
                mw._run_parser_stage(state)

            self.assertEqual(Path(state["parser_dir"]), root / "rtl" / "parser_pipeline_rtl")
            self.assertEqual(Path(state["knowledge_dir"]), root / "rtl" / "knowledge_ir" / "top")
            self.assertEqual(Path(state["manual_context_dir"]), root / "rtl" / "manual_context" / "top")

    def test_manual_cli_accepts_manual_generation_mode_with_no_llm(self):
        args = manual_cli.build_parser().parse_args([
            "--top-module",
            "arm_soc_top",
            "--manual-generation-mode",
            "llm_section_generate_with_page_polish",
            "--llm-module-page-scope",
            "top_and_direct",
            "--llm-module-page-limit",
            "5",
            "--llm-module-page-allowlist",
            "foo,bar",
            "--no-llm",
        ])
        client, model = manual_cli.build_model_client(args)
        state = manual_cli.build_initial_state(args)

        self.assertIsNone(client)
        self.assertIsNone(model)
        self.assertEqual(state["manual_generation_mode"], "llm_section_generate_with_page_polish")
        self.assertEqual(state["llm_module_page_scope"], "top_and_direct")
        self.assertEqual(state["llm_module_page_limit"], 5)
        self.assertEqual(state["llm_module_page_allowlist"], "foo,bar")

    def test_manual_timing_report_records_manual_generation_mode(self):
        args = manual_timing.build_parser().parse_args([
            "--top-module",
            "arm_soc_top",
            "--manual-generation-mode",
            "deterministic",
            "--llm-module-page-scope",
            "allowlist",
            "--llm-module-page-limit",
            "3",
            "--llm-module-page-allowlist",
            "top,child",
            "--no-llm",
        ])
        state = manual_timing.build_initial_state(args)
        report = manual_timing.build_report(args, "run", state, [], 0.0)

        self.assertEqual(state["manual_generation_mode"], "deterministic")
        self.assertEqual(state["force_stages"], list(mw.MANUAL_STAGE_ORDER))
        self.assertFalse(state["force_regenerate"])
        self.assertEqual(report["config"]["manual_generation_mode"], "deterministic")
        self.assertEqual(report["config"]["llm_module_page_scope"], "allowlist")
        self.assertEqual(report["config"]["llm_module_page_limit"], 3)
        self.assertEqual(report["config"]["llm_module_page_allowlist"], "top,child")

    def test_forced_knowledge_stage_disables_semantic_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = mw._ensure_state({
                "project_root": str(root),
                "rtl_inputs": "rtl",
                "top_module": "top",
                "stage": "knowledge",
                "knowledge_dir": str(root / "rtl" / "knowledge_ir" / "top"),
                "manual_context_dir": str(root / "rtl" / "manual_context" / "top"),
                "force_stages": ["knowledge"],
                "semantic_enrichment": True,
                "enrich_modules": "",
            })
            captured = {}

            def fake_run_knowledge_tool(**kwargs):
                captured.update(kwargs)
                return "Knowledge Tool execution succeeded"

            with patch.object(mw, "_knowledge_artifacts_ready", return_value=(False, Path(state["manual_context_dir"]), [])):
                with patch.object(mw, "run_knowledge_tool", fake_run_knowledge_tool):
                    reply = mw._run_knowledge_stage(state)

            self.assertTrue(captured["force"])
            self.assertIn("阶段3", reply)
            self.assertEqual(state["stage"], "evidence")


if __name__ == "__main__":
    unittest.main()
