"""Build deterministic Knowledge IR facts from parser pipeline artifacts.

This module is intentionally independent from the legacy manual_ir builder.
It produces AI-readable facts that can later be used for responsibility
enrichment and manual generation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Iterable, List


SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class ParserArtifacts:
    root: Path
    project_index: Dict[str, Any]
    modules: Dict[str, Dict[str, Any]]
    components: Dict[str, Dict[str, Any]]


def build_knowledge_ir(
    artifacts_root: str | Path,
    top_module: str,
    output_dir: str | Path,
    *,
    clean: bool = True,
) -> Dict[str, Any]:
    artifacts = load_parser_artifacts(Path(artifacts_root))
    if top_module not in artifacts.modules:
        raise KeyError(f"top module not found in parser artifacts: {top_module}")

    reachable_modules = collect_reachable_modules(artifacts, top_module)
    root = Path(output_dir)
    if clean and root.exists():
        shutil.rmtree(root)
    modules_dir = root / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)

    module_files: Dict[str, str] = {}
    for module_name in reachable_modules:
        module_payload = artifacts.modules[module_name]
        module_knowledge = build_module_knowledge(artifacts, module_payload, top_module)
        rel_path = f"modules/{safe_filename(module_name)}.json"
        write_json(root / rel_path, module_knowledge)
        module_files[module_name] = rel_path

    project_payload = build_project_knowledge(artifacts, top_module, reachable_modules)
    write_json(root / "project.json", project_payload)

    manifest = {
        "schema": "knowledge_ir_manifest",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "generated_from": {
            "artifacts_root": str(artifacts.root),
            "project_index": "project_index.json",
        },
        "counts": {
            "modules": len(reachable_modules),
        },
        "files": {
            "project": "project.json",
            "modules": module_files,
        },
    }
    write_json(root / "manifest.json", manifest)
    return manifest


def load_parser_artifacts(root: Path) -> ParserArtifacts:
    root = root.resolve()
    project_index = read_json(root / "project_index.json")
    modules = load_json_dir(root / "modules")
    components = load_json_dir(root / "components")
    return ParserArtifacts(
        root=root,
        project_index=project_index,
        modules=modules,
        components=components,
    )


def load_json_dir(path: Path) -> Dict[str, Dict[str, Any]]:
    items: Dict[str, Dict[str, Any]] = {}
    if not path.is_dir():
        return items
    for json_path in sorted(path.glob("*.json")):
        payload = read_json(json_path)
        name = payload.get("name") or json_path.stem
        items[str(name)] = payload
    return items


def collect_reachable_modules(artifacts: ParserArtifacts, top_module: str) -> List[str]:
    visited: set[str] = set()
    ordered: List[str] = []

    def walk(module_name: str) -> None:
        if module_name in visited or module_name not in artifacts.modules:
            return
        visited.add(module_name)
        ordered.append(module_name)
        payload = artifacts.modules[module_name]
        for instance in payload.get("instances", []):
            if instance.get("artifact_kind") == "module":
                walk(str(instance.get("module_type", "")))
        for child_name in payload.get("direct_children", {}).get("modules", []):
            walk(str(child_name))

    walk(top_module)
    return ordered


def build_project_knowledge(
    artifacts: ParserArtifacts,
    top_module: str,
    reachable_modules: List[str],
) -> Dict[str, Any]:
    top_payload = artifacts.modules[top_module]
    families = Counter()
    for module_name in reachable_modules:
        for instance in artifacts.modules[module_name].get("instances", []):
            family = instance.get("family")
            if family:
                families[str(family)] += 1
    return {
        "schema": "knowledge_ir_project_facts",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "source_refs": [
            {
                "source": "project_index.json",
                "paths": ["top_modules", "stats"],
            },
            {
                "source": f"modules/{top_module}.json",
                "paths": ["interface", "direct_children", "transitive_summary"],
            },
        ],
        "top_level": {
            "file": top_payload.get("file", ""),
            "direct_modules": list(top_payload.get("direct_children", {}).get("modules", [])),
            "direct_components": list(top_payload.get("direct_children", {}).get("components", [])),
        },
        "reachable_modules": reachable_modules,
        "component_families": [
            {"family": family, "instance_count": count}
            for family, count in sorted(families.items())
        ],
        "parser_stats": artifacts.project_index.get("stats", {}),
    }


def build_module_knowledge(
    artifacts: ParserArtifacts,
    payload: Dict[str, Any],
    top_module: str,
) -> Dict[str, Any]:
    module_name = str(payload.get("name", ""))
    interface = build_interface_facts(payload)
    key_instances = build_key_instance_facts(payload)
    assignment_facts = build_assignment_facts(payload)
    event_flows = build_internal_event_flows(payload, interface)
    component_families = summarize_component_families(payload)
    evidence_gaps = build_evidence_gaps(payload, interface, event_flows)

    return {
        "schema": "knowledge_ir_module_facts",
        "schema_version": SCHEMA_VERSION,
        "kind": "module_facts",
        "top_module": top_module,
        "module": module_name,
        "module_role": payload.get("module_role", ""),
        "source": {
            "rtl_file": payload.get("file", ""),
            "parser_module": f"modules/{module_name}.json",
        },
        "interface": interface,
        "interface_data_contract": build_interface_data_contract(interface),
        "internal_event_flow": event_flows,
        "assignment_facts": assignment_facts,
        "key_instances": key_instances,
        "component_families": component_families,
        "source_refs": [
            {
                "source": f"modules/{module_name}.json",
                "paths": [
                    "interface.ports",
                    "interface_summary",
                    "instances",
                    "connection_graph",
                    "assignments",
                    "flow_graph.assignment_dependencies",
                ],
            }
        ],
        "evidence_gaps": evidence_gaps,
        "warnings": list(payload.get("warnings", [])),
    }


def build_interface_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    ports = payload.get("interface", {}).get("ports", [])
    reset = payload.get("interface", {}).get("reset", {})
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "event_inputs": [],
        "event_outputs": [],
        "free_inputs": [],
        "free_outputs": [],
        "data_inputs": [],
        "data_outputs": [],
        "control_inputs": [],
        "control_outputs": [],
        "reset_inputs": [],
        "reset_outputs": [],
        "unknown_inputs": [],
        "unknown_outputs": [],
        "inout_ports": [],
    }

    for port in ports:
        if not isinstance(port, dict):
            continue
        port_fact = {
            "name": port.get("name", ""),
            "direction": port.get("direction", ""),
            "width_text": port.get("width_text", "1"),
            "role": classify_signal_role(str(port.get("name", "")), str(port.get("width_text", "1"))),
        }
        bucket = interface_bucket(port_fact)
        buckets[bucket].append(port_fact)

    return {
        **{key: sorted(value, key=lambda item: item["name"]) for key, value in buckets.items()},
        "reset": reset,
        "summary": {
            "event_input_count": len(buckets["event_inputs"]),
            "event_output_count": len(buckets["event_outputs"]),
            "data_input_count": len(buckets["data_inputs"]),
            "data_output_count": len(buckets["data_outputs"]),
            "free_input_count": len(buckets["free_inputs"]),
            "free_output_count": len(buckets["free_outputs"]),
        },
    }


def interface_bucket(port: Dict[str, Any]) -> str:
    direction = port.get("direction", "")
    role = port.get("role", "unknown")
    if direction == "inout":
        return "inout_ports"
    suffix = "inputs" if direction == "input" else "outputs"
    if role == "event_drive":
        return f"event_{suffix}"
    if role == "event_free":
        return f"free_{suffix}"
    if role == "payload_data":
        return f"data_{suffix}"
    if role == "reset":
        return f"reset_{suffix}"
    if role == "condition":
        return f"control_{suffix}"
    return f"unknown_{suffix}"


def build_interface_data_contract(interface: Dict[str, Any]) -> List[Dict[str, Any]]:
    contracts: List[Dict[str, Any]] = []
    contracts.extend(match_event_payloads(interface, direction="input"))
    contracts.extend(match_event_payloads(interface, direction="output"))
    return contracts


def match_event_payloads(interface: Dict[str, Any], *, direction: str) -> List[Dict[str, Any]]:
    event_key = "event_inputs" if direction == "input" else "event_outputs"
    data_key = "data_inputs" if direction == "input" else "data_outputs"
    free_key = "free_outputs" if direction == "input" else "free_inputs"
    events = interface.get(event_key, [])
    payloads = interface.get(data_key, [])
    frees = interface.get(free_key, [])
    contracts: List[Dict[str, Any]] = []

    for event in events:
        payload_matches = best_related_ports(event["name"], payloads)
        free_matches = rank_related_ports(event["name"], frees)
        selected_payloads = payload_matches[:3]
        selected_free = free_matches[0]["name"] if free_matches else ""
        confidence = "medium" if selected_payloads else "low"
        if len(payloads) == 1 and not selected_payloads:
            selected_payloads = [payloads[0]]
            confidence = "low"
        contracts.append(
            {
                "event": event["name"],
                "direction": direction,
                "payloads": [
                    {
                        "name": item["name"],
                        "width_text": item.get("width_text", "1"),
                    }
                    for item in selected_payloads
                ],
                "free_signal": selected_free,
                "confidence": confidence,
                "evidence": [
                    "interface.event_ports",
                    "interface.data_ports",
                ],
            }
        )
    return contracts


def rank_related_ports(seed_name: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seed_tokens = signal_tokens(seed_name)
    ranked = []
    for candidate in candidates:
        score = len(seed_tokens & signal_tokens(candidate.get("name", "")))
        if score <= 0:
            continue
        ranked.append((score, candidate.get("name", ""), candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked]


def best_related_ports(seed_name: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seed_tokens = signal_tokens(seed_name)
    ranked = []
    for candidate in candidates:
        score = len(seed_tokens & signal_tokens(candidate.get("name", "")))
        if score <= 0:
            continue
        ranked.append((score, candidate.get("name", ""), candidate))
    if not ranked:
        return []
    max_score = max(item[0] for item in ranked)
    return [
        item[2]
        for item in sorted(ranked, key=lambda item: item[1])
        if item[0] == max_score
    ]


def build_key_instance_facts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for instance in payload.get("instances", []):
        connections = instance.get("connections", [])
        fact = {
            "instance": instance.get("instance_name", ""),
            "module_type": instance.get("module_type", ""),
            "artifact_kind": instance.get("artifact_kind", ""),
            "family": instance.get("family", ""),
            "input_events": connection_signals(connections, direction="input", role="event_drive"),
            "output_events": connection_signals(connections, direction="output", role="event_drive"),
            "input_free": connection_signals(connections, direction="input", role="event_free"),
            "output_free": connection_signals(connections, direction="output", role="event_free"),
            "input_data": connection_signals(connections, direction="input", role="payload_data"),
            "output_data": connection_signals(connections, direction="output", role="payload_data"),
        }
        if any(fact[key] for key in ("input_events", "output_events", "input_data", "output_data")):
            facts.append(fact)
    return sorted(facts, key=lambda item: item["instance"])


def connection_signals(connections: List[Dict[str, Any]], *, direction: str, role: str) -> List[str]:
    values: List[str] = []
    for connection in connections:
        signal = str(connection.get("signal", ""))
        if connection.get("port_direction") != direction:
            continue
        signal_role = connection.get("signal_role") or classify_signal_role(signal)
        if signal_role != role:
            continue
        for term in connection.get("signal_terms", []) or [signal]:
            if isinstance(term, str) and term and term not in values:
                values.append(term)
    return sorted(values)


def build_assignment_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    assignments = payload.get("assignments", [])
    ports = {
        port.get("name"): port
        for port in payload.get("interface", {}).get("ports", [])
        if isinstance(port, dict)
    }
    port_names = set(ports)
    facts = []
    for assignment in assignments:
        lhs_terms = [item for item in assignment.get("lhs_terms", []) if isinstance(item, str)]
        rhs_terms = [item for item in assignment.get("rhs_terms", []) if isinstance(item, str)]
        fact = {
            "index": assignment.get("index"),
            "lhs": assignment.get("lhs", ""),
            "rhs": assignment.get("rhs", ""),
            "lhs_terms": lhs_terms,
            "rhs_terms": rhs_terms,
            "lhs_interface_terms": sorted(set(lhs_terms) & port_names),
            "rhs_interface_terms": sorted(set(rhs_terms) & port_names),
            "kind": assignment.get("kind", "continuous_assign"),
        }
        fact["interface_related"] = bool(fact["lhs_interface_terms"] or fact["rhs_interface_terms"])
        facts.append(fact)
    dependencies = payload.get("flow_graph", {}).get("assignment_dependencies", [])
    return {
        "continuous_assignments": facts,
        "dependencies": dependencies,
        "summary": {
            "assignment_count": len(facts),
            "dependency_count": len(dependencies),
            "interface_related_assignment_count": sum(1 for item in facts if item["interface_related"]),
        },
    }


def build_internal_event_flows(payload: Dict[str, Any], interface: Dict[str, Any]) -> List[Dict[str, Any]]:
    signal_to_instances, instance_flows = build_event_graph(payload)
    output_drives = {item["name"] for item in interface.get("event_outputs", [])}
    flows = []
    for start in interface.get("event_inputs", []):
        flows.append(trace_event_flow(start["name"], output_drives, signal_to_instances, instance_flows))
    return flows


def build_event_graph(payload: Dict[str, Any]) -> tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
    signal_to_instances: Dict[str, List[str]] = defaultdict(list)
    instance_flows: Dict[str, Dict[str, Any]] = {}
    for instance in payload.get("instances", []):
        instance_name = str(instance.get("instance_name", ""))
        if not instance_name:
            continue
        input_drives: List[str] = []
        output_drives: List[str] = []
        for connection in instance.get("connections", []):
            signal_names = connection_terms(connection)
            if not signal_names or not is_event_drive_connection(connection):
                continue
            if connection.get("port_direction") == "input":
                input_drives.extend(signal_names)
                for signal_name in signal_names:
                    if instance_name not in signal_to_instances[signal_name]:
                        signal_to_instances[signal_name].append(instance_name)
            elif connection.get("port_direction") == "output":
                output_drives.extend(signal_names)
        if input_drives or output_drives:
            instance_flows[instance_name] = {
                "instance": instance_name,
                "module_type": instance.get("module_type", ""),
                "artifact_kind": instance.get("artifact_kind", ""),
                "family": instance.get("family", ""),
                "input_drives": sorted(set(input_drives)),
                "output_drives": sorted(set(output_drives)),
                "role": instance_role(instance),
            }

    for transparent_flow in payload.get("transparent_flows", []):
        if transparent_flow.get("signal_role") != "event_drive":
            continue
        instance_name = str(transparent_flow.get("instance_name", ""))
        input_signal = str(transparent_flow.get("input_signal", ""))
        output_signal = str(transparent_flow.get("output_signal", ""))
        if not instance_name or not input_signal or not output_signal:
            continue
        if instance_name not in signal_to_instances[input_signal]:
            signal_to_instances[input_signal].append(instance_name)
        instance_flows[instance_name] = {
            "instance": instance_name,
            "module_type": transparent_flow.get("module_type", ""),
            "artifact_kind": "transparent_helper",
            "family": "",
            "input_drives": [input_signal],
            "output_drives": [output_signal],
            "role": "transparent_delay",
        }
    return dict(signal_to_instances), instance_flows


def trace_event_flow(
    start_signal: str,
    output_drives: set[str],
    signal_to_instances: Dict[str, List[str]],
    instance_flows: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    endpoints: List[str] = []
    branch_points: List[Dict[str, str]] = []
    join_points: List[Dict[str, str]] = []
    blocking_points: List[Dict[str, str]] = []
    visited_signals: set[str] = set()
    visited_instances: set[str] = set()
    queue = [start_signal]
    limit = 512

    while queue and len(visited_signals) + len(visited_instances) < limit:
        signal_name = queue.pop(0)
        if signal_name in visited_signals:
            continue
        visited_signals.add(signal_name)
        if signal_name in output_drives and signal_name not in endpoints:
            endpoints.append(signal_name)
        for instance_name in signal_to_instances.get(signal_name, []):
            instance = instance_flows.get(instance_name)
            if not instance:
                continue
            if instance_name not in visited_instances:
                visited_instances.add(instance_name)
                steps.append(
                    {
                        "order": len(steps) + 1,
                        "instance": instance_name,
                        "module_type": instance.get("module_type", ""),
                        "artifact_kind": instance.get("artifact_kind", ""),
                        "family": instance.get("family", ""),
                        "role": instance.get("role", ""),
                        "input_drives": instance.get("input_drives", []),
                        "output_drives": instance.get("output_drives", []),
                    }
                )
                append_event_flow_points(instance, branch_points, join_points, blocking_points)
            for output_signal in instance.get("output_drives", []):
                if output_signal not in visited_signals and output_signal not in queue:
                    queue.append(output_signal)

    warnings = []
    if queue:
        warnings.append("event traversal stopped after reaching traversal limit")
    if not endpoints:
        warnings.append(f"no module event output reached from {start_signal}")
    return {
        "start": start_signal,
        "endpoints": endpoints,
        "steps": steps,
        "branch_points": dedupe_dicts(branch_points),
        "join_points": dedupe_dicts(join_points),
        "blocking_points": dedupe_dicts(blocking_points),
        "confidence": "medium" if endpoints else "low",
        "warnings": warnings,
        "evidence": ["instances.connections", "transparent_flows"],
    }


def append_event_flow_points(
    instance: Dict[str, Any],
    branch_points: List[Dict[str, str]],
    join_points: List[Dict[str, str]],
    blocking_points: List[Dict[str, str]],
) -> None:
    role = str(instance.get("role", ""))
    name = str(instance.get("instance", ""))
    if len(instance.get("output_drives", [])) > 1 or role == "splitter":
        branch_points.append({"node": name, "reason": "event may branch through this instance"})
    if len(instance.get("input_drives", [])) > 1 or role in {"merger", "arbiter"}:
        join_points.append({"node": name, "reason": "event paths may merge or arbitrate here"})
    if role in {"fifo", "fifo_stage", "merger", "arbiter"}:
        blocking_points.append({"node": name, "reason": f"{role} may gate event propagation"})


def summarize_component_families(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    counter = Counter()
    examples: Dict[str, List[str]] = defaultdict(list)
    for instance in payload.get("instances", []):
        family = instance.get("family")
        if not family:
            continue
        family = str(family)
        counter[family] += 1
        instance_name = str(instance.get("instance_name", ""))
        if instance_name and len(examples[family]) < 8:
            examples[family].append(instance_name)
    return [
        {
            "family": family,
            "instance_count": count,
            "example_instances": examples[family],
        }
        for family, count in sorted(counter.items())
    ]


def build_evidence_gaps(
    payload: Dict[str, Any],
    interface: Dict[str, Any],
    event_flows: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    gaps: List[Dict[str, str]] = []
    if not payload.get("connection_graph"):
        gaps.append({"field": "connection_graph", "reason": "parser module has no connection_graph"})
    if interface["summary"]["event_input_count"] and not event_flows:
        gaps.append({"field": "internal_event_flow", "reason": "event inputs exist but no event flow was built"})
    for flow in event_flows:
        for warning in flow.get("warnings", []):
            gaps.append({"field": f"internal_event_flow.{flow.get('start')}", "reason": warning})
    for warning in payload.get("warnings", []):
        gaps.append({"field": "parser_warnings", "reason": str(warning)})
    return gaps


def classify_signal_role(name: str, width_text: str = "1") -> str:
    lowered = name.strip().lower()
    if re.match(r"^(rst|rstn|reset)\b", lowered):
        return "reset"
    if "drive" in lowered or re.search(r"(^|_)drv|^[iow]_drv", lowered):
        return "event_drive"
    if "free" in lowered:
        return "event_free"
    if "data" in lowered:
        return "payload_data"
    if (
        "valid" in lowered
        or lowered.startswith("sel")
        or "switch" in lowered
        or "permit" in lowered
        or "flag" in lowered
        or "wen" in lowered
        or "mode" in lowered
        or "type" in lowered
        or "code" in lowered
    ):
        return "condition"
    if width_text and width_text != "1":
        return "payload_data"
    return "unknown"


def is_event_drive_connection(connection: Dict[str, Any]) -> bool:
    signal = str(connection.get("signal", ""))
    port = str(connection.get("port", ""))
    return (
        connection.get("signal_role") == "event_drive"
        or classify_signal_role(signal) == "event_drive"
        or classify_signal_role(port) == "event_drive"
    )


def connection_terms(connection: Dict[str, Any]) -> List[str]:
    terms = connection.get("signal_terms")
    if isinstance(terms, list) and terms:
        return [term for term in terms if isinstance(term, str) and term]
    signal = connection.get("signal")
    return [signal] if isinstance(signal, str) and signal else []


def instance_role(instance: Dict[str, Any]) -> str:
    family = str(instance.get("family", ""))
    if family:
        return family_to_role(family)
    if instance.get("artifact_kind") == "module":
        return "module_instance"
    return "unknown"


def family_to_role(family: str) -> str:
    lowered = family.lower()
    if "fifo" in lowered:
        return "fifo_stage"
    if "split" in lowered or "selector" in lowered or "selsplit" in lowered:
        return "splitter"
    if "merge" in lowered:
        return "merger"
    if "arb" in lowered:
        return "arbiter"
    return lowered or "unknown"


def signal_tokens(name: str) -> set[str]:
    normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    tokens = {
        normalize_signal_token(token.lower())
        for token in re.split(r"[^A-Za-z0-9]+", normalized)
        if token
    }
    stop_words = {
        "i",
        "o",
        "w",
        "drive",
        "drv",
        "free",
        "data",
        "to",
        "from",
        "next",
    }
    return {
        token
        for token in tokens
        if token not in stop_words and not token.isdigit()
    }


def normalize_signal_token(token: str) -> str:
    aliases = {
        "exe": "execute",
        "exec": "execute",
        "lunch": "launch",
        "dec": "decoder",
        "deco": "decoder",
        "wb": "writeback",
        "grfw": "grf",
        "psr": "prf",
        "psrw": "prf",
    }
    return aliases.get(token, token)


def dedupe_dicts(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[str] = set()
    deduped: List[Dict[str, str]] = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_filename(name: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in name)
    return safe.strip("._") or "module"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Knowledge IR module facts.")
    parser.add_argument("--artifacts-root", default="rtl/parser_pipeline_rtl")
    parser.add_argument("--top-module", default="arm_soc_top")
    parser.add_argument("--output-root", default="rtl/knowledge_ir")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove an existing top-module output directory.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    output_dir = Path(args.output_root) / args.top_module
    manifest = build_knowledge_ir(
        args.artifacts_root,
        args.top_module,
        output_dir,
        clean=not args.no_clean,
    )
    print(json.dumps({
        "status": "passed",
        "output_dir": str(output_dir),
        "counts": manifest.get("counts", {}),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
