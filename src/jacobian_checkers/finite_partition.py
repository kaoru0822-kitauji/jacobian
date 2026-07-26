"""Independent exact replay for finite enumerated partitions."""

from __future__ import annotations

from typing import Any


def _reject(detail: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "conclusion": "UNKNOWN",
        "arithmetic": "EXACT_INTEGER",
        "method": "EXHAUSTIVE_FINITE",
        "coverage": "EXHAUSTIVE",
        "detail": detail,
    }


def check_partition(request: dict[str, Any]) -> dict[str, Any]:
    """Recompute finite coverage and disjointness from bound artifacts."""

    try:
        if request.get("request_version") != "1":
            return _reject("unsupported request version")
        claim = request["claim"]["payload"]
        partition = request["candidate"]["payload"]
        scope = request["scope"]["payload"]
        certificate = request["certificate"]["payload"]
        if claim.get("predicate") != "finite_partition":
            return _reject("unsupported claim predicate")
        if certificate.get("certificate_type") != "finite.partition":
            return _reject("unexpected certificate type")
        if certificate.get("format_version") != "1":
            return _reject("unsupported certificate format")
        if certificate.get("bindings") != request["expected_bindings"]:
            return _reject("certificate bindings do not match request")
        certificate_payload = certificate.get("payload")
        claim_uri = request["claim"].get("artifact_uri")
        if (
            not isinstance(certificate_payload, dict)
            or certificate_payload.get("relation_id") != "case.relation.partitions"
            or certificate_payload.get("obligation_uri") != claim_uri
        ):
            return _reject("certificate relationship metadata is not bound")
        universe = scope.get("elements")
        cases = partition.get("cases")
        if (
            not isinstance(universe, list)
            or not all(isinstance(item, str) for item in universe)
            or len(universe) != len(set(universe))
            or not isinstance(cases, list)
        ):
            return _reject("scope or partition is malformed")
        universe_set = set(universe)
        seen_case_ids: set[str] = set()
        memberships: dict[str, str] = {}
        for case in cases:
            if not isinstance(case, dict) or set(case) != {"case_id", "members"}:
                return _reject("case is malformed")
            case_id = case["case_id"]
            members = case["members"]
            if (
                not isinstance(case_id, str)
                or not case_id
                or case_id in seen_case_ids
                or not isinstance(members, list)
                or not all(isinstance(member, str) for member in members)
                or len(members) != len(set(members))
            ):
                return _reject("case identifiers or members are malformed")
            seen_case_ids.add(case_id)
            for member in members:
                if member not in universe_set:
                    return _reject("partition contains an element outside the scope")
                if claim.get("require_disjoint", True) and member in memberships:
                    return _reject("partition cases overlap")
                memberships[member] = case_id
        if set(memberships) != universe_set:
            return _reject("partition does not cover the exact finite scope")
        return {
            "accepted": True,
            "conclusion": "TRUE",
            "arithmetic": "EXACT_INTEGER",
            "method": "EXHAUSTIVE_FINITE",
            "coverage": "EXHAUSTIVE",
            "detail": (
                f"replayed {len(cases)} cases over {len(universe)} exact elements"
            ),
            "relation_id": "case.relation.partitions",
            "relationship_source_artifact_uris": ([request["scope"]["artifact_uri"]]),
            "relationship_target_artifact_uris": (
                [request["candidate"]["artifact_uri"]]
            ),
            "obligation_uri": claim_uri,
        }
    except (KeyError, TypeError, ValueError):
        return _reject("malformed checker request")
