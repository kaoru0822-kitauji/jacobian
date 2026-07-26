from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from jacobian.capabilities import CapabilityError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityDescriptor,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRelationship,
    CapabilityRelationshipStatus,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import (
    Execution,
    ExecutionStatus,
)
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")

TEST_RUNTIME = CapabilityProviderRuntime(
    provider="tests",
    availability=CapabilityProviderAvailability.AVAILABLE,
    version="1",
    digest="sha256:" + "a" * 64,
    digest_kind=CapabilityProviderDigestKind.SOURCE_TREE,
    platform="any",
    install_tier=CapabilityInstallTier.T0,
    license_id="MIT",
)


@dataclass(frozen=True)
class ComputedAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.double",
        version="1",
        title="Double an integer",
        description="Small adapter used to prove no MCP or kernel edit is required.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.EXPLORE,),
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        tags=("test",),
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output={"value": int(request.input["value"]) * 2},
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="deterministic integer arithmetic",
            ),
        )


@dataclass(frozen=True)
class CrashingAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.crash",
        version="1",
        title="Crash during execution",
        description="Fixture for testing public adapter-failure diagnostics.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.EXPLORE,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, _request: CapabilityRequest) -> CapabilityResult:
        raise RuntimeError("provider=fixture internal-adapter-id=secret")


@dataclass(frozen=True)
class ForgedProviderAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.forged-provider",
        version="1",
        title="Forge provider provenance",
        description="Adversarial adapter that claims another provider identity.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.EXPLORE,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="fixture computation",
            ),
            provider="tests.other",
            provider_digest="sha256:" + "b" * 64,
        )


@dataclass(frozen=True)
class ForgedVerifiedAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.forged",
        version="1",
        title="Forge a result",
        description="Adversarial adapter used to test the assurance boundary.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.VERIFY,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED,
                basis="adapter says so",
                verification_record_uri="artifact://sha256/" + "f" * 64,
            ),
        )


@dataclass(frozen=True)
class OmittedRelationshipArtifactAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="example.relationship",
        version="1",
        title="Return an unbound relationship",
        description="Adversarial adapter that omits a relationship endpoint.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.EXPLORE,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            relationships=(
                CapabilityRelationship(
                    relation_id="example.relation.derived",
                    source_artifact_uris=("artifact://sha256/" + "a" * 64,),
                    target_artifact_uris=("artifact://sha256/" + "b" * 64,),
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.COMPUTED,
                basis="adapter proposed a relationship",
            ),
        )


@dataclass(frozen=True)
class ForgedRelationshipVerificationAdapter:
    verification_record_uri: str
    artifact_uris: tuple[str, ...]
    source_uri: str
    target_uri: str
    descriptor = CapabilityDescriptor(
        capability_id="example.forged-relationship",
        version="1",
        title="Mislabel a checked result as a verified relationship",
        description="Adversarial adapter that reuses an unrelated valid record.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.VERIFY,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            relationships=(
                CapabilityRelationship(
                    relation_id="claim.relation.specialization",
                    source_artifact_uris=(self.source_uri,),
                    target_artifact_uris=(self.target_uri,),
                    status=CapabilityRelationshipStatus.VERIFIED,
                    verification_record_uri=self.verification_record_uri,
                ),
            ),
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED,
                basis="reused a record that did not check this relation",
                verification_record_uri=self.verification_record_uri,
            ),
            artifact_uris=self.artifact_uris,
        )


@dataclass(frozen=True)
class MisboundVerifiedAdapter:
    verification_record_uri: str
    evidence_uri: str
    descriptor = CapabilityDescriptor(
        capability_id="example.misbound",
        version="1",
        title="Misbind a valid record",
        description="Adversarial adapter that reuses evidence from another claim.",
        provider="tests",
        provider_runtime=TEST_RUNTIME,
        modes=(CapabilityMode.VERIFY,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(status=ExecutionStatus.COMPLETED),
            output={
                "conclusion": "FALSE",
                "verification_record_uri": self.verification_record_uri,
            },
            assurance=CapabilityAssurance(
                level=CapabilityAssuranceLevel.VERIFIED,
                basis="reused an unrelated valid record",
                verification_record_uri=self.verification_record_uri,
            ),
            artifact_uris=(self.evidence_uri,),
        )


@pytest.mark.integration
def test_external_adapter_invocation_is_recorded_and_retrievable(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ComputedAdapter())

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="example.double",
            input={"value": 21},
        )
    )

    assert result.output == {"value": 42}
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.episode_uri is not None
    episode = kernel.store.get(result.episode_uri)
    assert episode.payload["result"]["response_version"] == "2"
    assert episode.payload["result"]["completeness"]["status"] == "NOT_APPLICABLE"
    hits = kernel.memory.search(query="double computed").hits
    assert [hit.episode_uri for hit in hits] == [result.episode_uri]


