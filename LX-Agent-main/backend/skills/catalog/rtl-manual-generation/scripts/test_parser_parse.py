import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_INPUTS = "rtl/rtl"
DEFAULT_OUTPUT = "rtl/parser_pipeline_rtl"
EXPECTED_TOP_MODULES = {"arm_soc_top", "cpu_top_all"}


def package_env() -> dict[str, str]:
    skill_dir = Path(__file__).resolve().parents[1]
    package_dir = skill_dir / "packages"
    env = os.environ.copy()
    old_pythonpath = env.get("PYTHONPATH", "")
    paths = [str(package_dir)]
    if old_pythonpath:
        paths.append(old_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke-test parser.pipeline without pytest. Defaults to parsing "
            "rtl/rtl and writing rtl/parser_pipeline_rtl from the repository root."
        )
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--inputs", default=DEFAULT_INPUTS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    input_dir = (project_root / args.inputs).resolve()
    output_dir = (project_root / args.output).resolve()

    failures = validate_inputs(input_dir)
    if failures:
        print_failures("Input validation failed", failures)
        return 2

    cmd = [
        sys.executable,
        "-m",
        "parser.pipeline",
        "build",
        "--inputs",
        args.inputs,
        "--output",
        args.output,
    ]

    print("== Run parser.pipeline ==")
    print(f"project root: {project_root}")
    print(f"inputs: {args.inputs}")
    print(f"output: {args.output}")
    print(f"command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=args.timeout,
            env=package_env(),
        )
    except subprocess.TimeoutExpired:
        print(f"FAIL: parser timed out after {args.timeout}s")
        return 3

    if result.stdout.strip():
        print("\nSTDOUT:")
        print(result.stdout.strip())
    if result.stderr.strip():
        print("\nSTDERR:")
        print(result.stderr.strip())

    if result.returncode != 0:
        print(f"FAIL: parser exited with status {result.returncode}")
        return result.returncode

    artifact_failures = validate_outputs(output_dir)
    if artifact_failures:
        print_failures("Output validation failed", artifact_failures)
        return 4

    project_index = read_json(output_dir / "project_index.json")
    build_report = read_json(output_dir / "build_report.json")
    stats = project_index.get("stats", {})
    issues = build_report.get("issues", [])

    print("\n== Parser smoke test passed ==")
    print(f"output dir: {output_dir}")
    print(f"top modules: {', '.join(sorted(EXPECTED_TOP_MODULES))}")
    print(f"module count: {stats.get('module_count')}")
    print(f"component count: {stats.get('component_count')}")
    print(f"reported issues: {len(issues)}")
    return 0


def validate_inputs(input_dir: Path) -> list[str]:
    failures = []
    if not input_dir.is_dir():
        failures.append(f"missing RTL input directory: {input_dir}")
        return failures
    for file_name in ("read_rtl_list.tcl", "rtl_top_list.tcl"):
        path = input_dir / file_name
        if not path.is_file():
            failures.append(f"missing required filelist: {path}")
    return failures


def validate_outputs(output_dir: Path) -> list[str]:
    failures = []
    required_paths = [
        output_dir / "project_index.json",
        output_dir / "build_report.json",
        output_dir / "modules",
        output_dir / "components",
    ]
    for path in required_paths:
        if not path.exists():
            failures.append(f"missing expected artifact: {path}")
    if failures:
        return failures

    project_index = read_json(output_dir / "project_index.json")
    build_report = read_json(output_dir / "build_report.json")

    if project_index.get("schema") != "parser_pipeline_project_index":
        failures.append("project_index.json has unexpected schema")
    if build_report.get("schema") != "parser_pipeline_build_report":
        failures.append("build_report.json has unexpected schema")

    top_names = {
        item.get("name")
        for item in project_index.get("top_modules", [])
        if isinstance(item, dict)
    }
    missing_tops = sorted(EXPECTED_TOP_MODULES - top_names)
    if missing_tops:
        failures.append(f"missing expected top modules: {', '.join(missing_tops)}")

    stats = project_index.get("stats", {})
    if int(stats.get("module_count", 0)) <= 0:
        failures.append("project_index.json stats.module_count must be greater than 0")
    if int(stats.get("component_count", 0)) <= 0:
        failures.append("project_index.json stats.component_count must be greater than 0")

    for top_name in EXPECTED_TOP_MODULES:
        module_json = output_dir / "modules" / f"{top_name}.json"
        if not module_json.is_file():
            failures.append(f"missing top module JSON: {module_json}")

    module_dir = output_dir / "modules"
    for module_path in sorted(module_dir.glob("*.json")):
        failures.extend(validate_assignments(module_path))
        failures.extend(validate_connection_graph(module_path))

    return failures


def validate_assignments(module_path: Path) -> list[str]:
    failures = []
    module_json = read_json(module_path)
    assignments = module_json.get("assignments")
    if not isinstance(assignments, list):
        return [f"{module_path} assignments must be a list"]

    for assignment in assignments:
        if not isinstance(assignment, dict):
            failures.append(f"{module_path} contains a non-object assignment")
            continue
        for key in ("kind", "index", "lhs", "rhs", "lhs_terms", "rhs_terms"):
            if key not in assignment:
                failures.append(f"{module_path} assignment missing {key}")
        if assignment.get("kind") != "continuous_assign":
            failures.append(f"{module_path} assignment has unexpected kind {assignment.get('kind')!r}")

    flow_graph = module_json.get("flow_graph", {})
    dependencies = flow_graph.get("assignment_dependencies")
    if not isinstance(dependencies, list):
        failures.append(f"{module_path} flow_graph.assignment_dependencies must be a list")
    return failures


def validate_connection_graph(module_path: Path) -> list[str]:
    failures = []
    module_json = read_json(module_path)
    module_name = module_json.get("name") or module_path.stem
    connection_graph = module_json.get("connection_graph")
    if not isinstance(connection_graph, dict):
        return [f"{module_path} missing connection_graph"]
    if connection_graph.get("scope") != "module":
        failures.append(f"{module_path} connection_graph.scope must be module")
    if connection_graph.get("module") != module_name:
        failures.append(f"{module_path} connection_graph.module does not match module name")

    nodes = connection_graph.get("nodes", [])
    node_ids = {
        node.get("id")
        for node in nodes
        if isinstance(node, dict)
    }
    if "self" not in node_ids:
        failures.append(f"{module_path} connection_graph.nodes missing self boundary node")

    for connection in connection_graph.get("connections", []):
        if not isinstance(connection, dict):
            failures.append(f"{module_path} connection_graph contains a non-object connection")
            continue
        for side in ("from", "to"):
            endpoint = connection.get(side, {})
            node_id = endpoint.get("node") if isinstance(endpoint, dict) else None
            if node_id not in node_ids:
                signal = connection.get("signal", "<unknown>")
                failures.append(
                    f"{module_path} connection endpoint references missing node {node_id!r} on signal {signal}"
                )
    return failures


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def print_failures(title: str, failures: list[str]) -> None:
    print(f"FAIL: {title}")
    for failure in failures:
        print(f"- {failure}")


if __name__ == "__main__":
    raise SystemExit(main())
