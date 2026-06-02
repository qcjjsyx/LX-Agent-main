from __future__ import annotations

from pathlib import Path

from backend.tests.module_loader import load_run_knowledge_tool


run_knowledge_tool = load_run_knowledge_tool()


def test_locate_parser_artifacts_uses_project_root_layout(tmp_path):
    parser_dir = tmp_path / "parser_pipeline_rtl"
    (parser_dir / "modules").mkdir(parents=True)
    (parser_dir / "project_index.json").write_text("{}", encoding="utf-8")

    assert run_knowledge_tool.locate_parser_artifacts(tmp_path) == parser_dir
    assert run_knowledge_tool.output_base_for(tmp_path, parser_dir) == tmp_path


def test_path_arg_prefers_relative_paths_inside_project(tmp_path):
    inner = tmp_path / "knowledge_ir" / "top" / "semantic" / "semantic_progress.jsonl"
    outside = Path("/outside/progress.jsonl")

    assert run_knowledge_tool.path_arg(tmp_path, inner) == "knowledge_ir/top/semantic/semantic_progress.jsonl"
    assert run_knowledge_tool.path_arg(tmp_path, outside) == str(outside)
