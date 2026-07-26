"""SymPy-backed exact operations for sparse rational polynomial maps."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
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
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore


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
        schema=RationalPolynomialMap.model_json_schema(),
    )
    evaluation_schema_uri = schemas.register(
        name="jacobian.polynomial-map-evaluation",
        version="1",
        schema=PolynomialMapEvaluation.model_json_schema(),
    )
    jacobian_schema_uri = schemas.register(
        name="jacobian.polynomial-jacobian",
        version="1",
        schema=PolynomialJacobian.model_json_schema(),
    )
    claim_schema_uri = schemas.register(
        name="jacobian.polynomial-map-injectivity-claim",
        version="1",
        schema=PolynomialInjectivityClaim.model_json_schema(),
    )
    jacobian_claim_schema_uri = schemas.register(
        name="jacobian.polynomial-jacobian-claim",
        version="1",
        schema=PolynomialJacobianClaim.model_json_schema(),
    )
    witness_schema_uri = schemas.register(
        name="jacobian.witness-envelope",
        version="1",
        schema=WitnessEnvelope.model_json_schema(),
    )
    certificate_schema_uri = schemas.register(
        name="jacobian.certificate-envelope",
        version="1",
        schema=CertificateEnvelope.model_json_schema(),
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
            modes=(CapabilityMode.EXPLORE,),
            input_schema=PolynomialEvaluationRequest.model_json_schema(),
            output_schema=PolynomialEvaluationOutput.model_json_schema(),
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
            modes=(CapabilityMode.EXPLORE,),
            input_schema=PolynomialJacobianRequest.model_json_schema(),
            output_schema=PolynomialJacobianOutput.model_json_schema(),
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
    """Materialize exact collision evidence without certifying injectivity."""

    def __init__(self, resources: PolynomialResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="polynomial.map.collision_witness",
            version="1",
            title="Construct a polynomial-map collision witness",
            description=(
                "Evaluate two exact rational points and materialize a bound collision "
                "witness when their images agree and the points are distinct."
            ),
            provider="jacobian.sympy",
            modes=(CapabilityMode.EXPLORE,),
            input_schema=PolynomialCollisionRequest.model_json_schema(),
            output_schema=PolynomialCollisionOutput.model_json_schema(),
            tags=("polynomial", "map", "collision", "witness"),
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
        polynomial_map = validated.map
        polynomial_map, candidate_uri = _materialize_map(self.resources, polynomial_map)
        first_point = RationalPolynomialPoint(values=validated.first_point)
        second_point = RationalPolynomialPoint(values=validated.second_point)
        first_image = _evaluate(polynomial_map, first_point)
        second_image = _evaluate(polynomial_map, second_point)
        _, first_evaluation_uri = _materialize_evaluation(
            self.resources,
            map_uri=candidate_uri,
            point=first_point,
            image=first_image,
        )
        _, second_evaluation_uri = _materialize_evaluation(
            self.resources,
            map_uri=candidate_uri,
            point=second_point,
            image=second_image,
        )
        claim = PolynomialInjectivityClaim(map_uri=candidate_uri)
        claim_artifact = self.resources.artifacts.put(
            schema_uri=self.resources.installation.claim_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=claim.model_dump(mode="json"),
            parents=(candidate_uri,),
            summary="rational polynomial-map injectivity claim",
        )
        is_collision = (
            first_point.values != second_point.values and first_image == second_image
        )
        witness_uri = None
        if is_collision:
            semantics = self.resources.store.get(
                self.resources.installation.semantics_uri
            )
            candidate = self.resources.store.get(candidate_uri)
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
                parents=(claim_artifact.artifact_uri, candidate_uri),
                summary="unverified rational polynomial-map collision witness",
            )
            witness_uri = witness_artifact.artifact_uri
        checker_id = self.resources.installation.collision_checker_id
        output = PolynomialCollisionOutput(
            claim_uri=claim_artifact.artifact_uri,
            candidate_uri=candidate_uri,
            first_evaluation_uri=first_evaluation_uri,
            second_evaluation_uri=second_evaluation_uri,
            first_point=first_point.values,
            second_point=second_point.values,
            first_image=first_image,
            second_image=second_image,
            is_collision=is_collision,
            witness_uri=witness_uri,
            checker_id=checker_id,
            certificate_available=witness_uri is not None and checker_id is not None,
            backend_version=sympy.__version__,
        )
        artifact_uris = [
            candidate_uri,
            claim_artifact.artifact_uri,
            first_evaluation_uri,
            second_evaluation_uri,
        ]
        if witness_uri is not None:
            artifact_uris.append(witness_uri)
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="two exact point evaluations for one polynomial map",
                parameters={
                    "candidate_uri": candidate_uri,
                    "first_point": first_point.model_dump(mode="json")["values"],
                    "second_point": second_point.model_dump(mode="json")["values"],
                },
                artifact_uri=candidate_uri,
            ),
            relationships=(
                CapabilityRelationship(
                    relation_id="polynomial.relation.evaluation-of",
                    source_artifact_uris=(candidate_uri,),
                    target_artifact_uris=(
                        first_evaluation_uri,
                        second_evaluation_uri,
                    ),
                ),
            ),
            artifact_uris=tuple(artifact_uris),
            completeness_basis="both requested points were evaluated exactly",
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
            basis=(
                "deterministic exact SymPy arithmetic over QQ; the computation did "
                "not authorize or invoke an independent checker"
            ),
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
