"""SymPy-backed exact operations for sparse rational polynomial maps."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Any, cast

import sympy
from pydantic import ValidationError
from sympy import QQ, Matrix, Poly, expand, symbols
from sympy.polys.polyerrors import PolynomialError

from jacobian.artifacts import ArtifactService
from jacobian.canonical import canonicalize_json
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityRelationship,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.evidence import (
    CertificateEnvelope,
    EvidenceBindings,
    WitnessEnvelope,
    WitnessRole,
)
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.polynomials import (
    PolynomialCollisionOutput,
    PolynomialCollisionPayload,
    PolynomialCollisionRequest,
    PolynomialCollisionSearchOutput,
    PolynomialCollisionSearchRequest,
    PolynomialEvaluationOutput,
    PolynomialEvaluationRequest,
    PolynomialInjectivityClaim,
    PolynomialJacobian,
    PolynomialJacobianClaim,
    PolynomialJacobianOutput,
    PolynomialJacobianReplayPayload,
    PolynomialJacobianRequest,
    PolynomialMapEvaluation,
    RationalPolynomialMap,
    RationalPolynomialPoint,
    RationalPolynomialTerm,
    SparseRationalPolynomial,
)
from jacobian.contracts.results import ContractModel, Execution, ExecutionStatus
from jacobian.provider_runtime import known_provider_runtime
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore, StoredArtifact, StoreError


@dataclass(frozen=True, slots=True)
class PolynomialInstallation:
    semantics_uri: str
    map_schema_uri: str
    evaluation_schema_uri: str
    jacobian_schema_uri: str
    claim_schema_uri: str
    jacobian_claim_schema_uri: str
    witness_schema_uri: str
    certificate_schema_uri: str
    collision_checker_id: str | None
    jacobian_checker_id: str | None


@dataclass(frozen=True, slots=True)
class PolynomialResources:
    store: ArtifactStore
    artifacts: ArtifactService
    installation: PolynomialInstallation


def install_polynomial_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
    checkers: CheckerRegistry,
    *,
    authorize_checker: bool,
) -> tuple[
    tuple[
        PolynomialMapEvaluationAdapter,
        PolynomialJacobianAdapter,
        PolynomialCollisionAdapter,
        PolynomialCollisionSearchAdapter,
    ],
    PolynomialInstallation,
]:
    """Register exact polynomial-map schemas, adapters, and optional checker."""

    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.rational-polynomial-map",
        version="1",
        definition={
            "description": (
                "square sparse polynomial maps over QQ with an explicit variable "
                "order and canonical reduced rational coefficients"
            ),
            "domain": "QQ",
            "map_shape": "square",
            "maximum_dimension": 4,
            "maximum_terms_per_coordinate": 1024,
            "maximum_exponent": 32,
            "maximum_derived_exponent": 127,
            "maximum_jacobian_product_term_estimate": 1024,
        },
    )
    map_schema_uri = schemas.register(
        name="jacobian.rational-polynomial-map",
        version="1",
        schema=model_schema(RationalPolynomialMap),
    )
    evaluation_schema_uri = schemas.register(
        name="jacobian.polynomial-map-evaluation",
        version="1",
        schema=model_schema(PolynomialMapEvaluation),
    )
    jacobian_schema_uri = schemas.register(
        name="jacobian.polynomial-jacobian",
        version="1",
        schema=model_schema(PolynomialJacobian),
    )
    claim_schema_uri = schemas.register(
        name="jacobian.polynomial-map-injectivity-claim",
        version="1",
        schema=model_schema(PolynomialInjectivityClaim),
    )
    jacobian_claim_schema_uri = schemas.register(
        name="jacobian.polynomial-jacobian-claim",
        version="1",
        schema=model_schema(PolynomialJacobianClaim),
    )
    witness_schema_uri = schemas.register(
        name="jacobian.witness-envelope",
        version="1",
        schema=model_schema(WitnessEnvelope),
    )
    certificate_schema_uri = schemas.register(
        name="jacobian.certificate-envelope",
        version="1",
        schema=model_schema(CertificateEnvelope),
    )
    collision_checker_id = None
    jacobian_checker_id = None
    if authorize_checker:
        collision_checker_id = checkers.authorize(
            name="exact rational polynomial-map collision checker",
            entrypoint="jacobian_checkers.polynomial_maps:check_collision",
            evidence_kind="WITNESS",
            format_id="polynomial.map_collision",
            format_version="1",
            claim_schema_uris=(claim_schema_uri,),
            semantics_uris=(semantics_uri,),
            candidate_schema_uris=(map_schema_uri,),
            reason="bundled polynomial-map reference checker",
        ).checker_id
        jacobian_checker_id = checkers.authorize(
            name="exact sparse polynomial Jacobian replay checker",
            entrypoint="jacobian_checkers.polynomial_maps:check_jacobian",
            evidence_kind="CERTIFICATE",
            format_id="polynomial.jacobian_replay",
            format_version="1",
            claim_schema_uris=(jacobian_claim_schema_uri,),
            semantics_uris=(semantics_uri,),
            candidate_schema_uris=(jacobian_schema_uri,),
            reason="bundled independent sparse-polynomial Jacobian checker",
        ).checker_id
    installation = PolynomialInstallation(
        semantics_uri=semantics_uri,
        map_schema_uri=map_schema_uri,
        evaluation_schema_uri=evaluation_schema_uri,
        jacobian_schema_uri=jacobian_schema_uri,
        claim_schema_uri=claim_schema_uri,
        jacobian_claim_schema_uri=jacobian_claim_schema_uri,
        witness_schema_uri=witness_schema_uri,
        certificate_schema_uri=certificate_schema_uri,
        collision_checker_id=collision_checker_id,
        jacobian_checker_id=jacobian_checker_id,
    )
    resources = PolynomialResources(
        store=store,
        artifacts=artifacts,
        installation=installation,
    )
    return (
        (
            PolynomialMapEvaluationAdapter(resources),
            PolynomialJacobianAdapter(resources),
            PolynomialCollisionAdapter(resources),
            PolynomialCollisionSearchAdapter(resources),
        ),
        installation,
    )


class PolynomialMapEvaluationAdapter:
    """Evaluate one exact rational polynomial map at one exact point."""

    def __init__(self, resources: PolynomialResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="polynomial.map.evaluate",
            version="1",
            title="Evaluate a rational polynomial map",
            description=(
                "Compute the exact rational image of one point under one sparse "
                "square polynomial map over QQ."
            ),
            provider="jacobian.sympy",
            provider_runtime=known_provider_runtime(
                "jacobian.sympy",
                features=("rational-polynomial-evaluation",),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(PolynomialEvaluationRequest),
            output_schema=model_schema(PolynomialEvaluationOutput),
            tags=("polynomial", "map", "evaluation", "exact-computation"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = _validate_request(
            PolynomialEvaluationRequest,
            request.input,
            code="INVALID_POLYNOMIAL_EVALUATION_REQUEST",
            operation="evaluation",
        )
        started = time.monotonic()
        polynomial_map = validated.map
        polynomial_map, map_uri = _materialize_map(self.resources, polynomial_map)
        point = RationalPolynomialPoint(values=validated.point)
        image = _evaluate(polynomial_map, point)
        evaluation, evaluation_uri = _materialize_evaluation(
            self.resources,
            map_uri=map_uri,
            point=point,
            image=image,
        )
        output = PolynomialEvaluationOutput(
            map_uri=map_uri,
            evaluation_uri=evaluation_uri,
            point=point.values,
            image=evaluation.image,
            backend_version=sympy.__version__,
        )
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="one exact point evaluation for one polynomial map",
                parameters={
                    "map_uri": map_uri,
                    "point": point.model_dump(mode="json")["values"],
                },
                artifact_uri=map_uri,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id="polynomial.relation.evaluation-of",
                    source_artifact_uris=(map_uri,),
                    target_artifact_uris=(evaluation_uri,),
                ),
            ),
            artifact_uris=(map_uri, evaluation_uri),
            completeness_basis="every coordinate was evaluated exactly at the point",
        )


class PolynomialJacobianAdapter:
    """Compute the exact Jacobian matrix and determinant of one square map."""

    def __init__(self, resources: PolynomialResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="polynomial.map.compute_jacobian",
            version="1",
            title="Compute a polynomial-map Jacobian",
            description=(
                "Compute the exact Jacobian matrix and determinant of one sparse "
                "square polynomial map over QQ."
            ),
            provider="jacobian.sympy",
            provider_runtime=known_provider_runtime(
                "jacobian.sympy",
                features=("symbolic-jacobian", "rational-polynomials"),
                checker_ids=(
                    (resources.installation.jacobian_checker_id,)
                    if resources.installation.jacobian_checker_id is not None
                    else ()
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(PolynomialJacobianRequest),
            output_schema=model_schema(PolynomialJacobianOutput),
            tags=("polynomial", "jacobian", "determinant", "exact-computation"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = _validate_request(
            PolynomialJacobianRequest,
            request.input,
            code="INVALID_POLYNOMIAL_JACOBIAN_REQUEST",
            operation="Jacobian computation",
        )
        started = time.monotonic()
        polynomial_map = validated.map
        polynomial_map, map_uri = _materialize_map(self.resources, polynomial_map)
        try:
            generators, coordinates = _sympy_map(polynomial_map)
            matrix_polys = tuple(
                tuple(coordinate.diff(generator) for generator in generators)
                for coordinate in coordinates
            )
            determinant = Poly(
                expand(
                    Matrix(
                        [[entry.as_expr() for entry in row] for row in matrix_polys]
                    ).det()
                ),
                *generators,
                domain=QQ,
            )
        except (PolynomialError, TypeError, ValueError) as exc:
            raise _polynomial_error(
                "POLYNOMIAL_JACOBIAN_FAILED",
                "jacobian_computation",
                "The exact polynomial Jacobian computation failed.",
            ) from exc
        matrix = tuple(
            tuple(_wire_polynomial(entry) for entry in row) for row in matrix_polys
        )
        jacobian = PolynomialJacobian(
            map_uri=map_uri,
            variable_order=polynomial_map.variables,
            matrix=matrix,
            determinant=_wire_polynomial(determinant),
            backend_version=sympy.__version__,
        )
        jacobian_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.installation.jacobian_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=jacobian.model_dump(mode="json"),
            parents=(map_uri,),
            summary="exact rational polynomial-map Jacobian",
        )
        claim = PolynomialJacobianClaim(source_map_uri=map_uri)
        claim_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.installation.jacobian_claim_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=claim.model_dump(mode="json"),
            parents=(map_uri, jacobian_artifact.artifact_uri),
            summary="exact polynomial Jacobian replay claim",
        )
        semantics = self.resources.store.get(self.resources.installation.semantics_uri)
        source_map = self.resources.store.get(map_uri)
        certificate_payload = PolynomialJacobianReplayPayload(
            source_map_uri=map_uri,
            jacobian_uri=jacobian_artifact.artifact_uri,
        ).model_dump(mode="json")
        certificate = CertificateEnvelope(
            certificate_type="polynomial.jacobian_replay",
            format_version="1",
            bindings=EvidenceBindings(
                claim_digest=claim_artifact.object_digest,
                semantics_digest=semantics.manifest.object_digest,
                candidate_digest=jacobian_artifact.object_digest,
                scope_digest=source_map.manifest.object_digest,
            ),
            payload_digest=(
                "sha256:"
                + hashlib.sha256(canonicalize_json(certificate_payload)).hexdigest()
            ),
            payload=certificate_payload,
        )
        certificate_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.installation.certificate_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=certificate.model_dump(mode="json"),
            parents=(
                claim_artifact.artifact_uri,
                jacobian_artifact.artifact_uri,
                map_uri,
            ),
            summary="unverified exact polynomial Jacobian replay certificate",
        )
        output = PolynomialJacobianOutput(
            map_uri=map_uri,
            jacobian_uri=jacobian_artifact.artifact_uri,
            claim_uri=claim_artifact.artifact_uri,
            certificate_uri=certificate_artifact.artifact_uri,
            checker_id=self.resources.installation.jacobian_checker_id,
            matrix=jacobian.matrix,
            determinant=jacobian.determinant,
            backend_version=sympy.__version__,
        )
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the full Jacobian matrix for one square polynomial map",
                parameters={
                    "map_uri": map_uri,
                    "variable_order": list(polynomial_map.variables),
                },
                artifact_uri=map_uri,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id="polynomial.relation.jacobian-of",
                    source_artifact_uris=(map_uri,),
                    target_artifact_uris=(jacobian_artifact.artifact_uri,),
                ),
            ),
            artifact_uris=(
                map_uri,
                jacobian_artifact.artifact_uri,
                claim_artifact.artifact_uri,
                certificate_artifact.artifact_uri,
            ),
            completeness_basis=(
                "every partial derivative and the exact determinant were computed"
            ),
        )


class PolynomialCollisionAdapter:
    """Compare exact evaluation artifacts and materialize collision evidence."""

    def __init__(self, resources: PolynomialResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="polynomial.map.collision_witness",
            version="1",
            title="Construct a polynomial-map collision witness",
            description=(
                "Compare the declared canonical rational values in two structurally "
                "compatible point-evaluation artifacts for the same polynomial map "
                "and materialize an unverified candidate collision witness."
            ),
            provider="jacobian.artifact-comparison",
            provider_runtime=known_provider_runtime(
                "jacobian.artifact-comparison",
                features=("polynomial-collision-witness",),
                checker_ids=(
                    (resources.installation.collision_checker_id,)
                    if resources.installation.collision_checker_id is not None
                    else ()
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(PolynomialCollisionRequest),
            output_schema=model_schema(PolynomialCollisionOutput),
            tags=("polynomial", "map", "collision", "witness", "artifact-composition"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = _validate_request(
            PolynomialCollisionRequest,
            request.input,
            code="INVALID_POLYNOMIAL_COLLISION_REQUEST",
            operation="collision construction",
        )
        started = time.monotonic()
        first_evaluation, first_evaluation_artifact = _load_evaluation(
            self.resources,
            validated.first_evaluation_uri,
            path="first_evaluation_uri",
        )
        second_evaluation, second_evaluation_artifact = _load_evaluation(
            self.resources,
            validated.second_evaluation_uri,
            path="second_evaluation_uri",
        )
        if first_evaluation.map_uri != second_evaluation.map_uri:
            raise _polynomial_error(
                "POLYNOMIAL_EVALUATION_MAP_MISMATCH",
                "collision_validation",
                "Collision evaluation artifacts must reference the same polynomial map.",
            )
        candidate_uri = first_evaluation.map_uri
        polynomial_map, candidate = _load_polynomial_map(
            self.resources,
            candidate_uri,
        )
        dimension = len(polynomial_map.variables)
        if any(
            len(evaluation.point.values) != dimension
            for evaluation in (first_evaluation, second_evaluation)
        ):
            raise _polynomial_error(
                "POLYNOMIAL_EVALUATION_DIMENSION_MISMATCH",
                "collision_validation",
                "Collision evaluation dimensions must match the polynomial map.",
            )
        first_point = first_evaluation.point
        second_point = second_evaluation.point
        first_image = first_evaluation.image
        second_image = second_evaluation.image
        claim = PolynomialInjectivityClaim(map_uri=candidate_uri)
        claim_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.installation.claim_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=claim.model_dump(mode="json"),
            parents=(candidate_uri,),
            summary="rational polynomial-map injectivity claim",
        )
        candidate_collision = (
            first_point.values != second_point.values and first_image == second_image
        )
        witness_uri = None
        if candidate_collision:
            # Evaluation payloads are candidate evidence. The independent checker,
            # not this comparison adapter, replays the map at both points.
            semantics = self.resources.store.get(
                self.resources.installation.semantics_uri
            )
            witness = WitnessEnvelope(
                witness_format="polynomial.map_collision",
                format_version="1",
                role=WitnessRole.REFUTES_CLAIM,
                bindings=EvidenceBindings(
                    claim_digest=claim_artifact.object_digest,
                    semantics_digest=semantics.manifest.object_digest,
                    candidate_digest=candidate.manifest.object_digest,
                ),
                payload=PolynomialCollisionPayload(
                    first_point=first_point.values,
                    second_point=second_point.values,
                    image=first_image,
                ).model_dump(mode="json"),
            )
            witness_artifact = self.resources.store.put(
                schema_uri=self.resources.installation.witness_schema_uri,
                semantics_uri=self.resources.installation.semantics_uri,
                payload=witness.model_dump(mode="json"),
                parents=(
                    claim_artifact.artifact_uri,
                    candidate_uri,
                    first_evaluation_artifact.artifact_uri,
                    second_evaluation_artifact.artifact_uri,
                ),
                summary="unverified rational polynomial-map collision witness",
            )
            witness_uri = witness_artifact.artifact_uri
        checker_id = self.resources.installation.collision_checker_id
        output = PolynomialCollisionOutput(
            claim_uri=claim_artifact.artifact_uri,
            candidate_uri=candidate_uri,
            first_evaluation_uri=first_evaluation_artifact.artifact_uri,
            second_evaluation_uri=second_evaluation_artifact.artifact_uri,
            first_point=first_point.values,
            second_point=second_point.values,
            first_image=first_image,
            second_image=second_image,
            candidate_collision=candidate_collision,
            witness_uri=witness_uri,
            checker_id=checker_id,
            certificate_available=witness_uri is not None and checker_id is not None,
        )
        artifact_uris = [
            candidate_uri,
            claim_artifact.artifact_uri,
            first_evaluation_artifact.artifact_uri,
            second_evaluation_artifact.artifact_uri,
        ]
        if witness_uri is not None:
            artifact_uris.append(witness_uri)
        relationships = [
            CapabilityRelationship(
                relation_id="polynomial.relation.evaluation-of",
                source_artifact_uris=(candidate_uri,),
                target_artifact_uris=(
                    first_evaluation_artifact.artifact_uri,
                    second_evaluation_artifact.artifact_uri,
                ),
            )
        ]
        if witness_uri is not None:
            relationships.append(
                CapabilityRelationship(
                    relation_id="polynomial.relation.collision-derived-from",
                    source_artifact_uris=(
                        first_evaluation_artifact.artifact_uri,
                        second_evaluation_artifact.artifact_uri,
                    ),
                    target_artifact_uris=(witness_uri,),
                )
            )
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description=(
                    "exact comparison of two point-evaluation artifacts for one "
                    "polynomial map"
                ),
                parameters={
                    "candidate_uri": candidate_uri,
                    "first_evaluation_uri": first_evaluation_artifact.artifact_uri,
                    "second_evaluation_uri": second_evaluation_artifact.artifact_uri,
                },
                artifact_uri=candidate_uri,
            ),
            relationships=tuple(relationships),
            artifact_uris=tuple(artifact_uris),
            completeness_basis=(
                "both supplied evaluation artifact payloads were structurally "
                "validated and their declared values were compared exactly"
            ),
            assurance_basis=(
                "deterministic structural comparison of canonical rational payloads; "
                "the source evaluations were not replayed and any candidate witness "
                "remains unverified"
            ),
        )


class PolynomialCollisionSearchAdapter:
    """Search one fully declared finite rational grid for a collision."""

    def __init__(self, resources: PolynomialResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="polynomial.map.collision.search",
            version="1",
            title="Search a bounded rational grid for a collision",
            description=(
                "Enumerate one deterministic finite rational grid and return its "
                "first exact polynomial-map collision with reconciled accounting."
            ),
            provider="jacobian.sympy",
            provider_runtime=known_provider_runtime(
                "jacobian.sympy",
                features=("bounded-rational-grid-search",),
                checker_ids=(
                    (resources.installation.collision_checker_id,)
                    if resources.installation.collision_checker_id is not None
                    else ()
                ),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(PolynomialCollisionSearchRequest),
            output_schema=model_schema(PolynomialCollisionSearchOutput),
            tags=("polynomial", "map", "collision", "bounded-search"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = _validate_request(
            PolynomialCollisionSearchRequest,
            request.input,
            code="INVALID_POLYNOMIAL_COLLISION_SEARCH_REQUEST",
            operation="collision search",
        )
        started = time.monotonic()
        polynomial_map, map_uri = _materialize_map(self.resources, validated.map)
        scalar_values = tuple(
            CanonicalRational(num=str(value.numerator), den=str(value.denominator))
            for value in sorted(
                {
                    Fraction(numerator, denominator)
                    for denominator in range(1, validated.max_denominator + 1)
                    for numerator in range(
                        -validated.max_abs_numerator,
                        validated.max_abs_numerator + 1,
                    )
                }
            )
        )
        points = tuple(product(scalar_values, repeat=len(polynomial_map.variables)))
        seen: dict[
            tuple[tuple[str, str], ...],
            tuple[tuple[CanonicalRational, ...], str],
        ] = {}
        found: (
            tuple[
                tuple[CanonicalRational, ...],
                tuple[CanonicalRational, ...],
                tuple[CanonicalRational, ...],
                str,
                str,
            ]
            | None
        ) = None
        examined = 0
        for point_values in points:
            examined += 1
            point = RationalPolynomialPoint(values=point_values)
            image = _evaluate(polynomial_map, point)
            _, evaluation_uri = _materialize_evaluation(
                self.resources,
                map_uri=map_uri,
                point=point,
                image=image,
            )
            key = tuple((value.num, value.den) for value in image)
            previous = seen.get(key)
            if previous is not None and previous[0] != point_values:
                found = (
                    previous[0],
                    point_values,
                    image,
                    previous[1],
                    evaluation_uri,
                )
                break
            seen[key] = (point_values, evaluation_uri)
        claim_uri: str | None = None
        witness_uri: str | None = None
        first_point_result: tuple[CanonicalRational, ...] | None = None
        second_point_result: tuple[CanonicalRational, ...] | None = None
        image_result: tuple[CanonicalRational, ...] | None = None
        first_evaluation_result: str | None = None
        second_evaluation_result: str | None = None
        if found is not None:
            (
                first_point_result,
                second_point_result,
                image_result,
                first_evaluation_result,
                second_evaluation_result,
            ) = found
            assert first_evaluation_result is not None
            assert second_evaluation_result is not None
            candidate = self.resources.store.get(map_uri)
            claim = self.resources.artifacts.put(
                schema_uri=self.resources.installation.claim_schema_uri,
                semantics_uri=self.resources.installation.semantics_uri,
                payload=PolynomialInjectivityClaim(map_uri=map_uri).model_dump(
                    mode="json"
                ),
                parents=(map_uri,),
                summary="rational polynomial-map injectivity claim",
            )
            semantics = self.resources.store.get(
                self.resources.installation.semantics_uri
            )
            witness = WitnessEnvelope(
                witness_format="polynomial.map_collision",
                format_version="1",
                role=WitnessRole.REFUTES_CLAIM,
                bindings=EvidenceBindings(
                    claim_digest=claim.object_digest,
                    semantics_digest=semantics.manifest.object_digest,
                    candidate_digest=candidate.manifest.object_digest,
                ),
                payload=PolynomialCollisionPayload(
                    first_point=first_point_result,
                    second_point=second_point_result,
                    image=image_result,
                ).model_dump(mode="json"),
            )
            witness_artifact = self.resources.artifacts.put(
                schema_uri=self.resources.installation.witness_schema_uri,
                semantics_uri=self.resources.installation.semantics_uri,
                payload=witness.model_dump(mode="json"),
                parents=(
                    claim.artifact_uri,
                    map_uri,
                    first_evaluation_result,
                    second_evaluation_result,
                ),
                summary="unverified bounded-search collision witness",
            )
            claim_uri = claim.artifact_uri
            witness_uri = witness_artifact.artifact_uri
        output = PolynomialCollisionSearchOutput(
            found=found is not None,
            map_uri=map_uri,
            examined_point_count=examined,
            grid_point_count=len(points),
            first_point=first_point_result,
            second_point=second_point_result,
            common_image=image_result,
            first_evaluation_uri=first_evaluation_result,
            second_evaluation_uri=second_evaluation_result,
            claim_uri=claim_uri,
            witness_uri=witness_uri,
            checker_id=self.resources.installation.collision_checker_id,
        )
        artifacts = [map_uri, *[uri for _, uri in seen.values()]]
        if found is not None:
            assert second_evaluation_result is not None
            assert claim_uri is not None
            assert witness_uri is not None
            artifacts.extend(
                [
                    second_evaluation_result,
                    claim_uri,
                    witness_uri,
                ]
            )
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="complete declared finite rational grid",
                parameters={
                    "max_abs_numerator": validated.max_abs_numerator,
                    "max_denominator": validated.max_denominator,
                    "grid_point_count": len(points),
                },
                artifact_uri=map_uri,
            ),
            relationships=(),
            artifact_uris=tuple(
                dict.fromkeys(uri for uri in artifacts if uri is not None)
            ),
            completeness_basis=(
                "the deterministic grid was fully enumerated"
                if found is None
                else "the canonical prefix through the first collision was enumerated"
            ),
            assurance_basis=(
                "deterministic exact SymPy search; any returned witness remains "
                "unverified until independent replay"
            ),
        )


def _materialize_map(
    resources: PolynomialResources,
    polynomial_map: RationalPolynomialMap,
) -> tuple[RationalPolynomialMap, str]:
    artifact = resources.artifacts.put(
        schema_uri=resources.installation.map_schema_uri,
        semantics_uri=resources.installation.semantics_uri,
        payload=polynomial_map.model_dump(mode="json"),
        summary="exact sparse rational polynomial map",
    )
    return polynomial_map, artifact.artifact_uri


def _load_evaluation(
    resources: PolynomialResources,
    evaluation_uri: str,
    *,
    path: str,
) -> tuple[PolynomialMapEvaluation, StoredArtifact]:
    try:
        artifact = resources.store.get(evaluation_uri)
    except StoreError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="POLYNOMIAL_EVALUATION_ARTIFACT_NOT_FOUND",
                stage="evaluation_resolution",
                message="The requested polynomial evaluation artifact is unavailable.",
                path=path,
                schema_uri=resources.installation.evaluation_schema_uri,
                hint="Use an evaluation URI returned by polynomial.map.evaluate.",
            )
        ) from exc
    if (
        artifact.manifest.schema_uri != resources.installation.evaluation_schema_uri
        or artifact.manifest.semantics_uri != resources.installation.semantics_uri
        or not isinstance(artifact.payload, dict)
    ):
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_POLYNOMIAL_EVALUATION_ARTIFACT",
                stage="evaluation_validation",
                message="The artifact is not a compatible polynomial-map evaluation.",
                path=path,
                schema_uri=resources.installation.evaluation_schema_uri,
                hint="Use an evaluation URI returned by polynomial.map.evaluate.",
            )
        )
    try:
        evaluation = PolynomialMapEvaluation.model_validate(artifact.payload)
    except ValidationError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_POLYNOMIAL_EVALUATION_ARTIFACT",
                stage="evaluation_validation",
                message="The polynomial-map evaluation artifact payload is malformed.",
                path=path,
                schema_uri=resources.installation.evaluation_schema_uri,
                hint="Recreate the artifact through polynomial.map.evaluate.",
            )
        ) from exc
    if evaluation.map_uri not in artifact.manifest.parents:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="MISBOUND_POLYNOMIAL_EVALUATION_ARTIFACT",
                stage="evaluation_validation",
                message="The evaluation artifact is not bound to its declared map.",
                path=path,
                schema_uri=resources.installation.evaluation_schema_uri,
                hint="Recreate the artifact through polynomial.map.evaluate.",
            )
        )
    return evaluation, artifact


def _load_polynomial_map(
    resources: PolynomialResources,
    map_uri: str,
) -> tuple[RationalPolynomialMap, StoredArtifact]:
    try:
        artifact = resources.store.get(map_uri)
    except StoreError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="POLYNOMIAL_MAP_ARTIFACT_NOT_FOUND",
                stage="map_resolution",
                message="The polynomial map referenced by an evaluation is unavailable.",
                path="evaluation.map_uri",
                schema_uri=resources.installation.map_schema_uri,
                hint="Recreate the evaluations through polynomial.map.evaluate.",
            )
        ) from exc
    if (
        artifact.manifest.schema_uri != resources.installation.map_schema_uri
        or artifact.manifest.semantics_uri != resources.installation.semantics_uri
        or not isinstance(artifact.payload, dict)
    ):
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_POLYNOMIAL_MAP_ARTIFACT",
                stage="map_validation",
                message="An evaluation references an incompatible polynomial map.",
                path="evaluation.map_uri",
                schema_uri=resources.installation.map_schema_uri,
                hint="Recreate the evaluations through polynomial.map.evaluate.",
            )
        )
    try:
        polynomial_map = RationalPolynomialMap.model_validate(artifact.payload)
    except ValidationError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INCOMPATIBLE_POLYNOMIAL_MAP_ARTIFACT",
                stage="map_validation",
                message="The referenced polynomial map artifact payload is malformed.",
                path="evaluation.map_uri",
                schema_uri=resources.installation.map_schema_uri,
                hint="Recreate the evaluations through polynomial.map.evaluate.",
            )
        ) from exc
    return polynomial_map, artifact


def _validate_request[RequestModel: ContractModel](
    model: type[RequestModel],
    payload: object,
    *,
    code: str,
    operation: str,
) -> RequestModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise _polynomial_error(
            code,
            "request_validation",
            f"The complete polynomial {operation} request is invalid.",
        ) from exc


def _sympy_map(
    polynomial_map: RationalPolynomialMap,
) -> tuple[tuple[Any, ...], tuple[Poly, ...]]:
    generators = cast(
        tuple[Any, ...],
        symbols(" ".join(polynomial_map.variables), seq=True),
    )
    coordinates = tuple(
        _sympy_polynomial(polynomial, generators)
        for polynomial in polynomial_map.coordinates
    )
    return generators, coordinates


def _sympy_polynomial(
    polynomial: SparseRationalPolynomial,
    generators: tuple[Any, ...],
) -> Poly:
    terms = {
        term.exponents: QQ(
            int(term.coefficient.num),
            int(term.coefficient.den),
        )
        for term in polynomial.terms
    }
    return Poly.from_dict(terms, generators, domain=QQ)


def _wire_polynomial(polynomial: Poly) -> SparseRationalPolynomial:
    return SparseRationalPolynomial(
        terms=tuple(
            RationalPolynomialTerm(
                coefficient=_wire_rational(coefficient),
                exponents=exponents,
            )
            for exponents, coefficient in polynomial.terms()
            if coefficient != 0
        )
    )


def _wire_rational(value: object) -> CanonicalRational:
    rational = sympy.Rational(value)
    return CanonicalRational(num=str(rational.p), den=str(rational.q))


def _evaluate(
    polynomial_map: RationalPolynomialMap,
    point: RationalPolynomialPoint,
) -> tuple[CanonicalRational, ...]:
    try:
        generators, coordinates = _sympy_map(polynomial_map)
        substitutions = {
            generator: QQ(
                int(value.num),
                int(value.den),
            )
            for generator, value in zip(
                generators,
                point.values,
                strict=True,
            )
        }
        return tuple(_wire_rational(poly.eval(substitutions)) for poly in coordinates)
    except (PolynomialError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise _polynomial_error(
            "POLYNOMIAL_EVALUATION_FAILED",
            "evaluation",
            "The exact polynomial-map evaluation failed.",
        ) from exc


def _materialize_evaluation(
    resources: PolynomialResources,
    *,
    map_uri: str,
    point: RationalPolynomialPoint,
    image: tuple[CanonicalRational, ...],
) -> tuple[PolynomialMapEvaluation, str]:
    evaluation = PolynomialMapEvaluation(
        map_uri=map_uri,
        point=point,
        image=image,
        backend_version=sympy.__version__,
    )
    artifact = resources.artifacts.put(
        schema_uri=resources.installation.evaluation_schema_uri,
        semantics_uri=resources.installation.semantics_uri,
        payload=evaluation.model_dump(mode="json"),
        parents=(map_uri,),
        summary="exact rational polynomial-map point evaluation",
    )
    return evaluation, artifact.artifact_uri


def _computed_result(
    *,
    descriptor: CapabilityDescriptor,
    request: CapabilityRequest,
    started: float,
    output: dict[str, Any],
    scope: CapabilityScope,
    relationships: tuple[CapabilityRelationship, ...],
    artifact_uris: tuple[str, ...],
    completeness_basis: str,
    assurance_basis: str = (
        "deterministic exact SymPy arithmetic over QQ; the computation did not "
        "authorize or invoke an independent checker"
    ),
) -> CapabilityResult:
    return CapabilityResult(
        capability_id=descriptor.capability_id,
        capability_version=descriptor.version,
        mode=request.mode,
        execution=Execution(
            status=ExecutionStatus.COMPLETED,
            runtime_ms=max(0, round((time.monotonic() - started) * 1000)),
        ),
        output=output,
        scope=scope,
        completeness=CapabilityCompleteness(
            status=CapabilityCompletenessStatus.COMPLETE,
            basis=(
                f"{completeness_basis}; no mathematical conclusion or independent "
                "verification is claimed"
            ),
            assurance_level=CapabilityAssuranceLevel.COMPUTED,
        ),
        relationships=relationships,
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.COMPUTED,
            basis=assurance_basis,
        ),
        artifact_uris=artifact_uris,
    )


def _polynomial_error(
    code: str,
    stage: str,
    message: str,
) -> CapabilityInvocationError:
    return CapabilityInvocationError(
        CapabilityDiagnostic(
            code=code,
            stage=stage,
            message=message,
            hint=(
                "Use the advertised sparse QQ schema with reduced rationals, "
                "descending monomial order, and matching dimensions."
            ),
        )
    )
