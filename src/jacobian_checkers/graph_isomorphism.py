"""Independent direct replay for finite simple-graph isomorphism mappings."""

from __future__ import annotations

from typing import Any

_MAX_ORDER = 256


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_INTEGER",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": detail,
    }


def _graph(value: object) -> tuple[tuple[str, ...], set[tuple[str, str]]]:
    if not isinstance(value, dict) or set(value) != {
        "graph_schema_version",
        "vertices",
        "edges",
    }:
        raise ValueError("malformed graph")
    vertices = value["vertices"]
    edges = value["edges"]
    if (
        value["graph_schema_version"] != "1"
        or not isinstance(vertices, list)
        or len(vertices) > _MAX_ORDER
        or vertices != sorted(set(vertices))
        or any(not isinstance(vertex, str) or not vertex for vertex in vertices)
        or not isinstance(edges, list)
    ):
        raise ValueError("malformed graph vertices")
    parsed_edges: list[tuple[str, str]] = []
    for edge in edges:
        if (
            not isinstance(edge, list)
            or len(edge) != 2
            or not all(isinstance(endpoint, str) for endpoint in edge)
            or edge[0] >= edge[1]
            or edge[0] not in vertices
            or edge[1] not in vertices
        ):
            raise ValueError("malformed graph edge")
        parsed_edges.append((edge[0], edge[1]))
    if parsed_edges != sorted(set(parsed_edges)):
        raise ValueError("graph edges are not canonical")
    return tuple(vertices), set(parsed_edges)


def check_isomorphism(request: dict[str, Any]) -> dict[str, Any]:
    """Check one explicit mapping by exhaustive adjacency replay."""

    try:
        if request.get("request_version") != "1":
            return _reject("unsupported request version")
        claim = request["claim"]["payload"]
        pair_artifact = request["scope"]
        mapping_artifact = request["candidate"]
        certificate = request["certificate"]["payload"]
        if (
            not isinstance(claim, dict)
            or claim.get("claim_schema_version") != "1"
            or claim.get("predicate") != "MAPPING_IS_GRAPH_ISOMORPHISM"
            or claim.get("graph_pair_uri") != pair_artifact.get("artifact_uri")
            or claim.get("mapping_uri") != mapping_artifact.get("artifact_uri")
        ):
            return _reject("unexpected graph-isomorphism claim or binding")
        pair = pair_artifact["payload"]
        mapping_payload = mapping_artifact["payload"]
        if (
            not isinstance(pair, dict)
            or pair.get("pair_schema_version") != "1"
            or not isinstance(mapping_payload, dict)
            or mapping_payload.get("mapping_schema_version") != "1"
            or not isinstance(mapping_payload.get("mapping"), dict)
        ):
            return _reject("malformed graph-pair or mapping artifact")
        if (
            not isinstance(certificate, dict)
            or certificate.get("certificate_type") != "graph.isomorphism_replay"
            or certificate.get("format_version") != "1"
            or certificate.get("bindings") != request.get("expected_bindings")
            or certificate.get("payload")
            != {
                "method": "DIRECT_ADJACENCY_REPLAY",
                "graph_pair_uri": pair_artifact["artifact_uri"],
                "mapping_uri": mapping_artifact["artifact_uri"],
            }
        ):
            return _reject("unexpected isomorphism certificate or bindings")
        left_vertices, left_edges = _graph(pair["left"])
        right_vertices, right_edges = _graph(pair["right"])
        mapping = mapping_payload["mapping"]
        well_formed = (
            set(mapping) == set(left_vertices)
            and all(isinstance(value, str) for value in mapping.values())
            and set(mapping.values()) == set(right_vertices)
            and len(mapping) == len(set(mapping.values()))
        )
        mapped_edges = (
            {
                tuple(sorted((mapping[left], mapping[right])))
                for left, right in left_edges
            }
            if well_formed
            else set()
        )
        isomorphic = well_formed and mapped_edges == right_edges
        return {
            "accepted": True,
            "conclusion": "TRUE" if isomorphic else "FALSE",
            "arithmetic": "EXACT_INTEGER",
            "method": "CHECKED_CERTIFICATE",
            "coverage": "EXHAUSTIVE",
            "relation_id": "graph.relation.isomorphic-via",
            "detail": (
                "the bijection preserves every edge and nonedge"
                if isomorphic
                else "the proposed mapping is not an adjacency-preserving bijection"
            ),
        }
    except (KeyError, TypeError, ValueError):
        return _reject("malformed graph-isomorphism verification request")
