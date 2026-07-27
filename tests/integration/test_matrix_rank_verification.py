from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store_with_references")


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


@pytest.mark.integration
def test_matrix_rank_verify_independently_recomputes_rank(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.compute", input={"matrix": _matrix()}
        )
    )
    verified = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.verify",
            mode=CapabilityMode.VERIFY,
            input={"rank_uri": computed.output["rank_uri"]},
        )
    )
    assert verified.output["status"] == "VERIFIED_RANK"
    assert verified.output["conclusion"] == "TRUE"
    assert verified.assurance.level is CapabilityAssuranceLevel.VERIFIED


@pytest.mark.integration
def test_matrix_rank_verify_rejects_wrong_rank(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.compute", input={"matrix": _matrix()}
        )
    )
    source_uri = computed.output["matrix_uri"]
    wrong = kernel.artifacts.put(
        schema_uri=kernel.matrix.rank_schema_uri,
        semantics_uri=kernel.matrix.semantics_uri,
        payload={
            **kernel.store.get(computed.output["rank_uri"]).payload,
            "rank": 3,
            "pivot_columns": [0, 1, 2],
        },
        parents=(source_uri,),
        summary="deliberately incorrect rank candidate",
    )
    rejected = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.rank.verify",
            mode=CapabilityMode.VERIFY,
            input={"rank_uri": wrong.artifact_uri},
        )
    )
    assert rejected.output["status"] == "REJECTED"
    assert rejected.output["conclusion"] == "UNKNOWN"
    assert rejected.output["verification_record_uri"] is None
