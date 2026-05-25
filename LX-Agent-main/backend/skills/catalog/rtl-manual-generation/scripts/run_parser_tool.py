import argparse
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


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def run_parser_tool(project_root: str = ".", rtl_inputs: str = "rtl", timeout: int | None = None) -> str:
    root = Path(project_root).resolve()

    if not root.exists():
        return f"Parser failed: project_root does not exist: {root}"

    rtl_inputs, inputs_path = resolve_rtl_inputs(root, rtl_inputs)
    output_base = inputs_path.parent if inputs_path.parent != root and inputs_path.name == "rtl" else root
    output_dir = output_base / "parser_pipeline_rtl"
    output_arg = path_arg(root, output_dir)

    if not inputs_path.exists():
        return (
            f"Parser failed: RTL input directory does not exist: {inputs_path}\n"
            "Check rtl_inputs, for example rtl, rtl/rtl, test_data/rtl, or tests/fixtures/rtl."
        )

    cmd = [
        sys.executable,
        "-m",
        "parser.pipeline",
        "build",
        "--inputs",
        rtl_inputs,
        "--output",
        output_arg,
    ]

    parser_timeout = timeout or env_int("RTL_MANUAL_PARSER_TIMEOUT", 220)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=parser_timeout,
            env=package_env(),
        )
    except subprocess.TimeoutExpired:
        return f"Parser failed: execution timed out after {parser_timeout}s."
    except Exception as exc:
        return f"Parser failed: {exc}"

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        return (
            "Parser Tool execution failed\n"
            f"Command: {' '.join(cmd)}\n"
            f"Working directory: {root}\n\n"
            f"STDOUT:\n{stdout or 'None'}\n\n"
            f"STDERR:\n{stderr or 'None'}"
        )

    expected_items = [
        output_dir / "project_index.json",
        output_dir / "build_report.json",
        output_dir / "modules",
        output_dir / "components",
    ]
    missing = [str(path) for path in expected_items if not path.exists()]

    report = (
        "Parser Tool execution succeeded\n"
        f"Project root: {root}\n"
        f"RTL input directory: {rtl_inputs}\n"
        f"Output directory: {output_arg}\n\n"
    )

    if missing:
        report += "Some expected artifacts are missing:\n"
        report += "\n".join(f"- {item}" for item in missing)
    else:
        report += (
            "Generated key artifacts:\n"
            f"- {output_arg}/project_index.json\n"
            f"- {output_arg}/build_report.json\n"
            f"- {output_arg}/modules/\n"
            f"- {output_arg}/components/\n"
        )

    report += f"\n\nSTDOUT:\n{stdout or 'None'}\n"
    report += f"\nSTDERR:\n{stderr or 'None'}"
    return report


def resolve_rtl_inputs(root: Path, rtl_inputs: str) -> tuple[str, Path]:
    inputs_path = root / rtl_inputs
    if looks_like_rtl_project(inputs_path):
        return rtl_inputs, inputs_path

    nested = inputs_path / "rtl"
    if looks_like_rtl_project(nested):
        return str(Path(rtl_inputs) / "rtl"), nested

    return rtl_inputs, inputs_path


def looks_like_rtl_project(path: Path) -> bool:
    return (
        path.exists()
        and path.is_dir()
        and (
            (path / "read_rtl_list.tcl").is_file()
            or (path / "rtl_top_list.tcl").is_file()
            or any(path.glob("*.v"))
            or any(path.glob("*.sv"))
        )
    )


def path_arg(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rtl-inputs", default="rtl")
    parser.add_argument("--timeout", type=int, default=0)
    args = parser.parse_args()

    print(run_parser_tool(args.project_root, args.rtl_inputs, timeout=args.timeout or None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
