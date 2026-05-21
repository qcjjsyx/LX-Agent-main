import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def package_env():
    skill_dir = Path(__file__).resolve().parents[1]
    package_dir = skill_dir / "packages"
    env = os.environ.copy()
    old_pythonpath = env.get("PYTHONPATH", "")

    paths = [str(package_dir)]
    if old_pythonpath:
        paths.append(old_pythonpath)

    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def run_knowledge_tool(
    project_root: str = ".",
    top_module: str = "",
    audience: str = "newcomer",
    section_id: str = "",
    enrich: bool = True,
    enrich_modules: str = "",
    max_flows_per_module: str = "",
    semantic_workers: str = "",
    semantic_model: str = "",
    semantic_base_url: str = "",
    semantic_api_key: str = "",
    timeout: int | None = None,
) -> str:
    """Run the new Knowledge IR -> Manual Context pipeline.

    The function name and legacy arguments are kept for existing skill/tool
    routing. `audience` and `section_id` were only meaningful for legacy
    Manual IR ContextPack generation and are now recorded as compatibility
    notes; final manual generation consumes Manual Context instead.
    """
    if not top_module.strip():
        return "Knowledge Tool execution failed: top_module is required."

    root = Path(project_root).resolve()
    if not root.exists():
        return f"Knowledge Tool execution failed: project_root does not exist: {root}"

    parser_dir = locate_parser_artifacts(root)
    if not parser_dir:
        return (
            "Knowledge Tool execution failed: parser artifacts were not found.\n"
            "Expected one of:\n"
            f"- {root / 'rtl' / 'parser_pipeline_rtl'}\n"
            f"- {root / 'parser_pipeline_rtl'}\n"
            "Run run_parser_tool first so parser artifacts exist."
        )

    output_base = output_base_for(root, parser_dir)
    knowledge_output_root = output_base / "knowledge_ir"
    manual_context_output_root = output_base / "manual_context"
    knowledge_dir = knowledge_output_root / top_module
    manual_context_dir = manual_context_output_root / top_module

    cmd = [
        sys.executable,
        "-m",
        "knowledge.pipeline",
        "--artifacts-root",
        path_arg(root, parser_dir),
        "--top-module",
        top_module,
        "--knowledge-output-root",
        path_arg(root, knowledge_output_root),
        "--manual-context-output-root",
        path_arg(root, manual_context_output_root),
        "--skip-failed-semantic",
    ]

    if not enrich:
        cmd.append("--skip-semantic")
    elif enrich_modules.strip():
        cmd.extend(["--semantic-modules", normalize_modules(enrich_modules)])

    if max_flows_per_module.strip():
        cmd.extend(["--max-flows-per-module", max_flows_per_module.strip()])
    if semantic_workers.strip():
        cmd.extend(["--semantic-workers", semantic_workers.strip()])
    if semantic_model.strip():
        cmd.extend(["--semantic-model", semantic_model.strip()])
    if semantic_base_url.strip():
        cmd.extend(["--semantic-base-url", semantic_base_url.strip()])
    if semantic_api_key.strip():
        cmd.extend(["--semantic-api-key", semantic_api_key.strip()])

    pipeline_timeout = timeout or env_int("RTL_MANUAL_KNOWLEDGE_TIMEOUT", 3600)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=pipeline_timeout,
            env=package_env(),
        )
    except subprocess.TimeoutExpired:
        return f"Knowledge Tool execution failed: execution timed out after {pipeline_timeout}s."
    except Exception as exc:
        return f"Knowledge Tool execution failed: {exc}"

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    pipeline_report = parse_report(stdout)

    if result.returncode != 0:
        return (
            "Knowledge Tool execution failed\n"
            f"Command: {' '.join(cmd)}\n"
            f"Working directory: {root}\n\n"
            f"STDOUT:\n{stdout or 'None'}\n\n"
            f"STDERR:\n{stderr or 'None'}"
        )

    expected_items = [
        knowledge_dir / "manifest.json",
        knowledge_dir / "project.json",
        knowledge_dir / "modules",
        knowledge_dir / "ai_context" / "index.json",
        manual_context_dir / "manifest.json",
        manual_context_dir / "project_context.json",
        manual_context_dir / "system_topology.json",
        manual_context_dir / "interface_index.json",
        manual_context_dir / "flow_index.json",
        manual_context_dir / "evidence_index.json",
        manual_context_dir / "validation_report.json",
        manual_context_dir / "modules" / top_module / "module_context.json",
        manual_context_dir / "modules" / top_module / "interfaces.json",
        manual_context_dir / "modules" / top_module / "gaps.json",
    ]
    if enrich:
        expected_items.append(knowledge_dir / "semantic" / "index.json")

    missing = [str(path) for path in expected_items if not path.exists()]
    validation_report = read_optional_json(manual_context_dir / "validation_report.json")
    validation_status = validation_report.get("status", "unknown")

    if missing:
        status_line = "Knowledge Tool execution incomplete"
    else:
        status_line = "Knowledge Tool execution succeeded"

    report = (
        f"{status_line}\n"
        f"Input parser artifacts: {path_arg(root, parser_dir)}\n"
        f"Knowledge IR output: {path_arg(root, knowledge_dir)}\n"
        f"Manual Context output: {path_arg(root, manual_context_dir)}\n"
        "Legacy Manual IR output: not generated\n"
        f"Manual Context validation: {validation_status}\n"
    )

    if audience or section_id:
        notes = []
        if audience:
            notes.append(f"audience={audience} is retained for compatibility only")
        if section_id:
            notes.append(f"section_id={section_id} is ignored by Manual Context pipeline")
        report += "Compatibility notes: " + "; ".join(notes) + "\n"

    if pipeline_report:
        report += "\nPipeline summary:\n"
        report += json.dumps(summarize_pipeline_report(pipeline_report), ensure_ascii=False, indent=2)
        report += "\n"

    if missing:
        report += "\nMissing expected artifacts:\n"
        report += "\n".join(f"- {item}" for item in missing)
    else:
        report += (
            "\nGenerated key artifacts:\n"
            f"- {path_arg(root, knowledge_dir / 'manifest.json')}\n"
            f"- {path_arg(root, knowledge_dir / 'project.json')}\n"
            f"- {path_arg(root, knowledge_dir / 'modules')}/\n"
            f"- {path_arg(root, knowledge_dir / 'ai_context' / 'index.json')}\n"
            + (f"- {path_arg(root, knowledge_dir / 'semantic' / 'index.json')}\n" if enrich else "")
            + f"- {path_arg(root, manual_context_dir / 'manifest.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'project_context.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'system_topology.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'interface_index.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'flow_index.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'evidence_index.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'validation_report.json')}\n"
            + f"- {path_arg(root, manual_context_dir / 'modules' / top_module / 'module_context.json')}\n"
        )

    if stdout and not pipeline_report:
        report += f"\nSTDOUT:\n{stdout}\n"
    if stderr:
        report += f"\nSTDERR:\n{stderr}\n"
    return report


