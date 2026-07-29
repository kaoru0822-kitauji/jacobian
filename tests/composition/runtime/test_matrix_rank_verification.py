from __future__ import annotations

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)


def _matrix() -> dict[str, object]:
    def q(value: int) -> dict[str, str]:
        return {"num": str(value), "den": "1"}

    return {
        "entries": [
            [q(1), q(2), q(3)],
            [q(2), q(4), q(6)],
            [q(0), q(1), q(1)],
        ]
    }


def test_matrix_rank_verify_independently_recomputes_rank(
    authorized_complete_runtime,
) -> None:
    computed = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.compute", input={"matrix": _matrix()}
        )
    )
    verified = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.verify",
            mode=CapabilityMode.VERIFY,
            input={"rank_uri": computed.output["rank_uri"]},
        )
    )
    assert verified.output["status"] == "VERIFIED_RANK"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED


def test_matrix_rank_verify_rejects_wrong_rank(authorized_complete_runtime) -> None:
    computed = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.compute", input={"matrix": _matrix()}
        )
    )
    source_uri = computed.output["matrix_uri"]
    wrong = authorized_complete_runtime.core.artifacts.put(
        schema_uri=authorized_complete_runtime.portfolio.matrix.rank_schema_uri,
        semantics_uri=authorized_complete_runtime.portfolio.matrix.semantics_uri,
        payload={
            **authorized_complete_runtime.core.store.get(
                computed.output["rank_uri"]
            ).payload,
            "rank": 3,
            "pivot_columns": [0, 1, 2],
        },
        parents=(source_uri,),
        summary="deliberately incorrect rank candidate",
    )
    rejected = authorized_complete_runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.verify",
            mode=CapabilityMode.VERIFY,
            input={"rank_uri": wrong.artifact_uri},
        )
    )
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
