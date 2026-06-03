from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from .artifacts import (
    enhancement_entry,
    load_manifest,
    manual_paths,
    resolve_manifest_path,
    save_manifest,
    sha256_file,
    update_compose_status,
)


## 组合最终手册
def compose_final_manual(
    *,
    project_root: str | Path,
    top_module: str,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    paths = manual_paths(project_root, top_module)
    manifest = load_manifest(project_root, top_module)
    if not paths["base_main"].exists():
        raise FileNotFoundError(f"base main manual not found: {paths['base_main']}")

    _log(event_logger, "manual_compose_start", top_module=top_module)
    paths["final_main"].parent.mkdir(parents=True, exist_ok=True)
    paths["final_modules_dir"].mkdir(parents=True, exist_ok=True)
    for old_page in paths["final_modules_dir"].glob("*.md"):
        old_page.unlink()

    enhanced_count = 0
    fallback_count = 0
    stale_count = 0
    invalid_count = 0

    main_text, main_status = _select_main_text(paths, manifest)
    if main_status == "enhanced":
        enhanced_count += 1
    elif main_status == "stale":
        stale_count += 1
        fallback_count += 1
    elif main_status == "invalid":
        invalid_count += 1
        fallback_count += 1
    else:
        fallback_count += 1
    paths["final_main"].write_text(_rewrite_main_links(main_text, top_module).rstrip() + "\n", encoding="utf-8")

    base_pages = sorted(paths["base_modules_dir"].glob("*.md")) if paths["base_modules_dir"].exists() else []
    for base_page in base_pages:
        module_name = base_page.stem
        chosen_path, status = _select_module_page(project_root, manifest, module_name, base_page)
        final_text = chosen_path.read_text(encoding="utf-8")
        final_text = _inject_compose_drive_diagram(final_text, project_root, top_module, module_name)
        (paths["final_modules_dir"] / base_page.name).write_text(final_text.rstrip() + "\n", encoding="utf-8")
        if status == "enhanced":
            enhanced_count += 1
        elif status == "stale":
            stale_count += 1
            fallback_count += 1
        elif status == "invalid":
            invalid_count += 1
            fallback_count += 1
        else:
            fallback_count += 1

    manifest = update_compose_status(
        project_root,
        top_module,
        manifest,
        enhanced_count=enhanced_count,
        fallback_count=fallback_count,
        stale_count=stale_count,
        invalid_count=invalid_count,
    )
    manifest_path = save_manifest(project_root, top_module, manifest)
    _log(
        event_logger,
        "manual_compose_end",
        top_module=top_module,
        status="success",
        final_main=str(paths["final_main"]),
        final_modules_dir=str(paths["final_modules_dir"]),
        enhanced_count=enhanced_count,
        fallback_count=fallback_count,
        stale_count=stale_count,
        invalid_count=invalid_count,
        manifest_path=str(manifest_path),
    )
    return {
        "final_main": paths["final_main"],
        "final_modules_dir": paths["final_modules_dir"],
        "manifest_path": manifest_path,
        "enhanced_count": enhanced_count,
        "fallback_count": fallback_count,
        "stale_count": stale_count,
        "invalid_count": invalid_count,
    }


def _select_main_text(paths: dict[str, Path], manifest: dict[str, Any]) -> tuple[str, str]:
    entry = enhancement_entry(manifest, "main", "main")
    base_hash = sha256_file(paths["base_main"])
    if entry.get("status") != "success":
        return paths["base_main"].read_text(encoding="utf-8"), "fallback"
    if entry.get("base_hash") != base_hash:
        entry["status"] = "stale"
        entry["error"] = "Base main manual changed."
        return paths["base_main"].read_text(encoding="utf-8"), "stale"
    enhanced_path = resolve_manifest_path(paths["project_root"], entry.get("enhanced_path", ""))
    if not enhanced_path.exists():
        entry["status"] = "invalid"
        entry["error"] = "Enhanced main manual is missing."
        return paths["base_main"].read_text(encoding="utf-8"), "invalid"
    return enhanced_path.read_text(encoding="utf-8"), "enhanced"


def _select_module_page(
    project_root: str | Path,
    manifest: dict[str, Any],
    module_name: str,
    base_page: Path,
) -> tuple[Path, str]:
    entry = enhancement_entry(manifest, "module", module_name)
    if entry.get("status") != "success":
        return base_page, "fallback"
    if entry.get("base_hash") != sha256_file(base_page):
        entry["status"] = "stale"
        entry["error"] = "Base module page changed."
        return base_page, "stale"
    enhanced_path = resolve_manifest_path(project_root, entry.get("enhanced_path", ""))
    if not enhanced_path.exists():
        entry["status"] = "invalid"
        entry["error"] = "Enhanced module page is missing."
        return base_page, "invalid"
    return enhanced_path, "enhanced"


def _rewrite_main_links(markdown: str, top_module: str) -> str:
    return (
        markdown.replace(f"{top_module}_base_modules/", f"{top_module}_generated_modules/")
        .replace(f"{top_module}_enhanced/modules/", f"{top_module}_generated_modules/")
    )


def _inject_compose_drive_diagram(markdown: str, project_root: str | Path, top_module: str, module_name: str) -> str:
    section = _compose_drive_diagram_section(project_root, top_module, module_name)
    if not section:
        return markdown
    existing = re.search(r"\n### 3\.1 Drive 事件流图\n", markdown)
    if existing:
        next_heading = re.search(r"\n(?:## |### 3\.[2-9])", markdown[existing.end():])
        end = existing.end() + next_heading.start() if next_heading else len(markdown)
        return markdown[: existing.start()] + "\n" + section.rstrip() + markdown[end:]
    insert_match = re.search(r"\n## 4\.", markdown)
    if insert_match:
        return markdown[: insert_match.start()] + "\n" + section.rstrip() + "\n" + markdown[insert_match.start():]
    return markdown.rstrip() + "\n\n" + section.rstrip() + "\n"


def _compose_drive_diagram_section(project_root: str | Path, top_module: str, module_name: str) -> str:
    packet = _load_drive_diagram_packet(project_root, top_module, module_name)
    if not packet or not packet.get("flows"):
        return ""
    lines = [
        "### 3.1 Drive 事件流图",
        "",
        "- 该图由 compose 阶段根据 Manual Context `ordered_path` 确定性生成，只展示 drive/event 传递，忽略 payload。",
        "",
        "```mermaid",
        *_packet_to_mermaid(packet),
        "```",
    ]
    if packet.get("logic_nodes"):
        lines.extend([
            "",
            "- drive-like assign 逻辑合成：",
        ])
        for node in packet.get("logic_nodes", [])[:8]:
            inputs = ", ".join(f"`{item}`" for item in node.get("inputs", []) or [])
            output = node.get("output", "")
            operator = node.get("operator", "")
            if output and inputs:
                lines.append(f"  - `{output}` = {operator}({inputs})")
    return "\n".join(lines)


def _load_drive_diagram_packet(project_root: str | Path, top_module: str, module_name: str) -> dict[str, Any]:
    try:
        from backend import manual_workflow
    except Exception:
        return {}
    manual_context_dir = Path(project_root) / "manual_context" / top_module
    module_dir = manual_context_dir / "modules" / module_name
    module_context_path = module_dir / "module_context.json"
    if not module_context_path.exists():
        return {}
    try:
        payload = manual_workflow._read_manual_context_module(manual_context_dir, module_name)
        module = manual_workflow._summarize_manual_context_module(payload)
        digest = {"manual_context_dir": str(manual_context_dir)}
        state = {"project_root": str(project_root), "top_module": top_module}
        return manual_workflow._build_drive_diagram_packet(state, digest, module)
    except Exception:
        return {}


def _packet_to_mermaid(packet: dict[str, Any]) -> list[str]:
    lines = ["flowchart LR"]
    defined_nodes: set[str] = set()
    emitted_edges: set[tuple[str, str, str]] = set()

    def emit_node(node_id: str, label: str, shape: str = "box") -> None:
        if node_id in defined_nodes:
            return
        defined_nodes.add(node_id)
        safe_label = str(label).replace('"', "'")
        if shape == "signal":
            lines.append(f'  {node_id}(["{safe_label}"])')
        elif shape == "logic":
            lines.append(f'  {node_id}{{"{safe_label}"}}')
        else:
            lines.append(f'  {node_id}["{safe_label}"]')

    def emit_edge(src: str, dst: str, label: str = "") -> None:
        key = (src, dst, label)
        if key in emitted_edges:
            return
        emitted_edges.add(key)
        if label:
            lines.append(f"  {src} -->|{label}| {dst}")
        else:
            lines.append(f"  {src} --> {dst}")

    for flow_index, flow in enumerate(packet.get("flows", [])[:6], 1):
        previous_signals: list[str] = []
        for step in flow.get("steps", []) or []:
            if step.get("kind") == "port":
                signal = step.get("signal", "")
                if not signal:
                    continue
                signal_id = _mermaid_id("sig", signal)
                emit_node(signal_id, signal, "signal")
                previous_signals = [signal]
                continue
            if step.get("kind") != "component":
                continue
            instance = step.get("instance", "")
            if not instance:
                continue
            module_type = step.get("module_type", "")
            component_id = _mermaid_id("cmp", f"{instance}_{module_type}")
            component_label = f"{instance}:{module_type}" if module_type else instance
            emit_node(component_id, component_label)
            inputs = step.get("inputs", []) or previous_signals
            outputs = step.get("outputs", []) or []
            for signal in inputs:
                signal_id = _mermaid_id("sig", signal)
                emit_node(signal_id, signal, "signal")
                emit_edge(signal_id, component_id, f"F{flow_index}")
            for signal in outputs:
                signal_id = _mermaid_id("sig", signal)
                emit_node(signal_id, signal, "signal")
                emit_edge(component_id, signal_id)
            previous_signals = outputs or previous_signals

    for node in packet.get("logic_nodes", [])[:12]:
        output = node.get("output", "")
        inputs = node.get("inputs", []) or []
        if not output or not inputs:
            continue
        logic_id = _mermaid_id("logic", f"{output}_{node.get('operator', '')}")
        emit_node(logic_id, node.get("operator", "logic"), "logic")
        output_id = _mermaid_id("sig", output)
        emit_node(output_id, output, "signal")
        for signal in inputs[:8]:
            signal_id = _mermaid_id("sig", signal)
            emit_node(signal_id, signal, "signal")
            emit_edge(signal_id, logic_id)
        emit_edge(logic_id, output_id)

    if len(lines) == 1:
        lines.append('  empty["Manual Context 未提供可绘制的 drive flow"]')
    return lines


def _mermaid_id(prefix: str, value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value))
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "node"
    if cleaned[0].isdigit():
        cleaned = f"n_{cleaned}"
    return f"{prefix}_{cleaned}"


def _log(event_logger: Callable[..., None] | None, event_type: str, **payload: Any) -> None:
    if event_logger is None:
        return
    try:
        event_logger(event_type, **payload)
    except Exception:
        pass