def locate_parser_artifacts(root: Path) -> Path | None:
    candidates = [
        root / "rtl" / "parser_pipeline_rtl",
        root / "parser_pipeline_rtl",
    ]
    for candidate in candidates:
        if (candidate / "project_index.json").is_file() and (candidate / "modules").is_dir():
            return candidate
    return None


def output_base_for(root: Path, parser_dir: Path) -> Path:
    if parser_dir.parent.name == "rtl":
        return parser_dir.parent
    return root


def path_arg(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def normalize_modules(value: str) -> str:
    return ",".join(item.strip() for item in value.replace("，", ",").split(",") if item.strip())


def parse_report(stdout: str) -> dict:
    if not stdout:
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_pipeline_report(report: dict) -> dict:
    return {
        "status": report.get("status", ""),
        "top_module": report.get("top_module", ""),
        "outputs": report.get("outputs", {}),
        "steps": [
            {
                "name": step.get("name", ""),
                "status": step.get("status", ""),
                "counts": step.get("counts", {}),
                "issues": step.get("issues", [])[:5],
            }
            for step in report.get("steps", [])
            if isinstance(step, dict)
        ],
    }


def read_optional_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--top-module", required=True)
    parser.add_argument("--audience", default="newcomer")
    parser.add_argument("--section-id", default="")
    parser.add_argument("--enrich", dest="enrich", action="store_true", default=True, help="Run Semantic Layer before Manual Context (default).")
    parser.add_argument("--no-enrich", dest="enrich", action="store_false", help="Skip Semantic Layer and build Manual Context without AI claims.")
    parser.add_argument("--enrich-modules", default="", help="Compatibility alias for --semantic-modules.")
    parser.add_argument("--max-flows-per-module", default="")
    parser.add_argument("--semantic-workers", default="")
    parser.add_argument("--semantic-model", default="")
    parser.add_argument("--semantic-base-url", default="")
    parser.add_argument("--semantic-api-key", default="")
    parser.add_argument("--timeout", type=int, default=0, help="Timeout in seconds for knowledge.pipeline. Defaults to RTL_MANUAL_KNOWLEDGE_TIMEOUT or 3600.")
    args = parser.parse_args()

    print(
        run_knowledge_tool(
            project_root=args.project_root,
            top_module=args.top_module,
            audience=args.audience,
            section_id=args.section_id,
            enrich=args.enrich,
            enrich_modules=args.enrich_modules,
            max_flows_per_module=args.max_flows_per_module,
            semantic_workers=args.semantic_workers,
            semantic_model=args.semantic_model,
            semantic_base_url=args.semantic_base_url,
            semantic_api_key=args.semantic_api_key,
            timeout=args.timeout or None,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
