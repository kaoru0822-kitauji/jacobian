"""Exact rational determinant and rank capability adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from pydantic import ValidationError

from jacobian.artifacts import ArtifactService
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
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.matrices import (
    ExactRationalMatrix,
    MatrixDeterminantArtifact,
    MatrixDeterminantOutput,
    MatrixDeterminantRequest,
    MatrixRankArtifact,
    MatrixRankOutput,
    MatrixRankRequest,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.provider_runtime import known_provider_runtime
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore


@dataclass(frozen=True, slots=True)
class MatrixInstallation:
    semantics_uri: str
    matrix_schema_uri: str
    determinant_schema_uri: str
    rank_schema_uri: str


@dataclass(frozen=True, slots=True)
class MatrixResources:
    artifacts: ArtifactService
    installation: MatrixInstallation


def install_matrix_capabilities(
    store: ArtifactStore,
    schemas: SchemaRegistry,
    artifacts: ArtifactService,
) -> tuple[
    tuple[MatrixDeterminantAdapter, MatrixRankAdapter],
    MatrixInstallation,
]:
    """Register exact QQ matrix contracts and computation adapters."""

    semantics_uri = store.register_descriptor(
        kind="semantics",
        name="jacobian.exact-rational-matrix",
        version="1",
        definition={
            "description": (
                "rectangular matrices over QQ with canonical reduced rational entries"
            ),
            "domain": "QQ",
            "maximum_rows": 32,
            "maximum_columns": 32,
        },
    )
    installation = MatrixInstallation(
        semantics_uri=semantics_uri,
        matrix_schema_uri=schemas.register(
            name="jacobian.exact-rational-matrix",
            version="1",
            schema=model_schema(ExactRationalMatrix),
        ),
        determinant_schema_uri=schemas.register(
            name="jacobian.matrix-determinant",
            version="1",
            schema=model_schema(MatrixDeterminantArtifact),
        ),
        rank_schema_uri=schemas.register(
            name="jacobian.matrix-rank",
            version="1",
            schema=model_schema(MatrixRankArtifact),
        ),
    )
    resources = MatrixResources(artifacts=artifacts, installation=installation)
    return (
        (MatrixDeterminantAdapter(resources), MatrixRankAdapter(resources)),
        installation,
    )


class MatrixDeterminantAdapter:
    """Compute one exact determinant without claiming verification."""

    def __init__(self, resources: MatrixResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="matrix.determinant.compute",
            version="1",
            title="Compute an exact rational matrix determinant",
            description=(
                "Compute the determinant of one square matrix over QQ using "
                "fraction-free Bareiss elimination."
            ),
            provider="jacobian.python",
            provider_runtime=known_provider_runtime(
                "jacobian.python",
                features=("matrix", "determinant", "exact-rational"),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(MatrixDeterminantRequest),
            output_schema=model_schema(MatrixDeterminantOutput),
            tags=("matrix", "determinant", "exact-computation"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = _validate(MatrixDeterminantRequest, request.input)
        started = time.monotonic()
        matrix_uri = _materialize_matrix(self.resources, validated.matrix)
        determinant = _bareiss_determinant(_fractions(validated.matrix))
        determinant_value = _wire(determinant)
        artifact = MatrixDeterminantArtifact(
            matrix_uri=matrix_uri,
            determinant=determinant_value,
        )
        result_uri = self.resources.artifacts.put(
            schema_uri=self.resources.installation.determinant_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=artifact.model_dump(mode="json"),
            parents=(matrix_uri,),
            summary="exact rational matrix determinant",
        ).artifact_uri
        output = MatrixDeterminantOutput(
            matrix_uri=matrix_uri,
            determinant_uri=result_uri,
            determinant=determinant_value,
        )
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope_description="one square exact rational matrix",
            matrix_uri=matrix_uri,
            result_uri=result_uri,
            relation_id="matrix.relation.determinant-of",
            basis="fraction-free Bareiss elimination completed for the full matrix",
        )


class MatrixRankAdapter:
    """Compute one exact rank and expose its pivot columns."""

    def __init__(self, resources: MatrixResources) -> None:
        self.resources = resources
        self._descriptor = CapabilityDescriptor(
            capability_id="matrix.rank.compute",
            version="1",
            title="Compute exact rational matrix rank",
            description=(
                "Compute the rank and pivot columns of one rectangular matrix over QQ."
            ),
            provider="jacobian.python",
            provider_runtime=known_provider_runtime(
                "jacobian.python",
                features=("matrix", "rank", "exact-rational"),
            ),
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(MatrixRankRequest),
            output_schema=model_schema(MatrixRankOutput),
            tags=("matrix", "rank", "exact-computation"),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        validated = _validate(MatrixRankRequest, request.input)
        started = time.monotonic()
        matrix_uri = _materialize_matrix(self.resources, validated.matrix)
        pivot_columns = _rank_pivots(_fractions(validated.matrix))
        artifact = MatrixRankArtifact(
            matrix_uri=matrix_uri,
            rank=len(pivot_columns),
            pivot_columns=pivot_columns,
        )
        result_uri = self.resources.artifacts.put(
            schema_uri=self.resources.installation.rank_schema_uri,
            semantics_uri=self.resources.installation.semantics_uri,
            payload=artifact.model_dump(mode="json"),
            parents=(matrix_uri,),
            summary="exact rational matrix rank",
        ).artifact_uri
        output = MatrixRankOutput(
            matrix_uri=matrix_uri,
            rank_uri=result_uri,
            rank=len(pivot_columns),
            pivot_columns=pivot_columns,
        )
        return _computed_result(
            descriptor=self.descriptor,
            request=request,
            started=started,
            output=output.model_dump(mode="json"),
            scope_description="one rectangular exact rational matrix",
            matrix_uri=matrix_uri,
            result_uri=result_uri,
            relation_id="matrix.relation.rank-of",
            basis="exact rational row reduction completed for the full matrix",
        )


def _validate(model: Any, payload: dict[str, Any]) -> Any:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise CapabilityInvocationError(
            CapabilityDiagnostic(
                code="INVALID_EXACT_MATRIX_REQUEST",
                stage="matrix_input_validation",
                message="The matrix does not satisfy the advertised exact QQ contract.",
                hint=(
                    "Use a nonempty rectangular matrix of canonical reduced "
                    "rationals; determinant inputs must be square."
                ),
            )
        ) from exc


def _materialize_matrix(
    resources: MatrixResources,
    matrix: ExactRationalMatrix,
) -> str:
    return resources.artifacts.put(
        schema_uri=resources.installation.matrix_schema_uri,
        semantics_uri=resources.installation.semantics_uri,
        payload=matrix.model_dump(mode="json"),
        summary="exact rational matrix",
    ).artifact_uri


def _fractions(matrix: ExactRationalMatrix) -> list[list[Fraction]]:
    return [[entry.as_fraction() for entry in row] for row in matrix.entries]


def _wire(value: Fraction) -> CanonicalRational:
    return CanonicalRational(num=str(value.numerator), den=str(value.denominator))


def _bareiss_determinant(matrix: list[list[Fraction]]) -> Fraction:
    size = len(matrix)
    if size == 1:
        return matrix[0][0]
    denominators = [value.denominator for row in matrix for value in row]
    scale = 1
    for denominator in denominators:
        scale = _lcm(scale, denominator)
    work = [[int(value * scale) for value in row] for row in matrix]
    sign = 1
    previous = 1
    for column in range(size - 1):
        pivot = next(
            (row for row in range(column, size) if work[row][column] != 0),
            None,
        )
        if pivot is None:
            return Fraction(0)
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            sign = -sign
        pivot_value = work[column][column]
        for row in range(column + 1, size):
            for target_column in range(column + 1, size):
                numerator = (
                    work[row][target_column] * pivot_value
                    - work[row][column] * work[column][target_column]
                )
                work[row][target_column] = numerator // previous
            work[row][column] = 0
        previous = pivot_value
    return Fraction(sign * work[-1][-1], scale**size)


def _rank_pivots(matrix: list[list[Fraction]]) -> tuple[int, ...]:
    row_count = len(matrix)
    column_count = len(matrix[0])
    pivot_row = 0
    pivots: list[int] = []
    for column in range(column_count):
        selected = next(
            (row for row in range(pivot_row, row_count) if matrix[row][column] != 0),
            None,
        )
        if selected is None:
            continue
        matrix[pivot_row], matrix[selected] = matrix[selected], matrix[pivot_row]
        pivot = matrix[pivot_row][column]
        matrix[pivot_row] = [value / pivot for value in matrix[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or matrix[row][column] == 0:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(
                    matrix[row],
                    matrix[pivot_row],
                    strict=True,
                )
            ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break
    return tuple(pivots)


def _gcd(left: int, right: int) -> int:
    while right:
        left, right = right, left % right
    return abs(left)


def _lcm(left: int, right: int) -> int:
    return abs(left * right) // _gcd(left, right)


def _computed_result(
    *,
    descriptor: CapabilityDescriptor,
    request: CapabilityRequest,
    started: float,
    output: dict[str, Any],
    scope_description: str,
    matrix_uri: str,
    result_uri: str,
    relation_id: str,
    basis: str,
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
        scope=CapabilityScope(
            description=scope_description,
            parameters={"matrix_uri": matrix_uri},
            artifact_uri=matrix_uri,
        ),
        completeness=CapabilityCompleteness(
            status=CapabilityCompletenessStatus.COMPLETE,
            basis=f"{basis}; this is not independent verification",
            assurance_level=CapabilityAssuranceLevel.COMPUTED,
        ),
        relationships=(
            CapabilityRelationship(
                relation_id=relation_id,
                source_artifact_uris=(matrix_uri,),
                target_artifact_uris=(result_uri,),
            ),
        ),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.COMPUTED,
            basis=(
                "deterministic exact rational arithmetic; no independent checker "
                "was invoked"
            ),
        ),
        artifact_uris=(matrix_uri, result_uri),
    )
