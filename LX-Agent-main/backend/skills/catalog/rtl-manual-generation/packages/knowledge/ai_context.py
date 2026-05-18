"""Build compact AI contexts from deterministic Knowledge IR facts."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, List


SCHEMA_VERSION = "0.1"
MAX_FLOW_STEPS = 48
MAX_CONNECTIONS = 80
MAX_ASSIGNMENTS = 80
MAX_INSTANCES = 80


def build_ai_context(
    knowledge_dir: str | Path,
    parser_artifacts_root: str | Path,
    *,
    clean: bool = True,
) -> Dict[str, Any]:
    knowledge_root = Path(knowledge_dir)
    parser_root = Path(parser_artifacts_root)
    manifest = read_json(knowledge_root / "manifest.json")
    top_module = str(manifest.get("top_module", ""))
    output_root = knowledge_root / "ai_context"
    modules_out = output_root / "modules"
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    modules_out.mkdir(parents=True, exist_ok=True)

    module_files = manifest.get("files", {}).get("modules", {})
    if not isinstance(module_files, dict):
        raise ValueError("knowledge manifest files.modules must be an object")

    context_files: Dict[str, str] = {}
    flow_files: Dict[str, List[str]] = {}
    for module_name, rel_path in sorted(module_files.items()):
        if not isinstance(rel_path, str):
            continue
        facts = read_json(knowledge_root / rel_path)
        parser_module_path = parser_root / "modules" / f"{module_name}.json"
        parser_module = read_json(parser_module_path) if parser_module_path.is_file() else {}
        parts = build_module_ai_context_parts(facts, parser_module)

        module_flow_files: List[str] = []
        flow_refs = []
        for flow_index, flow in enumerate(parts["event_flows"]):
            flow_id = build_flow_id(str(module_name), flow, flow_index)
            flow_rel = (
                f"ai_context/modules/{safe_filename(str(module_name))}/"
                f"flows/{safe_filename(flow_id)}.json"
            )
            flow_context = build_flow_ai_context(
                facts=facts,
                parser_module=parser_module,
                flow=flow,
                flow_id=flow_id,
                connection_context=parts["connection_context"],
                assignment_context=parts["assignment_context"],
            )
            write_json(knowledge_root / flow_rel, flow_context)
            module_flow_files.append(flow_rel)
            flow_refs.append(
                {
                    "flow_id": flow_id,
                    "file": flow_rel,
                    "start": flow.get("start", ""),
                    "endpoints": flow.get("endpoints", []),
                    "step_count": len(flow.get("steps", [])),
                    "confidence": flow.get("confidence", ""),
                    "truncated": flow.get("truncated", False),
                }
            )

        context = build_module_ai_context(facts, parser_module, parts, flow_refs)
        out_rel = f"ai_context/modules/{safe_filename(str(module_name))}.json"
        write_json(knowledge_root / out_rel, context)
        context_files[str(module_name)] = out_rel
        flow_files[str(module_name)] = module_flow_files

    index = {
        "schema": "knowledge_ir_ai_context_index",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "generated_from": {
            "knowledge_manifest": "manifest.json",
            "parser_artifacts_root": str(parser_root.resolve()),
        },
        "counts": {
            "modules": len(context_files),
            "flows": sum(len(items) for items in flow_files.values()),
        },
        "files": {
            "modules": context_files,
            "flows": flow_files,
        },
    }
    write_json(output_root / "index.json", index)
    update_manifest_with_ai_context(knowledge_root / "manifest.json", manifest, context_files, flow_files)
    return index


def build_module_ai_context_parts(facts: Dict[str, Any], parser_module: Dict[str, Any]) -> Dict[str, Any]:
    compact_interface = compact_interface_context(facts)
    event_flows = compact_event_flows(facts.get("internal_event_flow", []))
    connection_context = select_key_connections(parser_module, facts)
    assignment_context = select_key_assignments(facts, connection_context)
    instance_context = select_key_instances(facts)
    return {
        "compact_interface": compact_interface,
        "event_flows": event_flows,
        "connection_context": connection_context,
        "assignment_context": assignment_context,
        "instance_context": instance_context,
    }


def build_module_ai_context(
    facts: Dict[str, Any],
    parser_module: Dict[str, Any],
    parts: Dict[str, Any],
    flow_refs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    module_name = str(facts.get("module", ""))
    return {
        "schema": "knowledge_ir_module_ai_context",
        "schema_version": SCHEMA_VERSION,
        "kind": "module_ai_context",
        "top_module": facts.get("top_module", ""),
        "module": module_name,
        "source": facts.get("source", {}),
        "question_for_ai": (
            "Infer module responsibility and implementation notes only from this compact context. "
            "Prioritize drive-based internal event flow, interface payload contracts, key component "
            "connections, and assign dependencies. Preserve evidence gaps instead of guessing."
        ),
        "compact_context": {
            "interface": parts["compact_interface"],
            "event_payload_contracts": facts.get("interface_data_contract", []),
            "internal_event_flow_refs": flow_refs,
            "key_component_connections": parts["connection_context"]["connections"],
            "assign_dependencies": parts["assignment_context"],
            "key_instances": parts["instance_context"],
            "component_families": facts.get("component_families", []),
            "evidence_gaps": facts.get("evidence_gaps", []),
            "warnings": facts.get("warnings", []),
        },
        "selection_summary": {
            "event_flow_count": len(flow_refs),
            "selected_connection_count": len(parts["connection_context"]["connections"]),
            "selected_assignment_count": len(parts["assignment_context"]),
            "selected_instance_count": len(parts["instance_context"]),
            "connection_selection_reasons": parts["connection_context"]["selection_reasons"],
        },
        "evidence_index": build_evidence_index(facts, parser_module),
    }


def build_flow_ai_context(
    *,
    facts: Dict[str, Any],
    parser_module: Dict[str, Any],
    flow: Dict[str, Any],
    flow_id: str,
    connection_context: Dict[str, Any],
    assignment_context: List[Dict[str, Any]],
) -> Dict[str, Any]:
    module_name = str(facts.get("module", ""))
    flow_signals = collect_one_flow_signals(flow)
    payload_contracts = [
        item
        for item in facts.get("interface_data_contract", [])
        if item.get("event") == flow.get("start")
        or item.get("event") in flow.get("endpoints", [])
    ]
    payload_signals = {
        payload.get("name")
        for contract in payload_contracts
        for payload in contract.get("payloads", [])
        if isinstance(payload, dict) and payload.get("name")
    }
    related_signals = flow_signals | set(str(item) for item in payload_signals if item)
    related_connections = [
        item
        for item in connection_context.get("connections", [])
        if item.get("signal") in related_signals
    ]
    related_assignments = [
        item
        for item in assignment_context
        if set(item.get("lhs_terms", []) + item.get("rhs_terms", [])) & related_signals
    ]
    return {
        "schema": "knowledge_ir_module_flow_ai_context",
        "schema_version": SCHEMA_VERSION,
        "kind": "module_flow_ai_context",
        "top_module": facts.get("top_module", ""),
        "module": module_name,
        "flow_id": flow_id,
        "source": facts.get("source", {}),
        "question_for_ai": (
            "Explain this single drive-based internal event flow using only the supplied "
            "steps, related component connections, and assign dependencies."
        ),
        "compact_context": {
            "flow": flow,
            "related_component_connections": related_connections,
            "related_assign_dependencies": related_assignments,
            "interface_payload_contracts": payload_contracts,
        },
        "selection_summary": {
            "flow_signal_count": len(flow_signals),
            "payload_signal_count": len(payload_signals),
            "related_connection_count": len(related_connections),
            "related_assignment_count": len(related_assignments),
        },
        "evidence_index": build_evidence_index(facts, parser_module),
    }


def compact_interface_context(facts: Dict[str, Any]) -> Dict[str, Any]:
    interface = facts.get("interface", {})
    return {
        "event_inputs": simple_ports(interface.get("event_inputs", [])),
        "event_outputs": simple_ports(interface.get("event_outputs", [])),
        "data_inputs": simple_ports(interface.get("data_inputs", [])),
        "data_outputs": simple_ports(interface.get("data_outputs", [])),
        "free_inputs": simple_ports(interface.get("free_inputs", [])),
        "free_outputs": simple_ports(interface.get("free_outputs", [])),
        "control_inputs": simple_ports(interface.get("control_inputs", [])),
        "control_outputs": simple_ports(interface.get("control_outputs", [])),
        "reset": interface.get("reset", {}),
        "summary": interface.get("summary", {}),
    }


def simple_ports(ports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "name": item.get("name", ""),
            "width_text": item.get("width_text", "1"),
            "role": item.get("role", ""),
        }
        for item in ports
        if isinstance(item, dict)
    ]


def compact_event_flows(flows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(
        flows,
        key=lambda flow: (
            flow.get("confidence") != "medium",
            -len(flow.get("endpoints", [])),
            -len(flow.get("branch_points", [])),
            -len(flow.get("join_points", [])),
            flow.get("start", ""),
        ),
    )
    compacted = []
    for flow in ranked:
        steps = flow.get("steps", [])
        compacted.append(
            {
                "start": flow.get("start", ""),
                "endpoints": flow.get("endpoints", []),
                "steps": compact_flow_steps(steps),
                "branch_points": flow.get("branch_points", []),
                "join_points": flow.get("join_points", []),
                "blocking_points": flow.get("blocking_points", []),
                "confidence": flow.get("confidence", ""),
                "warnings": flow.get("warnings", []),
                "truncated": len(steps) > MAX_FLOW_STEPS,
                "evidence": flow.get("evidence", []),
            }
        )
    return compacted


def compact_flow_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compacted = []
    for step in steps[:MAX_FLOW_STEPS]:
        compacted.append(
            {
                "order": step.get("order"),
                "instance": step.get("instance", ""),
                "module_type": step.get("module_type", ""),
                "family": step.get("family", ""),
                "role": step.get("role", ""),
                "input_drives": step.get("input_drives", []),
                "output_drives": step.get("output_drives", []),
            }
        )
    return compacted


def select_key_connections(parser_module: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    connection_graph = parser_module.get("connection_graph", {})
    connections = connection_graph.get("connections", [])
    event_signals = collect_event_flow_signals(facts.get("internal_event_flow", []))
    interface_names = collect_interface_names(facts.get("interface", {}))
    assignment_signals = collect_assignment_signals(facts.get("assignment_facts", {}))

    selected = []
    reason_counter = Counter()
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        signal = str(connection.get("signal", ""))
        role = str(connection.get("role", ""))
        reasons = []
        if signal in event_signals or role == "event_drive":
            reasons.append("event_flow")
        if signal in interface_names:
            reasons.append("module_boundary")
        if signal in assignment_signals:
            reasons.append("assign_related")
        touches_component = endpoint_is_component(connection.get("from", {})) or endpoint_is_component(connection.get("to", {}))
        if not reasons:
            continue
        if touches_component:
            reasons.append("component_connection")
        for reason in reasons:
            reason_counter[reason] += 1
        selected.append(
            {
                "from": format_endpoint(connection.get("from", {})),
                "to": format_endpoint(connection.get("to", {})),
                "signal": signal,
                "role": role,
                "reasons": sorted(set(reasons)),
            }
        )

    selected = sorted(
        selected,
        key=lambda item: (
            "event_flow" not in item["reasons"],
            "module_boundary" not in item["reasons"],
            item["signal"],
            item["from"],
            item["to"],
        ),
    )[:MAX_CONNECTIONS]
    return {
        "connections": selected,
        "selection_reasons": dict(sorted(reason_counter.items())),
    }


def select_key_assignments(facts: Dict[str, Any], connection_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    assignment_facts = facts.get("assignment_facts", {})
    assignments = assignment_facts.get("continuous_assignments", [])
    connected_signals = {
        item.get("signal")
        for item in connection_context.get("connections", [])
        if isinstance(item, dict)
    }
    interface_names = collect_interface_names(facts.get("interface", {}))
    selected = []
    for assignment in assignments:
        lhs_terms = set(assignment.get("lhs_terms", []))
        rhs_terms = set(assignment.get("rhs_terms", []))
        all_terms = lhs_terms | rhs_terms
        reasons = []
        if assignment.get("interface_related") or all_terms & interface_names:
            reasons.append("interface_related")
        if all_terms & connected_signals:
            reasons.append("connection_related")
        if any(is_payload_like(term) for term in all_terms):
            reasons.append("payload_or_data")
        if not reasons:
            continue
        selected.append(
            {
                "index": assignment.get("index"),
                "lhs": assignment.get("lhs", ""),
                "rhs": assignment.get("rhs", ""),
                "lhs_terms": assignment.get("lhs_terms", []),
                "rhs_terms": assignment.get("rhs_terms", []),
                "reasons": sorted(set(reasons)),
            }
        )
    return sorted(
        selected,
        key=lambda item: (
            "interface_related" not in item["reasons"],
            item.get("index") if item.get("index") is not None else 10**9,
        ),
    )[:MAX_ASSIGNMENTS]


def select_key_instances(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    instances = facts.get("key_instances", [])
    ranked = sorted(
        instances,
        key=lambda item: (
            not item.get("input_events") and not item.get("output_events"),
            item.get("family", ""),
            item.get("instance", ""),
        ),
    )
    selected = []
    for instance in ranked[:MAX_INSTANCES]:
        selected.append(
            {
                "instance": instance.get("instance", ""),
                "module_type": instance.get("module_type", ""),
                "artifact_kind": instance.get("artifact_kind", ""),
                "family": instance.get("family", ""),
                "input_events": instance.get("input_events", []),
                "output_events": instance.get("output_events", []),
                "input_data": instance.get("input_data", []),
                "output_data": instance.get("output_data", []),
            }
        )
    return selected


def build_evidence_index(facts: Dict[str, Any], parser_module: Dict[str, Any]) -> List[Dict[str, Any]]:
    module_name = str(facts.get("module", ""))
    entries = [
        {
            "id": "module_facts",
            "source": f"knowledge_ir/modules/{module_name}.json",
            "paths": [
                "interface",
                "interface_data_contract",
                "internal_event_flow",
                "assignment_facts",
                "key_instances",
            ],
        },
        {
            "id": "parser_module",
            "source": f"parser_pipeline_rtl/modules/{module_name}.json",
            "paths": [
                "interface",
                "instances",
                "connection_graph",
                "assignments",
                "flow_graph.assignment_dependencies",
            ],
        },
    ]
    if parser_module.get("file"):
        entries.append(
            {
                "id": "rtl_source",
                "source": parser_module.get("file", ""),
                "paths": ["module_source"],
            }
        )
    return entries


def collect_event_flow_signals(flows: List[Dict[str, Any]]) -> set[str]:
    signals = set()
    for flow in flows:
        if flow.get("start"):
            signals.add(str(flow["start"]))
        for endpoint in flow.get("endpoints", []):
            signals.add(str(endpoint))
        for step in flow.get("steps", []):
            signals.update(str(item) for item in step.get("input_drives", []))
            signals.update(str(item) for item in step.get("output_drives", []))
    return signals


def collect_one_flow_signals(flow: Dict[str, Any]) -> set[str]:
    signals = set()
    if flow.get("start"):
        signals.add(str(flow["start"]))
    for endpoint in flow.get("endpoints", []):
        signals.add(str(endpoint))
    for step in flow.get("steps", []):
        signals.update(str(item) for item in step.get("input_drives", []))
        signals.update(str(item) for item in step.get("output_drives", []))
    return signals


def build_flow_id(module_name: str, flow: Dict[str, Any], flow_index: int) -> str:
    start = safe_filename(str(flow.get("start", "")))
    return f"flow_{flow_index:03d}_{safe_filename(module_name)}_{start}"


def collect_interface_names(interface: Dict[str, Any]) -> set[str]:
    names = set()
    for key, value in interface.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    return names


def collect_assignment_signals(assignment_facts: Dict[str, Any]) -> set[str]:
    signals = set()
    for assignment in assignment_facts.get("continuous_assignments", []):
        signals.update(str(item) for item in assignment.get("lhs_terms", []))
        signals.update(str(item) for item in assignment.get("rhs_terms", []))
    return signals


def endpoint_is_component(endpoint: Dict[str, Any]) -> bool:
    kind = str(endpoint.get("kind", ""))
    return kind in {"instance_input", "instance_output"} and endpoint.get("node") != "self"


def format_endpoint(endpoint: Dict[str, Any]) -> str:
    node = str(endpoint.get("node", ""))
    port = str(endpoint.get("port", ""))
    if not node:
        return port
    if not port:
        return node
    return f"{node}.{port}"


def is_payload_like(signal: str) -> bool:
    lowered = signal.lower()
    return "data" in lowered or bool(lowered.endswith(("_32", "_64", "_96", "_128", "_207")))


def update_manifest_with_ai_context(
    manifest_path: Path,
    manifest: Dict[str, Any],
    context_files: Dict[str, str],
    flow_files: Dict[str, List[str]],
) -> None:
    files = manifest.setdefault("files", {})
    files["ai_context"] = {
        "index": "ai_context/index.json",
        "modules": context_files,
        "flows": flow_files,
    }
    counts = manifest.setdefault("counts", {})
    counts["ai_context_modules"] = len(context_files)
    counts["ai_context_flows"] = sum(len(items) for items in flow_files.values())
    write_json(manifest_path, manifest)


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_filename(name: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in name)
    return safe.strip("._") or "module"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build compact AI contexts from Knowledge IR facts.")
    parser.add_argument("--knowledge-dir", default="rtl/knowledge_ir/arm_soc_top")
    parser.add_argument("--parser-artifacts-root", default="rtl/parser_pipeline_rtl")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    index = build_ai_context(
        args.knowledge_dir,
        args.parser_artifacts_root,
        clean=not args.no_clean,
    )
    print(json.dumps({
        "status": "passed",
        "knowledge_dir": args.knowledge_dir,
        "counts": index.get("counts", {}),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
