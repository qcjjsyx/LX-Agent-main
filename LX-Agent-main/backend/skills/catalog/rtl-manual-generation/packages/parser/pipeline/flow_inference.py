"""Infer signal and flow roles from module connections and naming rules."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


_SIMPLE_SIGNAL_RE = re.compile(r"[A-Za-z_]\w*")


def infer_signal_role(name: str) -> str:
    normalized = name.strip()
    lowered = normalized.lower()
    if re.match(r"^(rst|rstn|reset)\b", lowered):
        return "reset"
    if "valid" in lowered or lowered.startswith("sel") or "switch" in lowered or lowered == "pmt" or "permit" in lowered:
        return "condition"
    if "drive" in lowered or _has_drv_token(lowered):
        return "event_drive"
    if "free" in lowered:
        return "event_free"
    if "data" in lowered:
        return "payload_data"
    return "unknown"


def _has_drv_token(lowered_name: str) -> bool:
    return bool(re.search(r"(^|_)drv|^[iow]_drv", lowered_name))


def extract_signal_terms(signal_name: str) -> List[str]:
    """Return deterministic member signals for simple concatenations.

    This intentionally handles only direct identifier terms such as
    ``{a,b,c}``. Complex Verilog expressions stay opaque so downstream layers
    do not infer semantics beyond parser facts.
    """

    normalized = signal_name.strip()
    if not normalized:
        return []
    if _SIMPLE_SIGNAL_RE.fullmatch(normalized):
        return [normalized]
    if not normalized.startswith("{") or not normalized.endswith("}"):
        return []

    inner = normalized[1:-1].strip()
    if not inner:
        return []

    terms = [_strip_signal_term(term) for term in _split_top_level_terms(inner)]
    if not terms or any(not _SIMPLE_SIGNAL_RE.fullmatch(term) for term in terms):
        return []
    return terms


def _split_top_level_terms(text: str) -> List[str]:
    items: List[str] = []
    depth_brace = 0
    depth_bracket = 0
    depth_paren = 0
    current: List[str] = []
    for char in text:
        if char == "," and depth_brace == 0 and depth_bracket == 0 and depth_paren == 0:
            items.append("".join(current))
            current = []
            continue
        current.append(char)
        if char == "{":
            depth_brace += 1
        elif char == "}":
            depth_brace -= 1
        elif char == "[":
            depth_bracket += 1
        elif char == "]":
            depth_bracket -= 1
        elif char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren -= 1
    if current:
        items.append("".join(current))
    return items


def _strip_signal_term(term: str) -> str:
    return term.strip()


def build_flow_graph(parse_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    signals: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    for port in parse_result.get("ports", []):
        signals[port["name"]] = {
            "name": port["name"],
            "kind": f"port_{port['direction']}",
            "width_text": port.get("width_text"),
            "role": infer_signal_role(port["name"]),
        }

    for signal in parse_result.get("local_signals", []):
        signals.setdefault(
            signal["name"],
            {
                "name": signal["name"],
                "kind": "local_signal",
                "width_text": signal.get("width_text"),
                "role": infer_signal_role(signal["name"]),
            },
        )

    for instance in parse_result.get("instances", []):
        for connection in instance.get("connections", []):
            signal_name = connection.get("signal") or ""
            if not signal_name:
                continue
            signal_terms = list(connection.get("signal_terms") or extract_signal_terms(signal_name))
            signals.setdefault(
                signal_name,
                {
                    "name": signal_name,
                    "kind": "expression" if _looks_like_expression(signal_name) else "implicit_signal",
                    "width_text": None,
                    "role": infer_signal_role(signal_name),
                },
            )
            for signal_term in signal_terms:
                signals.setdefault(
                    signal_term,
                    {
                        "name": signal_term,
                        "kind": "implicit_signal",
                        "width_text": None,
                        "role": infer_signal_role(signal_term),
                    },
                )
            port_direction = connection.get("port_direction") or "unknown"
            edge_base = {
                "instance_name": instance["instance_name"],
                "module_type": instance["module_type"],
                "port": connection["port"],
                "port_direction": port_direction,
                "signal_role": connection["signal_role"],
                "edge_kind": _edge_kind_for_direction(port_direction),
            }
            edges.append(
                {
                    "signal": signal_name,
                    **edge_base,
                }
            )
            if signal_terms and signal_terms != [signal_name]:
                for signal_term in signal_terms:
                    edges.append(
                        {
                            "signal": signal_term,
                            "source_expression": signal_name,
                            **edge_base,
                        }
                    )

    for transparent_flow in parse_result.get("transparent_flows", []):
        input_signal = transparent_flow.get("input_signal") or ""
        output_signal = transparent_flow.get("output_signal") or ""
        if not input_signal or not output_signal:
            continue
        signal_role = transparent_flow.get("signal_role") or infer_signal_role(output_signal)
        if signal_role == "unknown":
            signal_role = infer_signal_role(input_signal)
        for signal_name in (input_signal, output_signal):
            signals.setdefault(
                signal_name,
                {
                    "name": signal_name,
                    "kind": "implicit_signal",
                    "width_text": None,
                    "role": infer_signal_role(signal_name),
                },
            )
        edge_base = {
            "instance_name": transparent_flow.get("instance_name", ""),
            "module_type": transparent_flow.get("module_type", ""),
            "transparent": True,
            "transparent_source": transparent_flow.get("source", "skip_helper_rule"),
            "signal_role": signal_role,
        }
        edges.append(
            {
                "signal": input_signal,
                "port": transparent_flow.get("input_port", "inR"),
                "port_direction": "input",
                "edge_kind": "signal_to_instance",
                **edge_base,
            }
        )
        edges.append(
            {
                "signal": output_signal,
                "port": transparent_flow.get("output_port", "outR"),
                "port_direction": "output",
                "edge_kind": "instance_to_signal",
                **edge_base,
            }
        )

    assignment_dependencies = build_assignment_dependencies(parse_result.get("assignments", []))
    for assignment in parse_result.get("assignments", []):
        for signal_name in assignment.get("lhs_terms", []) + assignment.get("rhs_terms", []):
            signals.setdefault(
                signal_name,
                {
                    "name": signal_name,
                    "kind": "implicit_signal",
                    "width_text": None,
                    "role": infer_signal_role(signal_name),
                },
            )

    return {
        "signals": sorted(signals.values(), key=lambda item: item["name"]),
        "edges": edges,
        "assignment_dependencies": assignment_dependencies,
    }


def build_assignment_dependencies(assignments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dependencies: List[Dict[str, Any]] = []
    for assignment in assignments:
        lhs_terms = assignment.get("lhs_terms", [])
        rhs_terms = assignment.get("rhs_terms", [])
        if not lhs_terms or not rhs_terms:
            continue
        for lhs in lhs_terms:
            for rhs in rhs_terms:
                if lhs == rhs:
                    continue
                dependencies.append(
                    {
                        "from": rhs,
                        "to": lhs,
                        "assignment_index": assignment.get("index"),
                        "kind": "continuous_assign_dependency",
                        "lhs": assignment.get("lhs", ""),
                        "rhs": assignment.get("rhs", ""),
                    }
                )
    return dependencies


def build_connection_graph(parse_result: Dict[str, Any], flow_graph: Dict[str, Any]) -> Dict[str, Any]:
    """Build a module-scoped driver/load graph from parsed ports and instance edges."""

    module_name = parse_result.get("name", "")
    nodes = [
        {
            "id": "self",
            "kind": "module_boundary",
            "module": module_name,
        }
    ]
    for instance in parse_result.get("instances", []):
        node = {
            "id": instance.get("instance_name", ""),
            "kind": "instance",
            "module_type": instance.get("module_type", ""),
            "artifact_kind": instance.get("artifact_kind", "unknown"),
        }
        for optional_key in ("target_ref", "family", "ignored_unresolved"):
            if optional_key in instance:
                node[optional_key] = instance[optional_key]
        nodes.append(node)
    for transparent_flow in parse_result.get("transparent_flows", []):
        instance_name = transparent_flow.get("instance_name", "")
        if not instance_name:
            continue
        nodes.append(
            {
                "id": instance_name,
                "kind": "transparent_helper",
                "module_type": transparent_flow.get("module_type", ""),
                "artifact_kind": "transparent_helper",
                "transparent_source": transparent_flow.get("source", "skip_helper_rule"),
            }
        )

    nets: Dict[str, Dict[str, Any]] = {}
    for signal in flow_graph.get("signals", []):
        signal_name = signal.get("name")
        if not signal_name:
            continue
        nets[signal_name] = {
            "signal": signal_name,
            "kind": signal.get("kind", "unknown"),
            "width_text": signal.get("width_text"),
            "role": signal.get("role", infer_signal_role(signal_name)),
            "drivers": [],
            "loads": [],
            "bidirectional": [],
            "boundary_inputs": [],
            "boundary_outputs": [],
        }

    for port in parse_result.get("ports", []):
        signal_name = port.get("name", "")
        if not signal_name:
            continue
        net = _ensure_net(nets, signal_name)
        endpoint = {
            "node": "self",
            "port": signal_name,
            "port_direction": port.get("direction", "unknown"),
        }
        direction = port.get("direction")
        if direction == "input":
            _append_unique_endpoint(net["boundary_inputs"], endpoint)
            _append_unique_endpoint(net["drivers"], {**endpoint, "driver_kind": "module_input"})
        elif direction == "output":
            _append_unique_endpoint(net["boundary_outputs"], endpoint)
            _append_unique_endpoint(net["loads"], {**endpoint, "load_kind": "module_output"})
        else:
            _append_unique_endpoint(net["bidirectional"], endpoint)

    for edge in flow_graph.get("edges", []):
        signal_name = edge.get("signal", "")
        if not signal_name:
            continue
        net = _ensure_net(nets, signal_name)
        endpoint = {
            "node": edge.get("instance_name", ""),
            "port": edge.get("port", ""),
            "module_type": edge.get("module_type", ""),
            "port_direction": edge.get("port_direction", "unknown"),
        }
        if edge.get("source_expression"):
            endpoint["source_expression"] = edge["source_expression"]
        if edge.get("transparent"):
            endpoint["transparent"] = True
            endpoint["transparent_source"] = edge.get("transparent_source", "")

        edge_kind = edge.get("edge_kind")
        if edge_kind == "instance_to_signal":
            _append_unique_endpoint(net["drivers"], {**endpoint, "driver_kind": "instance_output"})
        elif edge_kind == "signal_to_instance":
            _append_unique_endpoint(net["loads"], {**endpoint, "load_kind": "instance_input"})
        else:
            _append_unique_endpoint(net["bidirectional"], endpoint)

    sorted_nets = sorted(nets.values(), key=lambda item: item["signal"])
    connections = _build_connections(sorted_nets)
    return {
        "schema_version": "1.0",
        "scope": "module",
        "module": module_name,
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "nets": sorted_nets,
        "connections": connections,
        "summary": {
            "node_count": len(nodes),
            "net_count": len(sorted_nets),
            "connection_count": len(connections),
        },
    }


def collect_family_usage(instances: Iterable[Dict[str, Any]]) -> List[str]:
    families = sorted(
        {
            instance.get("family")
            for instance in instances
            if instance.get("artifact_kind") == "derived_component" and instance.get("family")
        } # type: ignore
    )
    return families


def _ensure_net(nets: Dict[str, Dict[str, Any]], signal_name: str) -> Dict[str, Any]:
    return nets.setdefault(
        signal_name,
        {
            "signal": signal_name,
            "kind": "implicit_signal",
            "width_text": None,
            "role": infer_signal_role(signal_name),
            "drivers": [],
            "loads": [],
            "bidirectional": [],
            "boundary_inputs": [],
            "boundary_outputs": [],
        },
    )


def _append_unique_endpoint(endpoints: List[Dict[str, Any]], endpoint: Dict[str, Any]) -> None:
    key = (
        endpoint.get("node"),
        endpoint.get("port"),
        endpoint.get("port_direction"),
        endpoint.get("source_expression"),
    )
    for existing in endpoints:
        existing_key = (
            existing.get("node"),
            existing.get("port"),
            existing.get("port_direction"),
            existing.get("source_expression"),
        )
        if existing_key == key:
            existing.update({key: value for key, value in endpoint.items() if value not in ("", None)})
            return
    endpoints.append({key: value for key, value in endpoint.items() if value not in ("", None)})


def _build_connections(nets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    connections: List[Dict[str, Any]] = []
    for net in nets:
        signal_name = net["signal"]
        role = net.get("role", infer_signal_role(signal_name))
        for driver in net.get("drivers", []):
            for load in net.get("loads", []):
                if _same_endpoint(driver, load):
                    continue
                connection = {
                    "from": _connection_endpoint(driver),
                    "to": _connection_endpoint(load),
                    "signal": signal_name,
                    "role": role,
                }
                if driver.get("source_expression"):
                    connection["source_expression"] = driver["source_expression"]
                elif load.get("source_expression"):
                    connection["source_expression"] = load["source_expression"]
                connections.append(connection)
    return sorted(
        connections,
        key=lambda item: (
            item["signal"],
            item["from"].get("node", ""),
            item["from"].get("port", ""),
            item["to"].get("node", ""),
            item["to"].get("port", ""),
        ),
    )


def _connection_endpoint(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "node": endpoint.get("node", ""),
        "port": endpoint.get("port", ""),
    }
    if endpoint.get("module_type"):
        result["module_type"] = endpoint["module_type"]
    if endpoint.get("driver_kind"):
        result["kind"] = endpoint["driver_kind"]
    elif endpoint.get("load_kind"):
        result["kind"] = endpoint["load_kind"]
    return result


def _same_endpoint(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return left.get("node") == right.get("node") and left.get("port") == right.get("port")


def summarize_component_semantics(family_template: Dict[str, Any], role_mapping: Dict[str, Any]) -> Dict[str, str]:
    contract = family_template.get("contract", {})
    invariants = contract.get("invariants", [])
    release_rule = contract.get("release_rule", {})
    payload_ports = role_mapping.get("payload", {}).get("ports", [])
    event_behavior = invariants[0] if invariants else ""
    data_behavior = (
        f"Payload-related ports: {', '.join(payload_ports)}."
        if payload_ports
        else "This family primarily communicates through event handshakes."
    )
    completion_behavior = release_rule.get("details", "")
    if not completion_behavior and len(invariants) > 1:
        completion_behavior = invariants[1]
    return {
        "event_behavior": event_behavior,
        "data_behavior": data_behavior,
        "completion_behavior": completion_behavior,
    }


def _edge_kind_for_direction(direction: str) -> str:
    if direction == "input":
        return "signal_to_instance"
    if direction == "output":
        return "instance_to_signal"
    return "bidirectional"


def _looks_like_expression(signal_name: str) -> bool:
    return bool(re.search(r"[{}?:&|^~+\-*/\[\]()]", signal_name))
