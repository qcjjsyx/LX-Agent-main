import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


def add_skill_packages_to_path() -> Path:
    skill_dir = Path(__file__).resolve().parents[1]
    package_dir = skill_dir / "packages"
    sys.path.insert(0, str(package_dir))
    return package_dir


add_skill_packages_to_path()

from knowledge.loaders.knowledge_base import load_knowledge_base
from knowledge.manual_ir import build_context_pack, build_manual_ir, enrich_manual_ir, validate_manual_ir_split
from knowledge.manual_ir.cli import _write_split_manual_ir


DEFAULT_MODULES = "decoder,launch,execute,lsu,wb,fetch,intAndExc,grf,prf"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke-test the enhanced knowledge/manual_ir flow without pytest. "
            "It exports split Manual IR, runs RTL-source semantic enrichment, "
            "validates the result, and writes context_pack.json."
        )
    )
    parser.add_argument("--artifacts-root", default="rtl/parser_pipeline_rtl")
    parser.add_argument("--source-root", default="rtl/rtl")
    parser.add_argument("--output-root", default="rtl/manual_ir")
    parser.add_argument("--top-module", default="arm_soc_top")
    parser.add_argument("--audience", default="newcomer")
    parser.add_argument("--modules", default=DEFAULT_MODULES)
    parser.add_argument(
        "--keep-temp-artifacts",
        action="store_true",
        help="Keep the normalized temporary parser artifacts for inspection.",
    )
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    artifacts_root = (repo_root / args.artifacts_root).resolve()
    source_root = (repo_root / args.source_root).resolve()
    output_root = (repo_root / args.output_root).resolve()
    manual_ir_dir = output_root / args.top_module
    modules = [item.strip() for item in args.modules.split(",") if item.strip()]

    require_path(artifacts_root / "project_index.json", "parser project_index.json")
    require_path(artifacts_root / "modules", "parser modules directory")
    require_path(artifacts_root / "components", "parser components directory")
    require_path(source_root, "RTL source root")

    with tempfile.TemporaryDirectory(prefix="manual_ir_artifacts_") as temp_dir:
        temp_root = Path(temp_dir)
        normalized_artifacts = temp_root / "parser_pipeline_rtl"
        shutil.copytree(artifacts_root, normalized_artifacts)
        normalize_parser_source_paths(normalized_artifacts, source_root)

        print_step("1. Export split Manual IR")
        kb = load_knowledge_base(normalized_artifacts)
        manual_ir = build_manual_ir(kb, args.top_module)
        if manual_ir_dir.exists():
            shutil.rmtree(manual_ir_dir)
        _write_split_manual_ir(manual_ir_dir, manual_ir.to_dict())
        print(f"   wrote: {manual_ir_dir}")

        print_step("2. Run source-reading semantic enrichment")
        enrichment_report = enrich_manual_ir(
            manual_ir_dir,
            normalized_artifacts,
            modules=modules,
            skip_missing=True,
            skip_failed=True,
        )
        write_json(manual_ir_dir / "enrichment_report.json", enrichment_report)
        print(f"   status: {enrichment_report.get('status')}")
        print(f"   semantic cards: {enrichment_report.get('count')}")
        for issue in enrichment_report.get("issues", []):
            print(f"   {issue.get('level', 'issue')}: {issue.get('message', '')}")

        print_step("3. Validate split Manual IR")
        validation_report = validate_manual_ir_split(
            manual_ir_dir,
            parser_artifacts_root=normalized_artifacts,
        )
        write_json(manual_ir_dir / "validation_report.json", validation_report)
        print(f"   status: {validation_report.get('status')}")
        for issue in validation_report.get("issues", []):
            print(f"   {issue.get('level', 'issue')}: {issue.get('message', '')}")

        print_step("4. Build ContextPack")
        context_pack = build_context_pack(manual_ir_dir, audience=args.audience)
        write_json(manual_ir_dir / "context_pack.json", context_pack)
        overlay_count = sum(
            len(section.get("semantic_overlays", []))
            for section in context_pack.get("sections", [])
        )
        print(f"   wrote: {manual_ir_dir / 'context_pack.json'}")
        print(f"   semantic overlays in ContextPack: {overlay_count}")

        manifest = read_json(manual_ir_dir / "manifest.json")
        counts = manifest.get("counts", {})
        print_step("5. Result summary")
        print(f"   output dir: {manual_ir_dir}")
        print(f"   top module: {manifest.get('top_module')}")
        print(f"   counts: {json.dumps(counts, ensure_ascii=False)}")

        if args.keep_temp_artifacts:
            kept_root = output_root / "_normalized_parser_pipeline_rtl"
            if kept_root.exists():
                shutil.rmtree(kept_root)
            shutil.copytree(normalized_artifacts, kept_root)
            print(f"   kept normalized parser artifacts: {kept_root}")

        if enrichment_report.get("status") != "passed":
            return 2
        if validation_report.get("status") != "passed":
            return 3

    return 0


def normalize_parser_source_paths(artifacts_root: Path, source_root: Path) -> None:
    """Normalize parser JSON source paths so enrichment can read local RTL files."""

    project_index_path = artifacts_root / "project_index.json"
    project_index = read_json(project_index_path)
    source_parent = source_root.parent
    source_root_name = source_root.name
    project_index["repo_root"] = str(source_parent)

    for top in project_index.get("top_modules", []):
        if isinstance(top, dict) and isinstance(top.get("file"), str):
            top["file"] = normalize_source_ref(top["file"], source_root_name)

    artifacts = project_index.get("artifacts", {})
    if isinstance(artifacts, dict):
        for group in ("modules", "components"):
            for item in artifacts.get(group, []):
                if isinstance(item, dict) and isinstance(item.get("file"), str):
                    item["file"] = normalize_source_ref(item["file"], source_root_name)

    write_json(project_index_path, project_index)

    for module_path in sorted((artifacts_root / "modules").glob("*.json")):
        payload = read_json(module_path)
        if isinstance(payload.get("file"), str):
            payload["file"] = normalize_source_ref(payload["file"], source_root_name)
            write_json(module_path, payload)

    for component_path in sorted((artifacts_root / "components").glob("*.json")):
        payload = read_json(component_path)
        if isinstance(payload.get("file"), str):
            payload["file"] = normalize_source_ref(payload["file"], source_root_name)
            write_json(component_path, payload)


def normalize_source_ref(value: str, source_root_name: str) -> str:
    normalized = value.replace("\\", "/").strip()
    parts = [part for part in normalized.split("/") if part and part != "."]
    if parts and parts[0].lower() == source_root_name.lower():
        return "/".join(parts)
    if parts and parts[0].lower() == "rtl":
        parts[0] = source_root_name
        return "/".join(parts)
    return f"{source_root_name}/{'/'.join(parts)}" if parts else normalized


def print_step(title: str) -> None:
    print(f"\n== {title} ==")


def require_path(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