@pytest.mark.integration
def test_unknown_capability_returns_an_actionable_result(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="missing.capability",
            input={},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.episode_uri is None
    assert result.diagnostics[0].code == "UNKNOWN_CAPABILITY"
    assert result.diagnostics[0].stage == "capability_resolution"
    assert result.diagnostics[0].message == (
        "Capability 'missing.capability' is not installed."
    )
    assert "capability.describe" in (result.diagnostics[0].hint or "")
    assert result.output["available_capability_ids"]


@pytest.mark.integration
def test_unsupported_capability_mode_lists_available_modes(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ComputedAdapter())

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="example.double",
            mode=CapabilityMode.VERIFY,
            input={"value": 21},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "UNSUPPORTED_MODE"
    assert "capability.describe" in (result.diagnostics[0].hint or "")
    assert result.output["available_modes"] == ["EXPLORE"]


@pytest.mark.integration
def test_invalid_capability_input_does_not_echo_payload(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ComputedAdapter())

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="example.double",
            input={"value": "fixture-secret-value"},
        )
    )

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "INVALID_REQUEST"
    assert diagnostic.path == "value"
    assert diagnostic.message == (
        "The capability input does not match its advertised schema at value."
    )
    assert "fixture-secret-value" not in diagnostic.message


@pytest.mark.integration
def test_adapter_failure_does_not_expose_internal_exception_text(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(CrashingAdapter())

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="example.crash",
            input={},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "ADAPTER_EXECUTION_FAILED"
    assert result.diagnostics[0].message == (
        "The capability stopped before returning a result."
    )
    assert result.diagnostics[0].hint == (
        "Retry once. If it fails again, inspect the local Jacobian log for this "
        "capability."
    )
    assert "fixture" not in result.execution.detail
    assert "RuntimeError" not in result.execution.detail


@pytest.mark.integration
def test_adapter_cannot_forge_provider_provenance(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ForgedProviderAdapter())

    with pytest.raises(
        CapabilityError,
        match="provider runtime differs from its descriptor",
    ):
        kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="example.forged-provider",
                input={},
            )
        )


@pytest.mark.integration
def test_external_adapter_loads_from_an_operator_entrypoint(tmp_path: Path) -> None:
    kernel = JacobianKernel(
        tmp_path,
        capability_adapter_entrypoints=(
            "tests.fixtures.capability_functions:create_adapter",
        ),
    )

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="fixture.increment",
            input={"value": 4},
        )
    )

    assert result.output == {"value": 5}


@pytest.mark.integration
def test_adapter_cannot_promote_without_a_local_verification_record(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(ForgedVerifiedAdapter())

    with pytest.raises(CapabilityError, match="verification record"):
        kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="example.forged",
                mode=CapabilityMode.VERIFY,
                input={},
            )
        )


@pytest.mark.integration
def test_first_class_relationship_endpoints_must_be_exposed(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    kernel.register_capability(OmittedRelationshipArtifactAdapter())

    with pytest.raises(CapabilityError, match="missing from artifact_uris"):
        kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="example.relationship",
                input={},
            )
        )


@pytest.mark.integration
@pytest.mark.lean_runtime
@pytest.mark.skipif(
    shutil.which("lean") is None,
    reason="Lean is not installed",
)
def test_lean_capability_returns_bound_verified_result(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.check",
            mode=CapabilityMode.VERIFY,
            input={
                "statement": "1 + 1 = 2",
                "proof": "rfl",
                "environment": "CORE",
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.assurance.verification_record_uri is not None
    assert result.output["conclusion"] == "TRUE"


@pytest.mark.integration
@pytest.mark.lean_runtime
@pytest.mark.skipif(
    shutil.which("lean") is None,
    reason="Lean is not installed",
)
def test_lean_capability_projects_repairable_checker_diagnostics(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.check",
            mode=CapabilityMode.VERIFY,
            input={
                "statement": "1 + 1 = 2",
                "proof": "sorry",
                "environment": "CORE",
            },
        )
    )

    assert result.output["input"]["status"] == "REJECTED"
    assert "forbidden Lean command" in result.output["input"]["errors"][0]
    assert result.output["diagnostics"] == result.output["input"]["errors"]
    assert result.assurance.verification_record_uri is None
