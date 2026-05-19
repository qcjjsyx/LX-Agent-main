"""Build Manual Context Layer files for RTL code manual generation.

The Manual Context Layer is a documentation-facing contract.  It consumes
deterministic Knowledge IR, compact AI context, optional Semantic Layer claims,
and parser artifacts, then writes stable JSON files organized around the final
manual pages.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, List


SCHEMA_VERSION = "0.1"
DEFAULT_DOC_FOCUS = {
    "primary_event": "drive",
    "secondary_events": ["free"],
    "primary_topics": [
        "module_responsibility",
        "interface_data_contract",
        "internal_drive_flow",
        "cross_module_data_event_flow",
    ],
    "deemphasize": [
        "free_signal_details_unless_backpressure_affects_drive_availability",
    ],
}

DOC_PRIORITIES = {"primary", "secondary", "reference"}
MANUAL_IMPORTANCE_LEVELS = {"high", "medium", "low"}
DETERMINISTIC = "deterministic_fact"
DERIVED = "derived_fact"
AI_INFERRED = "ai_inferred"
HUMAN_ASSERTED = "human_asserted"
EVIDENCE_GAP = "evidence_gap"

MODULE_ROLE_CLAIMS = {
    "module_role",
    "structural_responsibility",
    "documentation_focus",
}
INTERFACE_CLAIMS = {"interface_intent"}
ASSIGNMENT_CLAIMS = {"assignment_interpretation"}
FLOW_MEANING_CLAIMS = {
    "flow_intent",
    "documentation_focus",
    "data_control_effect",
    "completion_backpressure",
}
COMPONENT_ROLE_CLAIMS = {"component_role"}


def build_manual_context(
    knowledge_dir: str | Path,
    parser_artifacts_root: str | Path,
    output_dir: str | Path | None = None,
    *,
    clean: bool = True,
    include_semantic: bool = True,
) -> Dict[str, Any]:
    """Write Manual Context Layer files and return the manifest payload."""

    knowledge_root = Path(knowledge_dir)
    parser_root = Path(parser_artifacts_root)
    manifest = read_json(knowledge_root / "manifest.json")
    top_module = str(manifest.get("top_module", ""))
    if not top_module:
        raise ValueError("knowledge manifest is missing top_module")

    out_root = Path(output_dir) if output_dir else Path("rtl/manual_context") / top_module
    if clean and out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    project_facts = read_json(knowledge_root / str(manifest.get("files", {}).get("project", "project.json")))
    parser_index = read_optional_json(parser_root / "project_index.json")
    parser_modules = load_parser_modules(parser_root)
    ai_index = read_optional_json(knowledge_root / "ai_context" / "index.json")
    semantic_index = read_optional_json(knowledge_root / "semantic" / "index.json") if include_semantic else {}

    module_files = manifest.get("files", {}).get("modules", {})
    if not isinstance(module_files, dict):
        raise ValueError("knowledge manifest files.modules must be an object")

    topology = build_topology(module_files, parser_modules)
    peer_index = build_peer_index(parser_modules)
    semantic_modules = load_semantic_modules(knowledge_root, semantic_index)
    semantic_flows = load_semantic_flows(knowledge_root, semantic_index)

    module_context_files: Dict[str, str] = {}
    interface_context_files: Dict[str, str] = {}
    gap_files: Dict[str, str] = {}
    flow_context_files: Dict[str, List[str]] = {}
    flow_index_items: List[Dict[str, Any]] = []
    interface_index_items: List[Dict[str, Any]] = []
    evidence_entries: Dict[str, Dict[str, Any]] = {}
    module_facts_by_name: Dict[str, Dict[str, Any]] = {}

    for module_name, rel_path in sorted(module_files.items()):
        if not isinstance(rel_path, str):
            continue
        facts = read_json(knowledge_root / rel_path)
        module_facts_by_name[str(module_name)] = facts
        parser_module = parser_modules.get(str(module_name), {})
        ai_module = read_ai_module_context(knowledge_root, ai_index, str(module_name))
        module_semantic = semantic_modules.get(str(module_name), {})
        flow_cards = semantic_flows.get(str(module_name), {})

        add_module_evidence(
            evidence_entries,
            top_module,
            str(module_name),
            facts,
            parser_module,
            knowledge_rel=rel_path,
            semantic_rel=semantic_module_rel(semantic_index, str(module_name)),
        )

        flow_infos = build_flow_infos(
            knowledge_root=knowledge_root,
            ai_index=ai_index,
            module_name=str(module_name),
            facts=facts,
            semantic_flow_cards=flow_cards,
            evidence_entries=evidence_entries,
            top_module=top_module,
        )

        interfaces = build_module_interfaces(
            module_name=str(module_name),
            facts=facts,
            peer_index=peer_index,
            module_semantic=module_semantic,
        )

        module_context = build_module_context(
            top_module=top_module,
            module_name=str(module_name),
            facts=facts,
            parser_module=parser_module,
            ai_module=ai_module,
            module_semantic=module_semantic,
            flow_infos=flow_infos,
            interfaces=interfaces,
            topology=topology,
        )

        module_dir = out_root / "modules" / safe_filename(str(module_name))
        module_rel = f"modules/{safe_filename(str(module_name))}/module_context.json"
        interfaces_rel = f"modules/{safe_filename(str(module_name))}/interfaces.json"
        gaps_rel = f"modules/{safe_filename(str(module_name))}/gaps.json"

        write_json(out_root / module_rel, module_context)
        write_json(
            out_root / interfaces_rel,
            {
                "schema": "manual_context_module_interfaces",
                "schema_version": SCHEMA_VERSION,
                "top_module": top_module,
                "module": str(module_name),
                "interfaces": interfaces,
            },
        )
        write_json(out_root / gaps_rel, build_module_gaps(top_module, str(module_name), facts, module_semantic, flow_infos))

        module_context_files[str(module_name)] = module_rel
        interface_context_files[str(module_name)] = interfaces_rel
        gap_files[str(module_name)] = gaps_rel

        flow_rels: List[str] = []
        for info in flow_infos:
            flow_rel = f"modules/{safe_filename(str(module_name))}/flows/{safe_filename(info['flow_id'])}.json"
            write_json(out_root / flow_rel, info["context"])
            flow_rels.append(flow_rel)
            flow_index_items.append(build_flow_index_item(str(module_name), flow_rel, info["context"]))
        flow_context_files[str(module_name)] = flow_rels

        for item in interfaces:
            interface_index_items.append(build_interface_index_item(str(module_name), interfaces_rel, item))

    project_context = build_project_context(
        top_module=top_module,
        project_facts=project_facts,
        parser_index=parser_index,
        topology=topology,
        module_facts=module_facts_by_name,
        parser_modules=parser_modules,
        flow_index_items=flow_index_items,
        semantic_modules=semantic_modules,
    )
    system_topology = build_system_topology(top_module, topology)
    interface_index = build_interface_index(top_module, interface_index_items)
    flow_index = build_flow_index(top_module, flow_index_items)
    evidence_index = build_evidence_index(top_module, evidence_entries)
    human_overrides = build_human_overrides(top_module)

    write_json(out_root / "project_context.json", project_context)
    write_json(out_root / "system_topology.json", system_topology)
    write_json(out_root / "interface_index.json", interface_index)
    write_json(out_root / "flow_index.json", flow_index)
    write_json(out_root / "evidence_index.json", evidence_index)
    write_json(out_root / "human_overrides.json", human_overrides)

    manual_manifest = {
        "schema": "manual_context_manifest",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "generated_from": {
            "knowledge_dir": str(knowledge_root),
            "parser_artifacts_root": str(parser_root),
            "knowledge_manifest": "manifest.json",
            "knowledge_schema_version": manifest.get("schema_version", ""),
            "ai_context_index": "ai_context/index.json" if ai_index else "",
            "semantic_index": "semantic/index.json" if semantic_index else "",
        },
        "doc_focus": DEFAULT_DOC_FOCUS,
        "counts": {
            "modules": len(module_context_files),
            "interfaces": len(interface_index_items),
            "flows": len(flow_index_items),
            "evidence_entries": len(evidence_entries),
        },
        "files": {
            "project_context": "project_context.json",
            "system_topology": "system_topology.json",
            "interface_index": "interface_index.json",
            "flow_index": "flow_index.json",
            "evidence_index": "evidence_index.json",
            "human_overrides": "human_overrides.json",
            "validation_report": "validation_report.json",
            "modules": module_context_files,
            "interfaces": interface_context_files,
            "flows": flow_context_files,
            "gaps": gap_files,
        },
        "manual_generator_contract": {
            "context_shape": "page_oriented_claims_with_evidence_refs",
            "certainty_values": [
                DETERMINISTIC,
                DERIVED,
                AI_INFERRED,
                HUMAN_ASSERTED,
                EVIDENCE_GAP,
            ],
            "preferred_entrypoints": [
                "project_context.json",
                "modules/<module>/module_context.json",
                "modules/<module>/interfaces.json",
                "modules/<module>/flows/<flow_id>.json",
            ],
        },
    }
    validation_report = build_validation_report(out_root, manual_manifest, evidence_index)
    manual_manifest["counts"]["validation_issues"] = len(validation_report.get("issues", []))
    write_json(out_root / "manifest.json", manual_manifest)
    write_json(out_root / "validation_report.json", validation_report)
    return manual_manifest


def build_topology(module_files: Dict[str, Any], parser_modules: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    module_names = {str(name) for name in module_files}
    parents: Dict[str, set[str]] = defaultdict(set)
    children: Dict[str, List[str]] = {}
    components: Dict[str, List[str]] = {}
    hierarchy_edges: List[Dict[str, Any]] = []

    for parent_name, payload in parser_modules.items():
        direct_modules = [
            str(item)
            for item in payload.get("direct_children", {}).get("modules", [])
            if str(item) in module_names
        ]
        direct_components = [
            str(item)
            for item in payload.get("direct_children", {}).get("components", [])
        ]
        children[parent_name] = sorted(set(direct_modules))
        components[parent_name] = sorted(set(direct_components))
        for child in direct_modules:
            parents[child].add(parent_name)
            hierarchy_edges.append(
                {
                    "parent": parent_name,
                    "child": child,
                    "relationship": "instantiates",
                    "certainty": DETERMINISTIC,
                    "source_layers": ["parse"],
                    "evidence_refs": [f"ev:{parent_name}:parser_module"],
                }
            )

    signal_edges = build_signal_edges(parser_modules, module_names)
    upstream: Dict[str, set[str]] = defaultdict(set)
    downstream: Dict[str, set[str]] = defaultdict(set)
    for edge in signal_edges:
        src = edge.get("from_module", "")
        dst = edge.get("to_module", "")
        if src in module_names and dst in module_names and src != dst:
            downstream[src].add(dst)
            upstream[dst].add(src)

    return {
        "module_names": sorted(module_names),
        "parents": {name: sorted(values) for name, values in parents.items()},
        "children": children,
        "components": components,
        "hierarchy_edges": hierarchy_edges,
        "signal_edges": signal_edges,
        "upstream": {name: sorted(values) for name, values in upstream.items()},
        "downstream": {name: sorted(values) for name, values in downstream.items()},
    }


def build_signal_edges(
    parser_modules: Dict[str, Dict[str, Any]],
    module_names: set[str],
) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for parent_name, payload in parser_modules.items():
        instance_types = {
            str(instance.get("instance_name", "")): str(instance.get("module_type", ""))
            for instance in payload.get("instances", [])
            if instance.get("artifact_kind") == "module"
        }
        for connection in payload.get("connection_graph", {}).get("connections", []):
            if not isinstance(connection, dict):
                continue
            role = str(connection.get("role", "unknown"))
            if role not in {"event_drive", "payload_data", "condition", "event_free"}:
                continue
            from_endpoint = connection.get("from", {})
            to_endpoint = connection.get("to", {})
            if not isinstance(from_endpoint, dict) or not isinstance(to_endpoint, dict):
                continue
            src_node = str(from_endpoint.get("node", ""))
            dst_node = str(to_endpoint.get("node", ""))
            src_module = str(from_endpoint.get("module_type", "") or instance_types.get(src_node, ""))
            dst_module = str(to_endpoint.get("module_type", "") or instance_types.get(dst_node, ""))
            if src_module not in module_names and dst_module not in module_names:
                continue
            signal = str(connection.get("signal", ""))
            key = (parent_name, src_node, dst_node, signal, role)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "parent_module": parent_name,
                    "from_instance": src_node,
                    "from_module": src_module if src_module in module_names else "",
                    "from_artifact": src_module,
                    "from_port": str(from_endpoint.get("port", "")),
                    "to_instance": dst_node,
                    "to_module": dst_module if dst_module in module_names else "",
                    "to_artifact": dst_module,
                    "to_port": str(to_endpoint.get("port", "")),
                    "signal": signal,
                    "signal_role": role,
                    "certainty": DETERMINISTIC,
                    "source_layers": ["parse"],
                    "evidence_refs": [f"ev:{parent_name}:parser_module"],
                }
            )
        for signal_info in payload.get("connection_graph", {}).get("signals", []):
            role = str(signal_info.get("role", "unknown"))
            if role not in {"event_drive", "payload_data", "condition", "event_free"}:
                continue
            signal = str(signal_info.get("signal", signal_info.get("name", "")))
            drivers = signal_info.get("drivers", [])
            loads = signal_info.get("loads", [])
            if not isinstance(drivers, list) or not isinstance(loads, list):
                continue
            for driver in drivers:
                src_node = str(driver.get("node", ""))
                src_module = instance_types.get(src_node)
                if src_module not in module_names:
                    continue
                for load in loads:
                    dst_node = str(load.get("node", ""))
                    dst_module = instance_types.get(dst_node)
                    if dst_module not in module_names:
                        continue
                    key = (parent_name, src_node, dst_node, signal, role)
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append(
                        {
                            "parent_module": parent_name,
                            "from_instance": src_node,
                            "from_module": src_module,
                            "from_port": str(driver.get("port", "")),
                            "to_instance": dst_node,
                            "to_module": dst_module,
                            "to_port": str(load.get("port", "")),
                            "signal": signal,
                            "signal_role": role,
                            "certainty": DETERMINISTIC,
                            "source_layers": ["parse"],
                            "evidence_refs": [f"ev:{parent_name}:parser_module"],
                        }
                    )
    return sorted(
        edges,
        key=lambda item: (
            item["parent_module"],
            item["from_module"],
            item["to_module"],
            item["signal_role"],
            item["signal"],
        ),
    )


def build_peer_index(parser_modules: Dict[str, Dict[str, Any]]) -> Dict[tuple[str, str], List[Dict[str, Any]]]:
    peer_index: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for parent_name, payload in parser_modules.items():
        instance_types = {
            str(instance.get("instance_name", "")): str(instance.get("module_type", ""))
            for instance in payload.get("instances", [])
            if instance.get("artifact_kind") == "module"
        }
        for connection in payload.get("connection_graph", {}).get("connections", []):
            if not isinstance(connection, dict):
                continue
            signal = str(connection.get("signal", ""))
            role = str(connection.get("role", "unknown"))
            endpoints = [
                ("driver", connection.get("from", {})),
                ("load", connection.get("to", {})),
            ]
            formatted = []
            for endpoint_role, endpoint in endpoints:
                if not isinstance(endpoint, dict):
                    continue
                node = str(endpoint.get("node", ""))
                module_type = str(endpoint.get("module_type", "") or instance_types.get(node, ""))
                if not module_type:
                    continue
                formatted.append(
                    {
                        "endpoint_role": endpoint_role,
                        "instance": node,
                        "module": module_type,
                        "port": str(endpoint.get("port", "")),
                        "peer_kind": "module" if module_type in instance_types.values() else "component_or_helper",
                    }
                )
            for endpoint in formatted:
                peers = [
                    {
                        "module": peer["module"],
                        "instance": peer["instance"],
                        "port": peer["port"],
                        "endpoint_role": peer["endpoint_role"],
                        "peer_kind": peer["peer_kind"],
                    }
                    for peer in formatted
                    if peer is not endpoint
                ]
                if not peers:
                    continue
                peer_index[(endpoint["module"], endpoint["port"])].append(
                    {
                        "parent_module": parent_name,
                        "local_instance": endpoint["instance"],
                        "parent_signal": signal,
                        "signal_role": role,
                        "local_endpoint_role": endpoint["endpoint_role"],
                        "peers": peers,
                        "certainty": DETERMINISTIC,
                        "source_layers": ["parse"],
                        "evidence_refs": [f"ev:{parent_name}:parser_module"],
                    }
                )
        for signal_info in payload.get("connection_graph", {}).get("signals", []):
            signal = str(signal_info.get("signal", signal_info.get("name", "")))
            role = str(signal_info.get("role", "unknown"))
            endpoints = []
            for endpoint in signal_info.get("drivers", []):
                endpoints.append(("driver", endpoint))
            for endpoint in signal_info.get("loads", []):
                endpoints.append(("load", endpoint))
            module_endpoints = [
                {
                    "endpoint_role": endpoint_role,
                    "instance": str(endpoint.get("node", "")),
                    "module": instance_types.get(str(endpoint.get("node", "")), ""),
                    "port": str(endpoint.get("port", "")),
                }
                for endpoint_role, endpoint in endpoints
                if instance_types.get(str(endpoint.get("node", "")), "")
            ]
            for endpoint in module_endpoints:
                peers = [
                    {
                        "module": peer["module"],
                        "instance": peer["instance"],
                        "port": peer["port"],
                        "endpoint_role": peer["endpoint_role"],
                    }
                    for peer in module_endpoints
                    if peer is not endpoint and peer["module"] != endpoint["module"]
                ]
                if not peers:
                    continue
                peer_index[(endpoint["module"], endpoint["port"])].append(
                    {
                        "parent_module": parent_name,
                        "local_instance": endpoint["instance"],
                        "parent_signal": signal,
                        "signal_role": role,
                        "local_endpoint_role": endpoint["endpoint_role"],
                        "peers": peers,
                        "certainty": DETERMINISTIC,
                        "source_layers": ["parse"],
                        "evidence_refs": [f"ev:{parent_name}:parser_module"],
                    }
                )
    return dict(peer_index)


def build_module_context(
    *,
    top_module: str,
    module_name: str,
    facts: Dict[str, Any],
    parser_module: Dict[str, Any],
    ai_module: Dict[str, Any],
    module_semantic: Dict[str, Any],
    flow_infos: List[Dict[str, Any]],
    interfaces: List[Dict[str, Any]],
    topology: Dict[str, Any],
) -> Dict[str, Any]:
    module_claims = select_claims(module_semantic, MODULE_ROLE_CLAIMS, limit=8)
    responsibility = build_responsibility(module_name, module_claims)
    internal_components = build_internal_components(facts, module_semantic)
    assignments = build_assignment_impact_summary(facts, module_semantic)
    important_signals = build_important_signals(facts, parser_module, module_semantic)
    key_flows = [build_key_flow_ref(info) for info in flow_infos]

    return {
        "schema": "manual_context_module",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "module_identity": {
            "module_name": module_name,
            "module_role": facts.get("module_role", parser_module.get("module_role", "")),
            "source_files": [facts.get("source", {}).get("rtl_file") or parser_module.get("file", "")],
            "source": facts.get("source", {}),
            "certainty": DETERMINISTIC,
            "source_layers": ["parse", "knowledge_ir"],
            "evidence_refs": [f"ev:{module_name}:knowledge_module", f"ev:{module_name}:parser_module"],
        },
        "system_position": {
            "parents": claim(sorted(topology.get("parents", {}).get(module_name, [])), DETERMINISTIC, ["parse"], [f"ev:{module_name}:parser_module"]),
            "children": claim(sorted(topology.get("children", {}).get(module_name, [])), DETERMINISTIC, ["parse"], [f"ev:{module_name}:parser_module"]),
            "component_children": claim(sorted(topology.get("components", {}).get(module_name, [])), DETERMINISTIC, ["parse"], [f"ev:{module_name}:parser_module"]),
            "upstream_modules": claim(sorted(topology.get("upstream", {}).get(module_name, [])), DETERMINISTIC, ["parse"], [f"ev:{module_name}:parser_module"]),
            "downstream_modules": claim(sorted(topology.get("downstream", {}).get(module_name, [])), DETERMINISTIC, ["parse"], [f"ev:{module_name}:parser_module"]),
            "region": classify_region(module_name, facts, parser_module),
        },
        "module_responsibility": responsibility,
        "interface_summary": build_interface_summary(facts, interfaces),
        "input_event_data_summary": build_event_data_summary(facts, "input"),
        "output_event_data_summary": build_event_data_summary(facts, "output"),
        "key_drive_flows": key_flows,
        "internal_components": internal_components,
        "assignment_impact_summary": assignments,
        "important_internal_signals": important_signals,
        "reset_control_state": build_reset_control_state(facts, parser_module, module_semantic),
        "manual_sections": build_module_manual_sections(module_name, flow_infos, interfaces, internal_components, assignments),
        "evidence_gaps": build_gap_claims(facts.get("evidence_gaps", []), module_name),
        "review_questions": build_review_questions(module_semantic, flow_infos, facts),
        "source_context_refs": {
            "knowledge_ir": f"modules/{safe_filename(module_name)}.json",
            "ai_context": ai_module.get("source_context", f"ai_context/modules/{safe_filename(module_name)}.json") if ai_module else "",
            "semantic_layer": module_semantic.get("id", ""),
        },
    }


def build_module_interfaces(
    *,
    module_name: str,
    facts: Dict[str, Any],
    peer_index: Dict[tuple[str, str], List[Dict[str, Any]]],
    module_semantic: Dict[str, Any],
) -> List[Dict[str, Any]]:
    interface = facts.get("interface", {})
    contracts = facts.get("interface_data_contract", [])
    semantic_claims = select_claims(module_semantic, INTERFACE_CLAIMS, limit=12)
    claims_by_signal = index_claims_by_signal(semantic_claims)
    result: List[Dict[str, Any]] = []
    contract_events = {str(contract.get("event", "")): contract for contract in contracts}
    event_ports = list(interface.get("event_inputs", [])) + list(interface.get("event_outputs", []))
    for event_port in event_ports:
        event_name = str(event_port.get("name", ""))
        contract = contract_events.get(event_name, {})
        direction = str(event_port.get("direction", contract.get("direction", "")))
        signal_claims = claims_by_signal.get(event_name, [])[:3]
        result.append(
            {
                "interface_id": f"if:{module_name}:{event_name}",
                "interface_name": event_name,
                "direction": direction,
                "doc_priority": "primary" if "drive" in event_name.lower() or "drv" in event_name.lower() else "secondary",
                "event_signals": [
                    signal_fact(event_port, DETERMINISTIC, ["knowledge_ir"], [f"ev:{module_name}:interface"])
                ],
                "payload_signals": [
                    signal_fact(payload, DETERMINISTIC, ["knowledge_ir"], [f"ev:{module_name}:interface_data_contract"])
                    for payload in contract.get("payloads", [])
                    if isinstance(payload, dict)
                ],
                "control_signals": [],
                "free_backpressure_signals": build_free_signal(contract, facts, module_name),
                "event_payload_binding": {
                    "event": event_name,
                    "payloads": [payload.get("name", "") for payload in contract.get("payloads", []) if isinstance(payload, dict)],
                    "free_signal": contract.get("free_signal", ""),
                    "certainty": DETERMINISTIC if contract else EVIDENCE_GAP,
                    "source_layers": ["knowledge_ir"],
                    "evidence_refs": [f"ev:{module_name}:interface_data_contract"],
                },
                "peer_modules": peer_index.get((module_name, event_name), []),
                "data_contract": contract,
                "manual_description": semantic_claims_to_manual_description(signal_claims, [f"ev:{module_name}:semantic_module"]),
                "evidence_refs": [f"ev:{module_name}:interface", f"ev:{module_name}:interface_data_contract"],
                "uncertainties": interface_uncertainties(module_name, event_name, contract, facts),
            }
        )

    result.extend(build_non_event_interface_groups(module_name, facts, peer_index, claims_by_signal))
    return result


def build_non_event_interface_groups(
    module_name: str,
    facts: Dict[str, Any],
    peer_index: Dict[tuple[str, str], List[Dict[str, Any]]],
    claims_by_signal: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    interface = facts.get("interface", {})
    groups = [
        ("data_inputs", "input", "payload_data", "secondary"),
        ("data_outputs", "output", "payload_data", "secondary"),
        ("control_inputs", "input", "control", "secondary"),
        ("control_outputs", "output", "control", "secondary"),
        ("free_inputs", "input", "free_backpressure", "reference"),
        ("free_outputs", "output", "free_backpressure", "reference"),
    ]
    result: List[Dict[str, Any]] = []
    for group_name, direction, role, priority in groups:
        ports = interface.get(group_name, [])
        if not ports:
            continue
        signals = [
            signal_fact(port, DETERMINISTIC, ["knowledge_ir"], [f"ev:{module_name}:interface"])
            for port in ports
            if isinstance(port, dict)
        ]
        result.append(
            {
                "interface_id": f"if:{module_name}:{group_name}",
                "interface_name": group_name,
                "direction": direction,
                "doc_priority": priority,
                "role": role,
                "event_signals": [],
                "payload_signals": signals if role == "payload_data" else [],
                "control_signals": signals if role == "control" else [],
                "free_backpressure_signals": signals if role == "free_backpressure" else [],
                "event_payload_binding": {
                    "certainty": EVIDENCE_GAP,
                    "reason": "non-event signal group is not directly bound to one drive event here",
                },
                "peer_modules": collect_group_peers(module_name, ports, peer_index),
                "manual_description": semantic_claims_to_manual_description(
                    [
                        claim_item
                        for port in ports
                        for claim_item in claims_by_signal.get(str(port.get("name", "")), [])
                    ][:3],
                    [f"ev:{module_name}:semantic_module"],
                ),
                "evidence_refs": [f"ev:{module_name}:interface"],
                "uncertainties": [],
            }
        )
    return result


def build_flow_infos(
    *,
    knowledge_root: Path,
    ai_index: Dict[str, Any],
    module_name: str,
    facts: Dict[str, Any],
    semantic_flow_cards: Dict[str, Dict[str, Any]],
    evidence_entries: Dict[str, Dict[str, Any]],
    top_module: str,
) -> List[Dict[str, Any]]:
    flows = facts.get("internal_event_flow", [])
    flow_paths = ai_index.get("files", {}).get("flows", {}).get(module_name, []) if ai_index else []
    ai_flows_by_start = load_ai_flows_by_start(knowledge_root, flow_paths)
    infos: List[Dict[str, Any]] = []
    for index, flow in enumerate(flows):
        if not isinstance(flow, dict):
            continue
        flow_start = str(flow.get("start", ""))
        ai_flow = ai_flows_by_start.get(flow_start, {})
        flow_id = str(ai_flow.get("flow_id") or fallback_flow_id(module_name, flow, index))
        semantic_card = semantic_flow_cards.get(flow_id, {})
        evidence_id = f"ev:{module_name}:flow:{flow_id}"
        evidence_entries[evidence_id] = {
            "evidence_id": evidence_id,
            "certainty": DETERMINISTIC,
            "source_layer": "knowledge_ir",
            "artifact": f"rtl/knowledge_ir/{top_module}/modules/{safe_filename(module_name)}.json",
            "json_path": f"$.internal_event_flow[{index}]",
            "related_artifacts": [ai_flow.get("source_context", "")] if ai_flow else [],
        }
        semantic_rel = semantic_flow_rel_for(flow_paths, index, module_name, flow_id)
        if semantic_card:
            semantic_evidence_id = f"ev:{module_name}:semantic_flow:{flow_id}"
            evidence_entries[semantic_evidence_id] = {
                "evidence_id": semantic_evidence_id,
                "certainty": AI_INFERRED,
                "source_layer": "semantic_layer",
                "artifact": f"rtl/knowledge_ir/{top_module}/{semantic_rel}",
                "json_path": "$.claims",
            }
        context = build_flow_context(
            top_module=top_module,
            module_name=module_name,
            flow_id=flow_id,
            flow_index=index,
            flow=flow,
            facts=facts,
            ai_flow=ai_flow,
            semantic_card=semantic_card,
        )
        infos.append(
            {
                "flow_id": flow_id,
                "flow_index": index,
                "context": context,
            }
        )
    return infos


def build_flow_context(
    *,
    top_module: str,
    module_name: str,
    flow_id: str,
    flow_index: int,
    flow: Dict[str, Any],
    facts: Dict[str, Any],
    ai_flow: Dict[str, Any],
    semantic_card: Dict[str, Any],
) -> Dict[str, Any]:
    semantic_meaning_claims = select_claims(semantic_card, FLOW_MEANING_CLAIMS, limit=6)
    component_role_claims = select_claims(semantic_card, COMPONENT_ROLE_CLAIMS, limit=20)
    payloads = payloads_for_flow(facts, flow)
    related_assignments = related_assignments_for_flow(facts, ai_flow)
    manual_importance = flow_manual_importance(flow, semantic_meaning_claims)
    evidence_refs = [f"ev:{module_name}:flow:{flow_id}"]
    if semantic_card:
        evidence_refs.append(f"ev:{module_name}:semantic_flow:{flow_id}")

    return {
        "schema": "manual_context_flow",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "flow_id": flow_id,
        "flow_index": flow_index,
        "module": module_name,
        "title": build_flow_title(module_name, flow),
        "trigger_event": {
            "signal": flow.get("start", ""),
            "certainty": DETERMINISTIC,
            "source_layers": ["knowledge_ir"],
            "evidence_refs": [f"ev:{module_name}:flow:{flow_id}"],
        },
        "payloads": payloads,
        "ordered_path": build_ordered_path(flow),
        "component_steps": build_component_steps(flow, component_role_claims, module_name, flow_id),
        "branch_merge_behavior": build_branch_merge_behavior(flow),
        "related_assignments": related_assignments,
        "outputs_or_effects": build_outputs_or_effects(flow, facts, module_name, flow_id),
        "semantic_meaning": semantic_claims_to_manual_description(semantic_meaning_claims, evidence_refs),
        "manual_importance": manual_importance,
        "writer_hints": build_flow_writer_hints(flow, semantic_meaning_claims, manual_importance),
        "evidence_refs": evidence_refs,
        "gaps": flow_gaps(module_name, flow_id, flow, semantic_meaning_claims),
    }


def build_project_context(
    *,
    top_module: str,
    project_facts: Dict[str, Any],
    parser_index: Dict[str, Any],
    topology: Dict[str, Any],
    module_facts: Dict[str, Dict[str, Any]],
    parser_modules: Dict[str, Dict[str, Any]],
    flow_index_items: List[Dict[str, Any]],
    semantic_modules: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    top_semantic = semantic_modules.get(top_module, {})
    top_role_claims = select_claims(top_semantic, MODULE_ROLE_CLAIMS, limit=4)
    reachable = project_facts.get("reachable_modules", topology.get("module_names", []))
    direct_modules = project_facts.get("top_level", {}).get("direct_modules", [])
    region_map = build_region_map(reachable, module_facts, parser_modules, topology)
    major_modules = build_major_modules(reachable, semantic_modules, region_map, topology)
    major_flows = sorted(
        flow_index_items,
        key=lambda item: (
            item.get("manual_importance") != "high",
            item.get("module", ""),
            item.get("trigger_event", ""),
        ),
    )[:40]
    return {
        "schema": "manual_context_project",
        "schema_version": SCHEMA_VERSION,
        "top_module": claim(top_module, DETERMINISTIC, ["knowledge_ir", "parse"], ["ev:project:top_module"]),
        "system_summary": semantic_claims_to_manual_description(top_role_claims, [f"ev:{top_module}:semantic_module"]),
        "top_level": {
            "source_file": project_facts.get("top_level", {}).get("file", ""),
            "direct_modules": claim(direct_modules, DETERMINISTIC, ["knowledge_ir", "parse"], ["ev:project:top_level"]),
            "direct_components": claim(project_facts.get("top_level", {}).get("direct_components", []), DETERMINISTIC, ["knowledge_ir"], ["ev:project:top_level"]),
        },
        "major_modules": major_modules,
        "module_hierarchy": {
            "edge_count": len(topology.get("hierarchy_edges", [])),
            "edges": topology.get("hierarchy_edges", [])[:240],
            "truncated": len(topology.get("hierarchy_edges", [])) > 240,
        },
        "region_map": region_map,
        "major_system_flows": major_flows,
        "component_families_overview": project_facts.get("component_families", []),
        "cross_module_interfaces": topology.get("signal_edges", [])[:240],
        "manual_toc_plan": build_manual_toc_plan(top_module, reachable),
        "system_level_gaps": build_system_level_gaps(project_facts, parser_index, top_semantic),
        "doc_focus": DEFAULT_DOC_FOCUS,
    }


def build_system_topology(top_module: str, topology: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "manual_context_system_topology",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "module_count": len(topology.get("module_names", [])),
        "hierarchy_edges": topology.get("hierarchy_edges", []),
        "signal_edges": topology.get("signal_edges", []),
        "module_neighbors": {
            module: {
                "parents": topology.get("parents", {}).get(module, []),
                "children": topology.get("children", {}).get(module, []),
                "upstream_modules": topology.get("upstream", {}).get(module, []),
                "downstream_modules": topology.get("downstream", {}).get(module, []),
            }
            for module in topology.get("module_names", [])
        },
    }


def build_interface_index(top_module: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_module = Counter(item["module"] for item in items)
    by_priority = Counter(item.get("doc_priority", "secondary") for item in items)
    return {
        "schema": "manual_context_interface_index",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "counts": {
            "interfaces": len(items),
            "modules": len(by_module),
            "by_priority": dict(sorted(by_priority.items())),
        },
        "interfaces": sorted(items, key=lambda item: (item["module"], item["interface_name"])),
    }


def build_flow_index(top_module: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_module = Counter(item["module"] for item in items)
    by_importance = Counter(item.get("manual_importance", "medium") for item in items)
    return {
        "schema": "manual_context_flow_index",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "counts": {
            "flows": len(items),
            "modules": len(by_module),
            "by_importance": dict(sorted(by_importance.items())),
        },
        "flows": sorted(items, key=lambda item: (item.get("manual_importance") != "high", item["module"], item["flow_id"])),
    }


def build_evidence_index(top_module: str, entries: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema": "manual_context_evidence_index",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "evidence_policy": {
            "deterministic_fact": "Facts copied or derived from parser artifacts and Knowledge IR.",
            "ai_inferred": "Interpretations copied from Semantic Layer claims.",
            "evidence_gap": "Known missing or incomplete evidence carried forward for manual review.",
        },
        "evidence": [entries[key] for key in sorted(entries)],
    }


def build_human_overrides(top_module: str) -> Dict[str, Any]:
    return {
        "schema": "manual_context_human_overrides",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "description": "Optional manual assertions that can be merged into Manual Context Layer outputs.",
        "allowed_certainty": HUMAN_ASSERTED,
        "module_overrides": {},
        "flow_overrides": {},
        "interface_overrides": {},
        "review_notes": [],
    }


def build_validation_report(
    out_root: Path,
    manifest: Dict[str, Any],
    evidence_index: Dict[str, Any],
) -> Dict[str, Any]:
    evidence_ids = {
        str(item.get("evidence_id", ""))
        for item in evidence_index.get("evidence", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    issues: List[Dict[str, Any]] = []
    checked_files: List[str] = []

    for rel_path in collect_manifest_output_files(manifest):
        if rel_path == "validation_report.json":
            continue
        file_path = out_root / rel_path
        if not file_path.is_file():
            issues.append(
                {
                    "level": "error",
                    "code": "missing_output_file",
                    "file": rel_path,
                    "message": f"Manual Context output file is missing: {rel_path}",
                }
            )
            continue
        checked_files.append(rel_path)
        try:
            payload = read_json(file_path)
        except Exception as exc:
            issues.append(
                {
                    "level": "error",
                    "code": "invalid_json",
                    "file": rel_path,
                    "message": str(exc),
                }
            )
            continue
        validate_payload_contract(payload, rel_path, evidence_ids, issues)

    return {
        "schema": "manual_context_validation_report",
        "schema_version": SCHEMA_VERSION,
        "top_module": manifest.get("top_module", ""),
        "status": "failed" if any(item.get("level") == "error" for item in issues) else "passed",
        "checked_files": checked_files,
        "counts": {
            "checked_files": len(checked_files),
            "issues": len(issues),
            "errors": sum(1 for item in issues if item.get("level") == "error"),
            "warnings": sum(1 for item in issues if item.get("level") == "warning"),
        },
        "issues": issues,
    }


def collect_manifest_output_files(manifest: Dict[str, Any]) -> List[str]:
    files = manifest.get("files", {})
    rels: List[str] = []
    for key in (
        "project_context",
        "system_topology",
        "interface_index",
        "flow_index",
        "evidence_index",
        "human_overrides",
        "validation_report",
    ):
        rel = files.get(key, "")
        if isinstance(rel, str) and rel:
            rels.append(rel)
    for key in ("modules", "interfaces", "gaps"):
        values = files.get(key, {})
        if isinstance(values, dict):
            rels.extend(str(rel) for rel in values.values() if isinstance(rel, str) and rel)
    flow_values = files.get("flows", {})
    if isinstance(flow_values, dict):
        for module_flows in flow_values.values():
            if isinstance(module_flows, list):
                rels.extend(str(rel) for rel in module_flows if isinstance(rel, str) and rel)
    return sorted(set(rels))


def validate_payload_contract(
    value: Any,
    rel_path: str,
    evidence_ids: set[str],
    issues: List[Dict[str, Any]],
    *,
    json_path: str = "$",
) -> None:
    if isinstance(value, dict):
        certainty = value.get("certainty")
        if certainty is not None and certainty not in {DETERMINISTIC, DERIVED, AI_INFERRED, HUMAN_ASSERTED, EVIDENCE_GAP}:
            issues.append(
                {
                    "level": "error",
                    "code": "invalid_certainty",
                    "file": rel_path,
                    "json_path": f"{json_path}.certainty",
                    "message": f"Unknown certainty value: {certainty}",
                }
            )
        doc_priority = value.get("doc_priority")
        if doc_priority is not None and doc_priority not in DOC_PRIORITIES:
            issues.append(
                {
                    "level": "error",
                    "code": "invalid_doc_priority",
                    "file": rel_path,
                    "json_path": f"{json_path}.doc_priority",
                    "message": f"Unknown doc_priority value: {doc_priority}",
                }
            )
        manual_importance = value.get("manual_importance")
        if manual_importance is not None and manual_importance not in MANUAL_IMPORTANCE_LEVELS:
            issues.append(
                {
                    "level": "error",
                    "code": "invalid_manual_importance",
                    "file": rel_path,
                    "json_path": f"{json_path}.manual_importance",
                    "message": f"Unknown manual_importance value: {manual_importance}",
                }
            )
        evidence_refs = value.get("evidence_refs")
        if isinstance(evidence_refs, list):
            for index, evidence_ref in enumerate(evidence_refs):
                if not isinstance(evidence_ref, str) or not evidence_ref:
                    continue
                if evidence_ref not in evidence_ids:
                    issues.append(
                        {
                            "level": "error",
                            "code": "unknown_evidence_ref",
                            "file": rel_path,
                            "json_path": f"{json_path}.evidence_refs[{index}]",
                            "message": f"evidence_ref is not present in evidence_index: {evidence_ref}",
                        }
                    )
        for key, child in value.items():
            validate_payload_contract(child, rel_path, evidence_ids, issues, json_path=f"{json_path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_payload_contract(child, rel_path, evidence_ids, issues, json_path=f"{json_path}[{index}]")


def build_responsibility(module_name: str, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    role_claim = first_claim(claims, "module_role") or (claims[0] if claims else {})
    if not role_claim:
        return {
            "short_summary": {
                "value": "",
                "certainty": EVIDENCE_GAP,
                "confidence": "low",
                "source_layers": [],
                "evidence_refs": [],
                "reason": "No Semantic Layer module role claim is available.",
            },
            "responsibility_claims": [],
            "review_status": "needs_review",
        }
    review_needed = bool(role_claim.get("requires_rtl_source_review")) or str(role_claim.get("confidence", "")).lower() == "low"
    return {
        "short_summary": semantic_claim_to_claim(role_claim, [f"ev:{module_name}:semantic_module"]),
        "responsibility_claims": [
            semantic_claim_to_claim(item, [f"ev:{module_name}:semantic_module"])
            for item in claims
            if item.get("claim_type") in {"module_role", "structural_responsibility"}
        ],
        "documentation_focus": [
            semantic_claim_to_claim(item, [f"ev:{module_name}:semantic_module"])
            for item in claims
            if item.get("claim_type") == "documentation_focus"
        ],
        "review_status": "needs_review" if review_needed else "ready",
    }


def build_interface_summary(facts: Dict[str, Any], interfaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    interface = facts.get("interface", {})
    summary = interface.get("summary", {})
    primary_interfaces = [
        {
            "interface_id": item.get("interface_id", ""),
            "interface_name": item.get("interface_name", ""),
            "direction": item.get("direction", ""),
            "doc_priority": item.get("doc_priority", ""),
        }
        for item in interfaces
        if item.get("doc_priority") == "primary"
    ]
    return {
        "counts": claim(summary, DETERMINISTIC, ["knowledge_ir"], [f"ev:{facts.get('module', '')}:interface"]),
        "primary_interfaces": primary_interfaces,
        "high_priority_interfaces": primary_interfaces,
        "event_inputs": interface.get("event_inputs", []),
        "event_outputs": interface.get("event_outputs", []),
        "free_backpressure_note": {
            "value": "free signals are retained as low-priority backpressure context unless they gate drive availability",
            "certainty": DERIVED,
            "source_layers": ["manual_context"],
            "evidence_refs": [f"ev:{facts.get('module', '')}:interface"],
        },
    }


def build_event_data_summary(facts: Dict[str, Any], direction: str) -> Dict[str, Any]:
    contracts = [
        contract
        for contract in facts.get("interface_data_contract", [])
        if contract.get("direction") == direction
    ]
    return {
        "direction": direction,
        "event_count": len(contracts),
        "bindings": [
            {
                "event": contract.get("event", ""),
                "payloads": contract.get("payloads", []),
                "free_signal": contract.get("free_signal", ""),
                "confidence": contract.get("confidence", ""),
                "certainty": DETERMINISTIC,
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{facts.get('module', '')}:interface_data_contract"],
            }
            for contract in contracts
        ],
    }


def build_internal_components(facts: Dict[str, Any], module_semantic: Dict[str, Any]) -> List[Dict[str, Any]]:
    component_claims = select_claims(module_semantic, COMPONENT_ROLE_CLAIMS, limit=80)
    claims_by_subject = {
        str(item.get("subject", "")): item
        for item in component_claims
        if item.get("subject")
    }
    components = []
    for instance in facts.get("key_instances", []):
        if not isinstance(instance, dict):
            continue
        instance_name = str(instance.get("instance", ""))
        family = str(instance.get("family", ""))
        has_events = bool(instance.get("input_events") or instance.get("output_events"))
        if not family and not has_events:
            continue
        role_claim = claims_by_subject.get(instance_name, {})
        components.append(
            {
                "instance_name": instance_name,
                "module_type": instance.get("module_type", ""),
                "artifact_kind": instance.get("artifact_kind", ""),
                "component_family": family,
                "input_events": instance.get("input_events", []),
                "output_events": instance.get("output_events", []),
                "input_data": instance.get("input_data", []),
                "output_data": instance.get("output_data", []),
                "doc_priority": "primary" if has_events or family_rank(family) <= 2 else "secondary",
                "role_in_manual": semantic_claim_to_claim(role_claim, [f"ev:{facts.get('module', '')}:semantic_module"]) if role_claim else empty_inference_gap("No component role claim is available."),
                "evidence_refs": [f"ev:{facts.get('module', '')}:key_instances"],
            }
        )
    return sorted(
        components,
        key=lambda item: (
            item["doc_priority"] != "primary",
            family_rank(str(item.get("component_family", ""))),
            item.get("instance_name", ""),
        ),
    )


def build_assignment_impact_summary(facts: Dict[str, Any], module_semantic: Dict[str, Any]) -> List[Dict[str, Any]]:
    semantic_claims = select_claims(module_semantic, ASSIGNMENT_CLAIMS, limit=80)
    claim_by_assignment = index_assignment_claims(semantic_claims)
    assignments = facts.get("assignment_facts", {}).get("continuous_assignments", [])
    result = []
    for assignment in assignments[:120]:
        if not isinstance(assignment, dict):
            continue
        assignment_id = str(assignment.get("index", ""))
        related_claim = claim_by_assignment.get(assignment_id, {})
        result.append(
            {
                "assignment_id": f"assign_{assignment_id}",
                "index": assignment.get("index"),
                "lhs": assignment.get("lhs", ""),
                "rhs": assignment.get("rhs", ""),
                "lhs_terms": assignment.get("lhs_terms", []),
                "rhs_terms": assignment.get("rhs_terms", []),
                "impact_area": classify_assignment_impact(assignment, related_claim),
                "doc_priority": assignment_doc_priority(assignment, related_claim),
                "interpretation": semantic_claim_to_claim(related_claim, [f"ev:{facts.get('module', '')}:semantic_module"]) if related_claim else empty_inference_gap("No Semantic Layer assignment interpretation is available."),
                "certainty": DERIVED,
                "source_layers": ["knowledge_ir", "semantic_layer"] if related_claim else ["knowledge_ir"],
                "evidence_refs": [f"ev:{facts.get('module', '')}:assignments"],
            }
        )
    return sorted(result, key=lambda item: (item["doc_priority"] != "primary", item.get("index") or 10**9))


def build_important_signals(
    facts: Dict[str, Any],
    parser_module: Dict[str, Any],
    module_semantic: Dict[str, Any],
) -> List[Dict[str, Any]]:
    module_name = str(facts.get("module", ""))
    signal_counter = Counter()
    signal_sources: Dict[str, set[str]] = defaultdict(set)
    for claim_item in module_semantic.get("claims", []):
        for signal in claim_item.get("signals", []):
            signal_name = str(signal)
            signal_counter[signal_name] += priority_weight(claim_item.get("doc_priority", "reference"))
            signal_sources[signal_name].add("semantic")
    interface_names = collect_interface_signal_names(facts)
    for name in interface_names:
        signal_counter[name] += 2
        signal_sources[name].add("interface")
    for flow in facts.get("internal_event_flow", []):
        if flow.get("start"):
            signal_name = str(flow["start"])
            signal_counter[signal_name] += 4
            signal_sources[signal_name].add("flow")
        for endpoint in flow.get("endpoints", []):
            signal_name = str(endpoint)
            signal_counter[signal_name] += 3
            signal_sources[signal_name].add("flow")
        for step in flow.get("steps", []):
            for signal in step.get("input_drives", []) + step.get("output_drives", []):
                signal_name = str(signal)
                signal_counter[signal_name] += 2
                signal_sources[signal_name].add("flow")
    local_signal_info = {
        str(item.get("name", "")): item
        for item in parser_module.get("local_signals", [])
        if isinstance(item, dict)
    }
    result = []
    for signal, score in signal_counter.most_common(60):
        if not signal or signal.startswith(("'", '"')):
            continue
        info = local_signal_info.get(signal, {})
        sources = set(signal_sources.get(signal, set()))
        if signal in local_signal_info:
            sources.add("local_signal")
        certainty = signal_certainty_from_sources(sources)
        result.append(
            {
                "signal": signal,
                "kind": info.get("kind", "interface_or_inferred"),
                "width_text": info.get("width_text", ""),
                "importance_score": score,
                "reason": "referenced by semantic claims, interface contracts, or drive flow paths",
                "certainty": certainty,
                "source_layers": signal_source_layers(sources),
                "evidence_refs": signal_evidence_refs(module_name, sources, bool(module_semantic)),
            }
        )
    return result


def build_reset_control_state(
    facts: Dict[str, Any],
    parser_module: Dict[str, Any],
    module_semantic: Dict[str, Any],
) -> Dict[str, Any]:
    module_name = str(facts.get("module", ""))
    interface = facts.get("interface", {})
    control_claims = [
        item
        for item in module_semantic.get("claims", [])
        if item.get("claim_type") in {"data_control_effect", "structural_responsibility"}
        and any("state" in str(signal).lower() or "flag" in str(signal).lower() or "control" in str(signal).lower() for signal in item.get("signals", []))
    ][:8]
    local_signals = parser_module.get("local_signals", [])
    state_like = [
        signal
        for signal in local_signals
        if any(token in str(signal.get("name", "")).lower() for token in ("state", "flag", "mode", "wen", "valid", "sel"))
    ][:40]
    return {
        "reset_signals": interface.get("reset_inputs", []) + interface.get("reset_outputs", []),
        "reset": interface.get("reset", {}),
        "control_signals": interface.get("control_inputs", []) + interface.get("control_outputs", []),
        "state_like_internal_signals": [
            {
                "name": item.get("name", ""),
                "kind": item.get("kind", ""),
                "width_text": item.get("width_text", ""),
                "certainty": DETERMINISTIC,
                "source_layers": ["parse"],
                "evidence_refs": [f"ev:{module_name}:parser_module"],
            }
            for item in state_like
        ],
        "semantic_notes": [
            semantic_claim_to_claim(item, [f"ev:{module_name}:semantic_module"])
            for item in control_claims
        ],
        "gaps": [] if interface.get("reset") or state_like else [
            {
                "field": "reset_control_state",
                "reason": "No reset/control/state-like evidence was found in parser or semantic outputs.",
                "certainty": EVIDENCE_GAP,
            }
        ],
    }


def build_module_manual_sections(
    module_name: str,
    flow_infos: List[Dict[str, Any]],
    interfaces: List[Dict[str, Any]],
    components: List[Dict[str, Any]],
    assignments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        {
            "section_id": f"module:{module_name}:responsibility",
            "title": "Module Responsibility",
            "doc_priority": "primary",
            "source_fields": ["module_responsibility", "system_position"],
        },
        {
            "section_id": f"module:{module_name}:interfaces",
            "title": "Interface Data/Event Contract",
            "doc_priority": "primary" if interfaces else "secondary",
            "source_fields": ["interface_summary", "input_event_data_summary", "output_event_data_summary"],
            "item_count": len(interfaces),
        },
        {
            "section_id": f"module:{module_name}:drive_flows",
            "title": "Key Drive Flows",
            "doc_priority": "primary" if flow_infos else "reference",
            "source_fields": ["key_drive_flows"],
            "item_count": len(flow_infos),
        },
        {
            "section_id": f"module:{module_name}:components",
            "title": "Internal Components",
            "doc_priority": "secondary" if components else "reference",
            "source_fields": ["internal_components"],
            "item_count": len(components),
        },
        {
            "section_id": f"module:{module_name}:assignments",
            "title": "Assignment Impact",
            "doc_priority": "secondary" if assignments else "reference",
            "source_fields": ["assignment_impact_summary"],
            "item_count": len(assignments),
        },
        {
            "section_id": f"module:{module_name}:evidence",
            "title": "Evidence And Uncertainty",
            "doc_priority": "primary",
            "source_fields": ["evidence_gaps", "review_questions"],
        },
    ]


def build_module_gaps(
    top_module: str,
    module_name: str,
    facts: Dict[str, Any],
    module_semantic: Dict[str, Any],
    flow_infos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    gaps = build_gap_claims(facts.get("evidence_gaps", []), module_name)
    source_review_claims = select_claims(module_semantic, {"source_review_request"}, limit=20)
    for claim_item in source_review_claims:
        gaps.append(
            {
                "field": claim_item.get("subject", "semantic_source_review"),
                "reason": claim_item.get("reason", claim_item.get("summary", "")),
                "certainty": EVIDENCE_GAP,
                "source_layers": ["semantic_layer"],
                "semantic_claim_id": claim_item.get("id", ""),
                "evidence_refs": [f"ev:{module_name}:semantic_module"],
            }
        )
    for info in flow_infos:
        for gap in info["context"].get("gaps", []):
            gaps.append(gap)
    return {
        "schema": "manual_context_module_gaps",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "module": module_name,
        "gaps": gaps,
        "review_status": "needs_review" if gaps else "ready",
    }


def build_review_questions(
    module_semantic: Dict[str, Any],
    flow_infos: List[Dict[str, Any]],
    facts: Dict[str, Any],
) -> List[Dict[str, Any]]:
    module_name = str(facts.get("module", ""))
    questions: List[Dict[str, Any]] = []
    for claim_item in select_claims(module_semantic, {"source_review_request"}, limit=12):
        questions.append(
            {
                "question": claim_item.get("reason", claim_item.get("summary", "")),
                "subject": claim_item.get("subject", ""),
                "needed_source_slice": claim_item.get("needed_source_slice", ""),
                "source_layers": ["semantic_layer"],
                "evidence_refs": [f"ev:{module_name}:semantic_module"],
            }
        )
    for gap in facts.get("evidence_gaps", []):
        questions.append(
            {
                "question": f"Confirm parser evidence gap: {gap.get('reason', '')}",
                "subject": gap.get("field", ""),
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{module_name}:knowledge_module"],
            }
        )
    for info in flow_infos:
        meaning = info["context"].get("semantic_meaning", {})
        if meaning.get("review_status") == "needs_review":
            questions.append(
                {
                    "question": f"Review semantic meaning for flow {info['flow_id']}.",
                    "subject": info["flow_id"],
                    "source_layers": ["semantic_layer", "knowledge_ir"],
                    "evidence_refs": info["context"].get("evidence_refs", []),
                }
            )
    return questions[:40]


def build_key_flow_ref(info: Dict[str, Any]) -> Dict[str, Any]:
    context = info["context"]
    importance = context.get("manual_importance", "medium")
    return {
        "flow_id": info["flow_id"],
        "title": context.get("title", ""),
        "trigger_event": context.get("trigger_event", {}).get("signal", ""),
        "manual_importance": importance,
        "doc_priority": manual_importance_to_doc_priority(str(importance)),
        "source_file": f"flows/{safe_filename(info['flow_id'])}.json",
        "reader_takeaway": context.get("semantic_meaning", {}),
        "evidence_refs": context.get("evidence_refs", []),
    }


def build_ordered_path(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    start = flow.get("start", "")
    if start:
        items.append(
            {
                "step_index": 0,
                "kind": "input_event",
                "name": start,
                "certainty": DETERMINISTIC,
                "source_layers": ["knowledge_ir"],
            }
        )
    for step in flow.get("steps", []):
        items.append(
            {
                "step_index": len(items),
                "kind": "component",
                "name": step.get("instance", ""),
                "module_type": step.get("module_type", ""),
                "artifact_kind": step.get("artifact_kind", ""),
                "component_family": step.get("family", ""),
                "input_drives": step.get("input_drives", []),
                "output_drives": step.get("output_drives", []),
                "certainty": DETERMINISTIC,
                "source_layers": ["knowledge_ir"],
            }
        )
    for endpoint in flow.get("endpoints", []):
        items.append(
            {
                "step_index": len(items),
                "kind": "output_event",
                "name": endpoint,
                "certainty": DETERMINISTIC,
                "source_layers": ["knowledge_ir"],
            }
        )
    return items


def build_component_steps(
    flow: Dict[str, Any],
    component_role_claims: List[Dict[str, Any]],
    module_name: str,
    flow_id: str,
) -> List[Dict[str, Any]]:
    claims_by_subject = {
        str(item.get("subject", "")): item
        for item in component_role_claims
        if item.get("subject")
    }
    result = []
    for step in flow.get("steps", []):
        instance_name = str(step.get("instance", ""))
        role_claim = claims_by_subject.get(instance_name, {})
        result.append(
            {
                "instance_name": instance_name,
                "module_type": step.get("module_type", ""),
                "component_family": step.get("family", ""),
                "input_drives": step.get("input_drives", []),
                "output_drives": step.get("output_drives", []),
                "role_in_flow": semantic_claim_to_claim(role_claim, [f"ev:{module_name}:semantic_flow:{flow_id}"]) if role_claim else empty_inference_gap("No Semantic Layer component role is available for this flow."),
                "certainty": DETERMINISTIC,
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{module_name}:flow:{flow_id}"],
            }
        )
    return result


def build_branch_merge_behavior(flow: Dict[str, Any]) -> Dict[str, Any]:
    families = [str(step.get("family", "")).lower() for step in flow.get("steps", [])]
    return {
        "has_splitter": any("split" in family or "selector" in family or "selsplit" in family for family in families)
        or bool(flow.get("branch_points")),
        "has_selector": any("selector" in family or "selsplit" in family for family in families),
        "has_merge": any("merge" in family for family in families) or bool(flow.get("join_points")),
        "has_waitmerge": any("waitmerge" in family for family in families),
        "branch_points": flow.get("branch_points", []),
        "join_points": flow.get("join_points", []),
        "blocking_points": flow.get("blocking_points", []),
        "certainty": DETERMINISTIC,
        "source_layers": ["knowledge_ir"],
    }


def related_assignments_for_flow(facts: Dict[str, Any], ai_flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    ai_related = ai_flow.get("compact_context", {}).get("related_assign_dependencies", []) if ai_flow else []
    if isinstance(ai_related, list) and ai_related:
        return [
            {
                "assignment_id": f"assign_{item.get('index', '')}",
                "index": item.get("index"),
                "lhs": item.get("lhs", ""),
                "rhs": item.get("rhs", ""),
                "lhs_terms": item.get("lhs_terms", []),
                "rhs_terms": item.get("rhs_terms", []),
                "reasons": item.get("reasons", []),
                "certainty": DETERMINISTIC,
                "source_layers": ["ai_context", "knowledge_ir"],
                "evidence_refs": [f"ev:{facts.get('module', '')}:assignments"],
            }
            for item in ai_related
            if isinstance(item, dict)
        ]
    return []


def build_outputs_or_effects(
    flow: Dict[str, Any],
    facts: Dict[str, Any],
    module_name: str,
    flow_id: str,
) -> List[Dict[str, Any]]:
    interface_outputs = {
        item.get("name")
        for item in facts.get("interface", {}).get("event_outputs", [])
        if isinstance(item, dict)
    }
    result = []
    for endpoint in flow.get("endpoints", []):
        result.append(
            {
                "signal": endpoint,
                "effect_type": "module_output_event" if endpoint in interface_outputs else "internal_event",
                "certainty": DETERMINISTIC,
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{module_name}:flow:{flow_id}"],
            }
        )
    if not result:
        result.append(
            {
                "effect_type": "evidence_gap",
                "reason": "Knowledge IR did not find a module output endpoint for this flow.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{module_name}:flow:{flow_id}"],
            }
        )
    return result


def payloads_for_flow(facts: Dict[str, Any], flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    flow_events = {str(flow.get("start", ""))}
    flow_events.update(str(item) for item in flow.get("endpoints", []))
    payloads: List[Dict[str, Any]] = []
    for contract in facts.get("interface_data_contract", []):
        if str(contract.get("event", "")) not in flow_events:
            continue
        for payload in contract.get("payloads", []):
            if not isinstance(payload, dict):
                continue
            payloads.append(
                {
                    "event": contract.get("event", ""),
                    "direction": contract.get("direction", ""),
                    "name": payload.get("name", ""),
                    "width_text": payload.get("width_text", ""),
                    "certainty": DETERMINISTIC,
                    "source_layers": ["knowledge_ir"],
                    "evidence_refs": [f"ev:{facts.get('module', '')}:interface_data_contract"],
                }
            )
    return payloads


def flow_gaps(
    module_name: str,
    flow_id: str,
    flow: Dict[str, Any],
    semantic_claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    gaps = [
        {
            "field": f"internal_event_flow.{flow.get('start', '')}",
            "reason": warning,
            "certainty": EVIDENCE_GAP,
            "source_layers": ["knowledge_ir"],
            "evidence_refs": [f"ev:{module_name}:knowledge_module"],
        }
        for warning in flow.get("warnings", [])
    ]
    if not semantic_claims:
        gaps.append(
            {
                "field": f"semantic_flow.{flow.get('start', '')}",
                "reason": "No Semantic Layer flow interpretation is available.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["semantic_layer"],
                "evidence_refs": [],
            }
        )
    elif any(item.get("requires_rtl_source_review") for item in semantic_claims):
        gaps.append(
            {
                "field": f"semantic_flow.{flow.get('start', '')}",
                "reason": "Semantic Layer requested RTL source review for this flow.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["semantic_layer"],
                "evidence_refs": [f"ev:{module_name}:semantic_flow:{flow_id}"] if flow_id else [],
            }
        )
    return gaps


def build_flow_writer_hints(
    flow: Dict[str, Any],
    semantic_claims: List[Dict[str, Any]],
    manual_importance: str,
) -> List[Dict[str, Any]]:
    hints = [
        {
            "hint": "Lead with the trigger drive event and its payload binding.",
            "source": "manual_context_policy",
        }
    ]
    if flow.get("branch_points"):
        hints.append({"hint": "Explain branch/split points before listing every downstream signal.", "source": "manual_context_policy"})
    if flow.get("join_points"):
        hints.append({"hint": "Call out merge/arbitration points because they affect event ordering.", "source": "manual_context_policy"})
    if manual_importance != "high":
        hints.append({"hint": "Keep this flow brief unless referenced by the module responsibility.", "source": "manual_context_policy"})
    if any(item.get("requires_rtl_source_review") for item in semantic_claims):
        hints.append({"hint": "Mark interpretation as review-needed; do not present it as confirmed design intent.", "source": "manual_context_policy"})
    return hints


def build_flow_title(module_name: str, flow: Dict[str, Any]) -> str:
    start = str(flow.get("start", "input drive"))
    endpoints = [str(item) for item in flow.get("endpoints", [])]
    if endpoints:
        return f"{start} to {', '.join(endpoints[:3])}"
    return f"{module_name} flow from {start}"


def flow_manual_importance(flow: Dict[str, Any], semantic_claims: List[Dict[str, Any]]) -> str:
    if any(item.get("doc_priority") == "primary" for item in semantic_claims):
        return "high"
    if flow.get("endpoints") and len(flow.get("steps", [])) >= 2:
        return "high"
    if flow.get("steps"):
        return "medium"
    return "low"


def build_flow_index_item(module_name: str, flow_rel: str, context: Dict[str, Any]) -> Dict[str, Any]:
    meaning = context.get("semantic_meaning", {})
    return {
        "flow_id": context.get("flow_id", ""),
        "module": module_name,
        "title": context.get("title", ""),
        "trigger_event": context.get("trigger_event", {}).get("signal", ""),
        "payloads": [item.get("name", "") for item in context.get("payloads", [])],
        "endpoint_count": len(context.get("outputs_or_effects", [])),
        "component_step_count": len(context.get("component_steps", [])),
        "manual_importance": context.get("manual_importance", "medium"),
        "summary": meaning.get("value", ""),
        "requires_review": meaning.get("review_status") == "needs_review" or bool(context.get("gaps")),
        "source_file": flow_rel,
        "evidence_refs": context.get("evidence_refs", []),
    }


def build_interface_index_item(module_name: str, interfaces_rel: str, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "interface_id": item.get("interface_id", ""),
        "module": module_name,
        "interface_name": item.get("interface_name", ""),
        "direction": item.get("direction", ""),
        "role": item.get("role", "event_drive"),
        "doc_priority": item.get("doc_priority", "secondary"),
        "payload_count": len(item.get("payload_signals", [])),
        "free_count": len(item.get("free_backpressure_signals", [])),
        "peer_count": len(item.get("peer_modules", [])),
        "source_file": interfaces_rel,
        "evidence_refs": item.get("evidence_refs", []),
    }


def build_region_map(
    reachable: List[str],
    module_facts: Dict[str, Dict[str, Any]],
    parser_modules: Dict[str, Dict[str, Any]],
    topology: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for module_name in reachable:
        module_name = str(module_name)
        region_claim = classify_region(
            module_name,
            module_facts.get(module_name, {}),
            parser_modules.get(module_name, {}),
        )
        result[str(region_claim["value"])].append(
            {
                "module": module_name,
                "confidence": region_claim["confidence"],
                "certainty": region_claim["certainty"],
                "parents": topology.get("parents", {}).get(module_name, []),
                "children_count": len(topology.get("children", {}).get(module_name, [])),
            }
        )
    return {
        "certainty": DERIVED,
        "source_layers": ["manual_context", "parse", "knowledge_ir"],
        "regions": {region: sorted(items, key=lambda item: item["module"]) for region, items in sorted(result.items())},
        "evidence_refs": ["ev:project:module_list"],
    }


def build_major_modules(
    reachable: List[str],
    semantic_modules: Dict[str, Dict[str, Any]],
    region_map: Dict[str, Any],
    topology: Dict[str, Any],
) -> List[Dict[str, Any]]:
    by_region = region_map.get("regions", {})
    region_for_module = {
        item["module"]: region
        for region, items in by_region.items()
        for item in items
    }
    candidates = []
    for module_name in reachable:
        module_name = str(module_name)
        semantic = semantic_modules.get(module_name, {})
        role = first_claim(select_claims(semantic, {"module_role"}, limit=1), "module_role")
        score = 0
        score += 4 if role and role.get("doc_priority") == "primary" else 0
        score += len(topology.get("children", {}).get(module_name, []))
        score += len(topology.get("upstream", {}).get(module_name, []))
        score += len(topology.get("downstream", {}).get(module_name, []))
        if module_name in {"cpu_top_all", "fetch", "decoder", "launch", "execute", "lsu", "wb", "grf", "prf", "IONetwork", "socmem"}:
            score += 8
        candidates.append(
            {
                "module": module_name,
                "region": region_for_module.get(module_name, "other"),
                "importance_score": score,
                "summary": role.get("summary", "") if role else "",
                "certainty": AI_INFERRED if role else DERIVED,
                "source_layers": ["semantic_layer"] if role else ["manual_context"],
                "evidence_refs": [f"ev:{module_name}:semantic_module"] if role else [f"ev:{module_name}:knowledge_module"],
            }
        )
    return sorted(candidates, key=lambda item: (-item["importance_score"], item["module"]))[:40]


def build_manual_toc_plan(top_module: str, reachable: List[str]) -> List[Dict[str, Any]]:
    module_pages = [
        {
            "page_type": "module",
            "module": str(module_name),
            "source_file": f"modules/{safe_filename(str(module_name))}/module_context.json",
        }
        for module_name in reachable
    ]
    return [
        {
            "page_type": "system_overview",
            "title": "System Overview",
            "source_file": "project_context.json",
        },
        {
            "page_type": "interface_index",
            "title": "Interface Index",
            "source_file": "interface_index.json",
        },
        {
            "page_type": "flow_index",
            "title": "Drive Flow Index",
            "source_file": "flow_index.json",
        },
        {
            "page_type": "module_group",
            "title": "Module Pages",
            "top_module": top_module,
            "pages": module_pages,
        },
    ]


def build_system_level_gaps(
    project_facts: Dict[str, Any],
    parser_index: Dict[str, Any],
    top_semantic: Dict[str, Any],
) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    parser_stats = project_facts.get("parser_stats", {})
    unresolved = parser_stats.get("unresolved_instance_count", 0)
    warnings = parser_stats.get("warning_count", 0)
    if unresolved:
        gaps.append(
            {
                "field": "parser_stats.unresolved_instance_count",
                "reason": f"{unresolved} unresolved parser instances remain.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["parse", "knowledge_ir"],
                "evidence_refs": ["ev:project:parser_stats"],
            }
        )
    if warnings:
        gaps.append(
            {
                "field": "parser_stats.warning_count",
                "reason": f"{warnings} parser warnings are present.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["parse", "knowledge_ir"],
                "evidence_refs": ["ev:project:parser_stats"],
            }
        )
    if not top_semantic:
        gaps.append(
            {
                "field": "semantic.top_module",
                "reason": "Top module semantic claims are unavailable.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["semantic_layer"],
                "evidence_refs": [],
            }
        )
    if not parser_index:
        gaps.append(
            {
                "field": "parser_project_index",
                "reason": "Parser project_index.json was not available.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["parse"],
                "evidence_refs": [],
            }
        )
    return gaps


def classify_region(module_name: str, facts: Dict[str, Any], parser_module: Dict[str, Any]) -> Dict[str, Any]:
    source = str(facts.get("source", {}).get("rtl_file", "") or parser_module.get("file", ""))
    text = f"{module_name} {source}".lower()
    if any(token in text for token in ("execute", "adder", "mul", "div", "shift", "align", "eor", "ander", "orrer", "satq", "hsb")):
        region = "execution_pipeline"
    elif any(token in text for token in ("fetch", "decode", "decoder", "launch", "wb", "writeback", "grf", "prf", "lsu", "intandexc", "cpu")):
        region = "cpu"
    elif any(token in text for token in ("noc", "ionet", "route", "node", "arbmsg")):
        region = "noc"
    elif any(token in text for token in ("memory", "socmem", "sram", "rom", "data_slot", "memory_slot")):
        region = "storage"
    elif any(token in text for token in ("uart", "spi", "iic", "i2c", "gpio", "watchdog", "timer", "pwm", "perip")):
        region = "peripheral"
    elif "slot" in text:
        region = "system_slot"
    else:
        region = "other"
    return {
        "value": region,
        "certainty": DERIVED,
        "confidence": "medium" if region != "other" else "low",
        "source_layers": ["manual_context", "parse"],
        "evidence_refs": [f"ev:{module_name}:parser_module"],
        "classification_rule": "module_name_and_source_path_keyword",
    }


def add_module_evidence(
    evidence_entries: Dict[str, Dict[str, Any]],
    top_module: str,
    module_name: str,
    facts: Dict[str, Any],
    parser_module: Dict[str, Any],
    *,
    knowledge_rel: str,
    semantic_rel: str,
) -> None:
    evidence_entries.setdefault(
        "ev:project:top_module",
        {
            "evidence_id": "ev:project:top_module",
            "certainty": DETERMINISTIC,
            "source_layer": "knowledge_ir",
            "artifact": f"rtl/knowledge_ir/{top_module}/manifest.json",
            "json_path": "$.top_module",
        },
    )
    evidence_entries.setdefault(
        "ev:project:module_list",
        {
            "evidence_id": "ev:project:module_list",
            "certainty": DETERMINISTIC,
            "source_layer": "knowledge_ir",
            "artifact": f"rtl/knowledge_ir/{top_module}/project.json",
            "json_path": "$.reachable_modules",
        },
    )
    evidence_entries.setdefault(
        "ev:project:top_level",
        {
            "evidence_id": "ev:project:top_level",
            "certainty": DETERMINISTIC,
            "source_layer": "knowledge_ir",
            "artifact": f"rtl/knowledge_ir/{top_module}/project.json",
            "json_path": "$.top_level",
        },
    )
    evidence_entries.setdefault(
        "ev:project:parser_stats",
        {
            "evidence_id": "ev:project:parser_stats",
            "certainty": DETERMINISTIC,
            "source_layer": "knowledge_ir",
            "artifact": f"rtl/knowledge_ir/{top_module}/project.json",
            "json_path": "$.parser_stats",
        },
    )
    source_file = parser_module.get("file") or facts.get("source", {}).get("rtl_file", "")
    base = f"ev:{module_name}"
    evidence_entries[f"{base}:knowledge_module"] = {
        "evidence_id": f"{base}:knowledge_module",
        "certainty": DETERMINISTIC,
        "source_layer": "knowledge_ir",
        "artifact": f"rtl/knowledge_ir/{top_module}/{knowledge_rel}",
        "json_path": "$",
        "rtl_locations": [{"file": source_file}] if source_file else [],
    }
    evidence_entries[f"{base}:interface"] = {
        "evidence_id": f"{base}:interface",
        "certainty": DETERMINISTIC,
        "source_layer": "knowledge_ir",
        "artifact": f"rtl/knowledge_ir/{top_module}/{knowledge_rel}",
        "json_path": "$.interface",
        "rtl_locations": [{"file": source_file}] if source_file else [],
    }
    evidence_entries[f"{base}:interface_data_contract"] = {
        "evidence_id": f"{base}:interface_data_contract",
        "certainty": DETERMINISTIC,
        "source_layer": "knowledge_ir",
        "artifact": f"rtl/knowledge_ir/{top_module}/{knowledge_rel}",
        "json_path": "$.interface_data_contract",
        "rtl_locations": [{"file": source_file}] if source_file else [],
    }
    evidence_entries[f"{base}:key_instances"] = {
        "evidence_id": f"{base}:key_instances",
        "certainty": DETERMINISTIC,
        "source_layer": "knowledge_ir",
        "artifact": f"rtl/knowledge_ir/{top_module}/{knowledge_rel}",
        "json_path": "$.key_instances",
        "rtl_locations": [{"file": source_file}] if source_file else [],
    }
    evidence_entries[f"{base}:assignments"] = {
        "evidence_id": f"{base}:assignments",
        "certainty": DETERMINISTIC,
        "source_layer": "knowledge_ir",
        "artifact": f"rtl/knowledge_ir/{top_module}/{knowledge_rel}",
        "json_path": "$.assignment_facts",
        "rtl_locations": [{"file": source_file}] if source_file else [],
    }
    evidence_entries[f"{base}:parser_module"] = {
        "evidence_id": f"{base}:parser_module",
        "certainty": DETERMINISTIC,
        "source_layer": "parse",
        "artifact": f"rtl/parser_pipeline_rtl/modules/{safe_filename(module_name)}.json",
        "json_path": "$",
        "rtl_locations": [{"file": source_file}] if source_file else [],
    }
    if semantic_rel:
        evidence_entries[f"{base}:semantic_module"] = {
            "evidence_id": f"{base}:semantic_module",
            "certainty": AI_INFERRED,
            "source_layer": "semantic_layer",
            "artifact": f"rtl/knowledge_ir/{top_module}/{semantic_rel}",
            "json_path": "$.claims",
            "rtl_locations": [{"file": source_file}] if source_file else [],
        }


def select_claims(card: Dict[str, Any], claim_types: set[str], *, limit: int) -> List[Dict[str, Any]]:
    claims = [
        item
        for item in card.get("claims", [])
        if isinstance(item, dict) and item.get("claim_type") in claim_types
    ]
    return sorted(
        claims,
        key=lambda item: (
            priority_rank(str(item.get("doc_priority", ""))),
            confidence_rank(str(item.get("confidence", ""))),
            item.get("id", ""),
        ),
    )[:limit]


def first_claim(claims: List[Dict[str, Any]], claim_type: str) -> Dict[str, Any]:
    for item in claims:
        if item.get("claim_type") == claim_type:
            return item
    return {}


def semantic_claim_to_claim(claim_item: Dict[str, Any], evidence_refs: List[str]) -> Dict[str, Any]:
    if not claim_item:
        return empty_inference_gap("No semantic claim is available.")
    confidence = str(claim_item.get("confidence", "low") or "low")
    review_needed = bool(claim_item.get("requires_rtl_source_review")) or confidence == "low"
    return {
        "value": claim_item.get("summary", ""),
        "explanation": claim_item.get("explanation", ""),
        "certainty": AI_INFERRED,
        "confidence": confidence,
        "source_layers": ["semantic_layer"],
        "semantic_claim_id": claim_item.get("id", ""),
        "doc_priority": claim_item.get("doc_priority", ""),
        "signals": claim_item.get("signals", []),
        "instances": claim_item.get("instances", []),
        "related_flows": claim_item.get("related_flows", []),
        "related_assignments": claim_item.get("related_assignments", []),
        "requires_rtl_source_review": bool(claim_item.get("requires_rtl_source_review")),
        "review_status": "needs_review" if review_needed else "ready",
        "evidence_refs": evidence_refs,
        "semantic_evidence": claim_item.get("evidence", []),
    }


def semantic_claims_to_manual_description(claims: List[Dict[str, Any]], evidence_refs: List[str]) -> Dict[str, Any]:
    if not claims:
        return empty_inference_gap("No Semantic Layer description is available.")
    primary = claims[0]
    related = [semantic_claim_to_claim(item, evidence_refs) for item in claims[1:]]
    result = semantic_claim_to_claim(primary, evidence_refs)
    result["supporting_claims"] = related
    return result


def empty_inference_gap(reason: str) -> Dict[str, Any]:
    return {
        "value": "",
        "certainty": EVIDENCE_GAP,
        "confidence": "low",
        "source_layers": [],
        "evidence_refs": [],
        "reason": reason,
        "review_status": "needs_review",
    }


def claim(
    value: Any,
    certainty: str,
    source_layers: List[str],
    evidence_refs: List[str],
    *,
    confidence: str | None = None,
) -> Dict[str, Any]:
    payload = {
        "value": value,
        "certainty": certainty,
        "source_layers": source_layers,
        "evidence_refs": evidence_refs,
    }
    if confidence:
        payload["confidence"] = confidence
    return payload


def signal_fact(
    payload: Dict[str, Any],
    certainty: str,
    source_layers: List[str],
    evidence_refs: List[str],
) -> Dict[str, Any]:
    return {
        "name": payload.get("name", ""),
        "direction": payload.get("direction", ""),
        "width_text": payload.get("width_text", ""),
        "role": payload.get("role", ""),
        "certainty": certainty,
        "source_layers": source_layers,
        "evidence_refs": evidence_refs,
    }


def build_free_signal(contract: Dict[str, Any], facts: Dict[str, Any], module_name: str) -> List[Dict[str, Any]]:
    free_name = contract.get("free_signal", "")
    if not free_name:
        return []
    for key in ("free_inputs", "free_outputs"):
        for item in facts.get("interface", {}).get(key, []):
            if item.get("name") == free_name:
                signal = signal_fact(item, DETERMINISTIC, ["knowledge_ir"], [f"ev:{module_name}:interface"])
                signal["doc_priority"] = "reference"
                signal["include_condition"] = "include_when_affects_drive_availability"
                return [signal]
    return [
        {
            "name": free_name,
            "role": "event_free",
            "doc_priority": "reference",
            "include_condition": "include_when_affects_drive_availability",
            "certainty": DETERMINISTIC,
            "source_layers": ["knowledge_ir"],
            "evidence_refs": [f"ev:{module_name}:interface_data_contract"],
        }
    ]


def interface_uncertainties(
    module_name: str,
    event_name: str,
    contract: Dict[str, Any],
    facts: Dict[str, Any],
) -> List[Dict[str, Any]]:
    gaps = []
    if not contract:
        gaps.append(
            {
                "field": f"interface_data_contract.{event_name}",
                "reason": "No event-payload contract was built for this event.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{module_name}:interface"],
            }
        )
    if contract and not contract.get("payloads"):
        gaps.append(
            {
                "field": f"interface_data_contract.{event_name}.payloads",
                "reason": "Event has no bound payload signal.",
                "certainty": EVIDENCE_GAP,
                "source_layers": ["knowledge_ir"],
                "evidence_refs": [f"ev:{module_name}:interface_data_contract"],
            }
        )
    for gap in facts.get("evidence_gaps", []):
        field = str(gap.get("field", ""))
        if event_name in field:
            gaps.append(
                {
                    "field": field,
                    "reason": gap.get("reason", ""),
                    "certainty": EVIDENCE_GAP,
                    "source_layers": ["knowledge_ir"],
                    "evidence_refs": [f"ev:{module_name}:knowledge_module"],
                }
            )
    return gaps


def collect_group_peers(
    module_name: str,
    ports: List[Dict[str, Any]],
    peer_index: Dict[tuple[str, str], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for port in ports:
        result.extend(peer_index.get((module_name, str(port.get("name", ""))), []))
    return result[:40]


def index_claims_by_signal(claims: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for claim_item in claims:
        for signal in claim_item.get("signals", []):
            result[str(signal)].append(claim_item)
    return dict(result)


def index_assignment_claims(claims: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for claim_item in claims:
        for assignment in claim_item.get("related_assignments", []):
            result[str(assignment).replace("assign_", "")] = claim_item
        subject = str(claim_item.get("subject", ""))
        if subject.lower().startswith("assign"):
            result[subject.replace("assign_", "").replace("assign", "").strip("_: ")] = claim_item
    return result


def classify_assignment_impact(assignment: Dict[str, Any], claim_item: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(assignment.get("lhs", "")),
            str(assignment.get("rhs", "")),
            str(claim_item.get("summary", "")),
            str(claim_item.get("explanation", "")),
        ]
    ).lower()
    if any(token in text for token in ("drive", "free", "valid", "flag", "wen", "sel", "switch", "control")):
        return "control_path"
    if any(token in text for token in ("data", "_32", "_64", "_96", "_128", "_163", "_207", "payload", "result")):
        return "data_path"
    return "unknown"


def assignment_doc_priority(assignment: Dict[str, Any], claim_item: Dict[str, Any]) -> str:
    if claim_item.get("doc_priority") == "primary":
        return "primary"
    if assignment.get("interface_related"):
        return "primary"
    if classify_assignment_impact(assignment, claim_item) in {"control_path", "data_path"}:
        return "secondary"
    return "reference"


def collect_interface_signal_names(facts: Dict[str, Any]) -> set[str]:
    names: set[str] = set()
    interface = facts.get("interface", {})
    for value in interface.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    return names


def priority_weight(priority: str) -> int:
    return {"primary": 4, "secondary": 2, "reference": 1}.get(str(priority), 1)


def priority_rank(priority: str) -> int:
    return {"primary": 0, "secondary": 1, "reference": 2}.get(str(priority), 3)


def confidence_rank(confidence: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(confidence), 3)


def manual_importance_to_doc_priority(importance: str) -> str:
    return {
        "high": "primary",
        "medium": "secondary",
        "low": "reference",
    }.get(str(importance), "secondary")


def signal_certainty_from_sources(sources: set[str]) -> str:
    if "interface" in sources or "local_signal" in sources:
        return DETERMINISTIC
    if "flow" in sources:
        return DERIVED
    return AI_INFERRED


def signal_source_layers(sources: set[str]) -> List[str]:
    layers: List[str] = []
    if "local_signal" in sources:
        layers.append("parse")
    if "interface" in sources or "flow" in sources:
        layers.append("knowledge_ir")
    if "semantic" in sources:
        layers.append("semantic_layer")
    return layers or ["manual_context"]


def signal_evidence_refs(module_name: str, sources: set[str], has_semantic: bool) -> List[str]:
    refs: List[str] = []
    if "local_signal" in sources:
        refs.append(f"ev:{module_name}:parser_module")
    if "interface" in sources:
        refs.append(f"ev:{module_name}:interface")
    if "flow" in sources:
        refs.append(f"ev:{module_name}:knowledge_module")
    if "semantic" in sources and has_semantic:
        refs.append(f"ev:{module_name}:semantic_module")
    return refs


def family_rank(family: str) -> int:
    lowered = family.lower()
    if "waitmerge" in lowered:
        return 0
    if "merge" in lowered:
        return 1
    if "split" in lowered or "selector" in lowered or "selsplit" in lowered:
        return 2
    if "fifo" in lowered:
        return 3
    return 4


def build_gap_claims(gaps: List[Dict[str, Any]], module_name: str) -> List[Dict[str, Any]]:
    return [
        {
            "field": gap.get("field", ""),
            "reason": gap.get("reason", ""),
            "certainty": EVIDENCE_GAP,
            "source_layers": ["knowledge_ir"],
            "evidence_refs": [f"ev:{module_name}:knowledge_module"],
        }
        for gap in gaps
        if isinstance(gap, dict)
    ]


def fallback_flow_id(module_name: str, flow: Dict[str, Any], index: int) -> str:
    return f"flow_{index:03d}_{safe_filename(module_name)}_{safe_filename(str(flow.get('start', 'drive')))}"


def semantic_flow_rel_for(flow_paths: List[str], index: int, module_name: str, flow_id: str) -> str:
    return f"semantic/flows/{safe_filename(module_name)}/{safe_filename(flow_id)}.json"


def semantic_module_rel(semantic_index: Dict[str, Any], module_name: str) -> str:
    rel = semantic_index.get("files", {}).get("modules", {}).get(module_name, "")
    return str(rel) if rel else ""


def read_ai_module_context(knowledge_root: Path, ai_index: Dict[str, Any], module_name: str) -> Dict[str, Any]:
    rel = ai_index.get("files", {}).get("modules", {}).get(module_name, "") if ai_index else ""
    if not rel:
        return {}
    return read_optional_json(knowledge_root / str(rel))


def load_ai_flows_by_start(knowledge_root: Path, flow_paths: List[str]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for rel_path in flow_paths:
        if not isinstance(rel_path, str):
            continue
        payload = read_optional_json(knowledge_root / rel_path)
        start = str(payload.get("compact_context", {}).get("flow", {}).get("start", ""))
        if start:
            result[start] = payload
    return result


def load_semantic_modules(knowledge_root: Path, semantic_index: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for module_name, rel_path in semantic_index.get("files", {}).get("modules", {}).items():
        if isinstance(rel_path, str):
            result[str(module_name)] = read_optional_json(knowledge_root / rel_path)
    return result


def load_semantic_flows(knowledge_root: Path, semantic_index: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    result: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for module_name, flow_paths in semantic_index.get("files", {}).get("flows", {}).items():
        if not isinstance(flow_paths, list):
            continue
        for rel_path in flow_paths:
            if not isinstance(rel_path, str):
                continue
            card = read_optional_json(knowledge_root / rel_path)
            flow_id = str(card.get("flow_id", Path(rel_path).stem))
            result[str(module_name)][flow_id] = card
    return dict(result)


def load_parser_modules(parser_root: Path) -> Dict[str, Dict[str, Any]]:
    modules_dir = parser_root / "modules"
    modules: Dict[str, Dict[str, Any]] = {}
    if not modules_dir.is_dir():
        return modules
    for path in sorted(modules_dir.glob("*.json")):
        payload = read_json(path)
        name = str(payload.get("name", path.stem))
        modules[name] = payload
    return modules


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    return read_json(path)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_filename(name: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in name)
    return safe.strip("._") or "item"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Manual Context Layer files from Knowledge IR.")
    parser.add_argument("--knowledge-dir", default="rtl/knowledge_ir/arm_soc_top")
    parser.add_argument("--parser-artifacts-root", default="rtl/parser_pipeline_rtl")
    parser.add_argument("--output-dir", default="", help="Defaults to rtl/manual_context/<top_module>.")
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--no-semantic", action="store_true", help="Do not consume Semantic Layer claims.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest = build_manual_context(
        args.knowledge_dir,
        args.parser_artifacts_root,
        args.output_dir or None,
        clean=not args.no_clean,
        include_semantic=not args.no_semantic,
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "top_module": manifest.get("top_module", ""),
                "counts": manifest.get("counts", {}),
                "output_dir": str(Path(args.output_dir) if args.output_dir else Path("rtl/manual_context") / str(manifest.get("top_module", ""))),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
