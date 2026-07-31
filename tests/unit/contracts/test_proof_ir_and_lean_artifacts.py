from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.lean_artifacts import (
    LeanEnvironmentIdentity,
    LeanProofEdit,
    LeanProofState,
)
from jacobian.contracts.proof_ir import (
    AtomicClaimRef,
    ConjunctionClaim,
    ImplicationClaim,
    ProofObligationSet,
)
from jacobian.contracts.results import ExecutionStatus


def _ref(index: str) -> AtomicClaimRef:
    return AtomicClaimRef(
        claim_artifact_uri=f"artifact://sha256/{index * 64}",
        schema_digest=f"sha256/{index * 64}".replace("sha256/", "sha256:"),
        semantics_digest=f"sha256/{index * 64}".replace("sha256/", "sha256:"),
    )


def test_bounded_claim_ir_preserves_order_and_direction() -> None:
    first = _ref("a")
    second = _ref("b")

    assert ConjunctionClaim(claim_refs=(first, second)).claim_refs == (first, second)
    assert ImplicationClaim(premises=(first,), conclusion=second).conclusion == second
    with pytest.raises(ValidationError):
        ProofObligationSet(
            source_logical_claim=first,
            obligation_refs=(second, second),
            decomposition_semantics=first.semantics_digest,
            completeness_status="COMPLETE",
        )


def test_lean_artifacts_bind_state_to_environment_identity() -> None:
    environment = LeanEnvironmentIdentity(
        lean_toolchain_version="4.31.0",
        project_source_digest="sha256:" + "a" * 64,
        provider_runtime_digest="sha256:" + "b" * 64,
    )
    state = LeanProofState(
        source_artifact_uri="artifact://sha256/" + "c" * 64,
        declaration_or_command_position=3,
        typed_goals=(),
        local_hypotheses=(),
        metavariable_identifiers=(),
        dependency_references=(),
        environment_identity=environment,
    )
    edit = LeanProofEdit(
        before_state_uri=state.source_artifact_uri,
        requested_edit="rfl",
        diagnostics=(),
        execution_status=ExecutionStatus.ERROR,
        environment_identity=environment,
    )

    assert edit.before_state_uri == state.source_artifact_uri
