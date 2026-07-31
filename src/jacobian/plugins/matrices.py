"""Search-side integer-matrix reference plugin.

Implements the v0.2 matrix reference scenarios:
- MAT-KERNEL-001: the 2x2 matrix [[2,4],[1,2]] is singular.
- MAT-MAXDET3-001: maximize |det A| over 3x3 matrices with entries in {-1,1}.

All outputs are unverified search results; checkers replay evidence separately.
"""

from __future__ import annotations

import itertools
import re
import time
from collections.abc import Iterator
from copy import deepcopy
from fractions import Fraction
from typing import Any, cast

from pydantic import ValidationError

from jacobian.contracts.plugin_inputs import (
    MatrixCapabilityRequest,
    MatrixEnumerationRequest,
    MatrixEvaluationRequest,
    MatrixMaterializeRequest,
    MatrixReductionRequest,
    MatrixTransformRequest,
)

MAX_SEARCHED_MATRICES = 65_536

# ---------------------------------------------------------------------------
# Canonical helpers
# ---------------------------------------------------------------------------


_INTEGER_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)$")


def _is_exact_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return bool(_INTEGER_RE.match(value))
    return False


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an exact integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not _INTEGER_RE.match(value):
            raise ValueError(f"not an exact integer: {value!r}")
        return int(value)
    raise ValueError(f"not an exact integer: {value!r}")


def _to_int_matrix(entries: Any) -> list[list[int]]:
    if not isinstance(entries, list):
        raise ValueError("entries must be a list of rows")
    matrix: list[list[int]] = []
    for row in entries:
        if not isinstance(row, list):
            raise ValueError("each row must be a list")
        matrix.append([_to_int(x) for x in row])
    return matrix


def _canonical_rational(frac: Fraction) -> dict[str, str]:
    return {"num": str(frac.numerator), "den": str(frac.denominator)}


def enumerate_candidates_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Page through a finite rectangular integer-matrix scope."""

    try:
        selected = MatrixEnumerationRequest.model_validate(request)
    except ValidationError as exc:
        raise ValueError(
            "matrix enumeration request does not match its contract"
        ) from exc
    bounds = selected.bounds.model_dump(mode="json")
    page_size = selected.page_size
    offset = selected.cursor.offset if selected.cursor is not None else 0
    errors = _validate_scope(bounds)
    if errors:
        raise ValueError("; ".join(errors))

    rows = cast(int, bounds["rows"])
    cols = cast(int, bounds["cols"])
    values = [_to_int(value) for value in cast(list[Any], bounds["entries"])]
    total = len(values) ** (rows * cols)
    stop = min(offset + page_size, total)
    candidates: list[dict[str, Any]] = []
    for flat_index in range(offset, stop):
        index = flat_index
        flat: list[str] = []
        for _ in range(rows * cols):
            flat.append(str(values[index % len(values)]))
            index //= len(values)
        entries = [flat[row * cols : (row + 1) * cols] for row in range(rows)]
        candidates.append({"rows": rows, "cols": cols, "entries": entries})

    complete = stop >= total
    return {
        "response_version": "1",
        "candidates": candidates,
        "next_cursor": None if complete else {"offset": stop},
        "complete": complete,
        "scope": {
            "rows": rows,
            "cols": cols,
            "entries": [str(value) for value in values],
            "labeled": True,
            "candidate_count": total,
        },
    }


def transform_row_major_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Propose a row-major representation of one integer matrix."""

    try:
        selected = MatrixTransformRequest.model_validate(request)
    except ValidationError as exc:
        raise ValueError(
            "matrix transform request does not match its contract"
        ) from exc
    source = selected.source.model_dump(mode="json")
    errors = validate_candidate(source)
    if errors:
        raise ValueError("; ".join(errors))
    rows = cast(int, source["rows"])
    cols = cast(int, source["cols"])
    values = [
        str(_to_int(value))
        for row in cast(list[list[Any]], source["entries"])
        for value in row
    ]
    return {
        "response_version": "1",
        "transform_format": "matrix.row_major",
        "format_version": "1",
        "relation": "EQUIVALENT",
        "target_payload": {
            "rows": rows,
            "cols": cols,
            "values": values,
        },
        "obligation": {
            "kind": "row_major_bijection",
            "source_entry_count": rows * cols,
            "target_value_count": len(values),
        },
        "detail": "flattened entries in row-major order",
    }


# ---------------------------------------------------------------------------
# Exact linear algebra
# ---------------------------------------------------------------------------


def _det_fraction(matrix: list[list[int]]) -> Fraction:
    """Exact determinant using Fraction Gaussian elimination."""
    n = len(matrix)
    if n == 0:
        return Fraction(1)
    a = [[Fraction(x) for x in row] for row in matrix]
    det = Fraction(1)
    row = 0
    for col in range(n):
        pivot = None
        for r in range(row, n):
            if a[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            return Fraction(0)
        if pivot != row:
            a[pivot], a[row] = a[row], a[pivot]
            det = -det
        piv = a[row][col]
        det *= piv
        for r in range(row + 1, n):
            if a[r][col] == 0:
                continue
            factor = a[r][col] / piv
            for c in range(col, n):
                a[r][c] -= factor * a[row][c]
        row += 1
    return det


def _kernel_vector(matrix: list[list[int]]) -> list[Fraction] | None:
    """Return a non-zero rational vector in the kernel, or None if trivial."""
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    a = [[Fraction(x) for x in row] for row in matrix]
    pivot_cols: list[int] = []
    pivot_rows: list[int] = []
    r = 0
    for c in range(cols):
        pivot = None
        for i in range(r, rows):
            if a[i][c] != 0:
                pivot = i
                break
        if pivot is None:
            continue
        a[pivot], a[r] = a[r], a[pivot]
        pivot_cols.append(c)
        pivot_rows.append(r)
        for i in range(r + 1, rows):
            if a[i][c] == 0:
                continue
            factor = a[i][c] / a[r][c]
            for j in range(c, cols):
                a[i][j] -= factor * a[r][j]
        r += 1

    if len(pivot_cols) == cols:
        return None

    free_cols = [c for c in range(cols) if c not in pivot_cols]
    sol = [Fraction(0) for _ in range(cols)]
    sol[free_cols[0]] = Fraction(1)

    for r_idx, c_idx in reversed(list(zip(pivot_rows, pivot_cols, strict=True))):
        total = Fraction(0)
        for j in range(c_idx + 1, cols):
            total += a[r_idx][j] * sol[j]
        sol[c_idx] = -total / a[r_idx][c_idx]

    return sol


def _is_singular(matrix: list[list[int]]) -> bool:
    return _det_fraction(matrix) == 0


# ---------------------------------------------------------------------------
# Scope enumeration
# ---------------------------------------------------------------------------


def _validate_scope(scope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = scope.get("rows")
    cols = scope.get("cols")
    entries = scope.get("entries")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
        errors.append("scope.rows must be a positive integer")
    if not isinstance(cols, int) or isinstance(cols, bool) or cols <= 0:
        errors.append("scope.cols must be a positive integer")
    if not isinstance(entries, list) or not entries:
        errors.append("scope.entries must be a non-empty list of allowed integers")
    else:
        for e in entries:
            if not _is_exact_integer(e):
                errors.append(f"scope entry {e!r} is not an exact integer")
                break
    return errors


def _scope_iterator(
    scope: dict[str, Any],
) -> Iterator[tuple[int, list[list[int]]]]:
    rows = cast(int, scope["rows"])
    cols = cast(int, scope["cols"])
    values = [_to_int(e) for e in scope["entries"]]
    positions = rows * cols
    for index, combo in enumerate(itertools.product(values, repeat=positions)):
        mat = [list(combo[i * cols : (i + 1) * cols]) for i in range(rows)]
        yield index, mat


def _scope_total(scope: dict[str, Any]) -> int:
    values = [_to_int(e) for e in scope["entries"]]
    rows = cast(int, scope["rows"])
    cols = cast(int, scope["cols"])
    return cast(int, len(values) ** (rows * cols))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_candidate(payload: dict[str, Any]) -> list[str]:
    """Return a list of validation errors for a matrix candidate payload."""
    errors: list[str] = []
    rows = payload.get("rows")
    cols = payload.get("cols")
    entries = payload.get("entries")

    if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
        errors.append("rows must be a positive integer")
    if not isinstance(cols, int) or isinstance(cols, bool) or cols <= 0:
        errors.append("cols must be a positive integer")
    if not isinstance(entries, list):
        errors.append("entries must be a list of rows")
        return errors

    if rows is not None and len(entries) != rows:
        errors.append(f"entries has {len(entries)} rows, expected {rows}")

    for i, row in enumerate(entries):
        if not isinstance(row, list):
            errors.append(f"row {i} is not a list")
            continue
        if cols is not None and len(row) != cols:
            errors.append(f"row {i} has {len(row)} columns, expected {cols}")
        for j, val in enumerate(row):
            if not _is_exact_integer(val):
                errors.append(f"entry ({i},{j}) is not an exact integer")

    if not errors:
        try:
            _to_int_matrix(entries)
        except ValueError as exc:
            errors.append(str(exc))

    return errors


def validate_claim(payload: dict[str, Any]) -> list[str]:
    """Return a list of validation errors for a matrix claim payload."""
    errors: list[str] = []
    predicate = payload.get("predicate")
    if predicate == "is_nonsingular":
        pass
    elif predicate == "maximize_absolute_determinant":
        scope = payload.get("scope")
        if not isinstance(scope, dict):
            errors.append("maximize_absolute_determinant requires a scope")
        else:
            errors.extend(_validate_scope(scope))
            if (
                isinstance(scope.get("rows"), int)
                and isinstance(scope.get("cols"), int)
                and scope["rows"] != scope["cols"]
            ):
                errors.append("determinant scope must be square")
    else:
        errors.append(f"unsupported matrix claim predicate: {predicate}")
    return errors


def _validate_candidate_for_claim(
    claim: dict[str, Any], candidate: dict[str, Any]
) -> list[str]:
    errors = validate_candidate(candidate)
    if (
        not errors
        and claim.get("predicate")
        in {"is_nonsingular", "maximize_absolute_determinant"}
        and candidate.get("rows") != candidate.get("cols")
    ):
        errors.append("determinant predicates require a square matrix")
    if not errors and claim.get("predicate") == "maximize_absolute_determinant":
        scope = claim.get("scope")
        if not isinstance(scope, dict):
            errors.append("maximize_absolute_determinant requires a scope")
        else:
            if candidate.get("rows") != scope.get("rows") or candidate.get(
                "cols"
            ) != scope.get("cols"):
                errors.append("candidate dimensions do not match claim scope")
            else:
                allowed = {_to_int(value) for value in scope["entries"]}
                matrix = _to_int_matrix(candidate["entries"])
                if any(entry not in allowed for row in matrix for entry in row):
                    errors.append("candidate entry is outside claim scope")
    return errors


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _now_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _ok(start: float) -> dict[str, Any]:
    return {
        "execution": {"status": "COMPLETED", "runtime_ms": _now_ms(start)},
        "input": {"status": "ACCEPTED", "errors": [], "warnings": []},
        "verified": False,
    }


def _rejected(errors: list[str], start: float) -> dict[str, Any]:
    return {
        "execution": {"status": "COMPLETED", "runtime_ms": _now_ms(start)},
        "input": {"status": "REJECTED", "errors": errors, "warnings": []},
        "verified": False,
    }


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------


def _claim_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Project a generic ClaimSpec into this plugin's compact domain view."""

    predicate = payload.get("predicate")
    if not isinstance(predicate, dict):
        return payload
    parameters = predicate.get("parameters", {})
    bounds = payload.get("bounds", {})
    return {
        "predicate": predicate.get("name"),
        **(parameters if isinstance(parameters, dict) else {}),
        **(bounds if isinstance(bounds, dict) else {}),
    }


def _matrix_capability_request(request: dict[str, Any]) -> MatrixCapabilityRequest:
    try:
        return MatrixCapabilityRequest.model_validate(request)
    except ValidationError as exc:
        raise ValueError(
            "matrix capability request does not match its contract"
        ) from exc


def _matrix_reduction_request(request: dict[str, Any]) -> MatrixReductionRequest:
    try:
        return MatrixReductionRequest.model_validate(request)
    except ValidationError as exc:
        raise ValueError(
            "matrix reduction request does not match its contract"
        ) from exc


def evaluate(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate integer-matrix candidates for a claim.  Results are unverified."""
    start = time.monotonic()
    try:
        selected = MatrixEvaluationRequest.model_validate(request)
    except ValidationError:
        return _rejected(
            ["matrix evaluation request does not match its contract"], start
        )
    claim = selected.claim.model_dump(mode="json")
    candidate_list = (
        [selected.candidate.model_dump(mode="json")]
        if selected.candidate is not None
        else [
            candidate.model_dump(mode="json") for candidate in selected.candidates or ()
        ]
    )

    claim_errors = validate_claim(claim)
    if claim_errors:
        return _rejected(claim_errors, start)

    predicate = claim.get("predicate")
    results: list[dict[str, Any]] = []

    for idx, candidate in enumerate(candidate_list):
        if candidate is None:
            results.append({"candidate_index": idx, "error": "missing candidate"})
            continue
        cand_errors = _validate_candidate_for_claim(claim, candidate)
        if cand_errors:
            return _rejected(cand_errors, start)

        matrix = _to_int_matrix(candidate["entries"])
        det = _det_fraction(matrix)

        if predicate == "is_nonsingular":
            result: dict[str, Any] = {
                "candidate_index": idx,
                "objective": {
                    "name": "determinant",
                    "value": _canonical_rational(det),
                },
                "is_singular": det == 0,
                "proposed_witness": None,
                "coverage": "EXHAUSTIVE",
                "arithmetic": "EXACT_RATIONAL",
                "detail": "exact rational determinant",
            }
            if det == 0:
                vec = _kernel_vector(matrix)
                if vec is not None:
                    result["proposed_witness"] = {
                        "witness_format": "matrix.kernel_vector",
                        "format_version": "1",
                        "role": "DEFEATS_CANDIDATE",
                        "payload": {"vector": [_canonical_rational(v) for v in vec]},
                    }
                    result["detail"] = (
                        "matrix is singular with a non-zero kernel vector"
                    )
            results.append(result)

        elif predicate == "maximize_absolute_determinant":
            abs_det = abs(det)
            results.append(
                {
                    "candidate_index": idx,
                    "objective": {
                        "name": "abs_determinant",
                        "value": _canonical_rational(abs_det),
                    },
                    "is_singular": det == 0,
                    "proposed_witness": None,
                    "coverage": "EXHAUSTIVE",
                    "arithmetic": "EXACT_RATIONAL",
                    "detail": "exact rational absolute determinant",
                }
            )

    response = _ok(start)
    response["results"] = results
    response["coverage"] = "EXHAUSTIVE"
    response["arithmetic"] = "EXACT_RATIONAL"
    response["detail"] = "matrix search-side evaluation"
    return response


def evaluate_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Return one matrix evaluation in the generic evaluator contract."""

    try:
        selected = MatrixCapabilityRequest.model_validate(request)
    except ValidationError as exc:
        raise ValueError(
            "matrix evaluation request does not match its contract"
        ) from exc
    claim = selected.claim.model_dump(mode="json")
    candidate_model = selected.candidate
    candidate = (
        candidate_model.model_dump(mode="json") if candidate_model is not None else None
    )
    response = evaluate({"claim": claim, "candidate": candidate})
    if response["input"]["status"] != "ACCEPTED":
        raise ValueError("; ".join(response["input"]["errors"]))
    result = response["results"][0]
    if "error" in result:
        raise ValueError(result["error"])
    objective = result["objective"]
    predicate = claim.get("predicate")
    if predicate == "is_nonsingular":
        conclusion = "FALSE" if result["is_singular"] else "TRUE"
        method = "EXHAUSTIVE_FINITE"
        coverage = "EXHAUSTIVE"
    else:
        conclusion = "UNKNOWN"
        method = "BOUNDED_SEARCH"
        coverage = "BOUNDED"
    return {
        "response_version": "1",
        "conclusion": conclusion,
        "arithmetic": result["arithmetic"],
        "method": method,
        "coverage": coverage,
        "objectives": {objective["name"]: objective["value"]},
        "features": (
            {
                "rows": str(candidate_model.rows),
                "cols": str(candidate_model.cols),
            }
            if candidate_model is not None
            else {}
        ),
        "failure_classifications": (
            ["nontrivial_kernel"] if result.get("is_singular") else []
        ),
        "detail": result["detail"],
    }


def find_witness(request: dict[str, Any]) -> dict[str, Any]:
    """Search for a matrix witness.  Result is unverified."""
    start = time.monotonic()
    selected = _matrix_capability_request(request)
    claim = selected.claim.model_dump(mode="json")
    candidate = (
        selected.candidate.model_dump(mode="json")
        if selected.candidate is not None
        else None
    )
    claim_errors = validate_claim(claim)
    if claim_errors:
        return _rejected(claim_errors, start)

    predicate = claim.get("predicate")
    requested_role = selected.witness_role

    if predicate == "is_nonsingular":
        if requested_role != "DEFEATS_CANDIDATE":
            return _rejected(
                ["is_nonsingular supports only DEFEATS_CANDIDATE witnesses"],
                start,
            )
        if candidate is None:
            return _rejected(["is_nonsingular witness requires a candidate"], start)
        cand_errors = _validate_candidate_for_claim(claim, candidate)
        if cand_errors:
            return _rejected(cand_errors, start)
        matrix = _to_int_matrix(candidate["entries"])
        vec = _kernel_vector(matrix)
        if vec is None:
            response = _ok(start)
            response.update(
                {
                    "status": "SEARCH_EXHAUSTED",
                    "witness": None,
                    "coverage": "EXHAUSTIVE",
                    "arithmetic": "EXACT_RATIONAL",
                    "detail": "matrix has trivial kernel only",
                }
            )
            return response
        response = _ok(start)
        response.update(
            {
                "status": "FOUND",
                "witness": {"vector": [_canonical_rational(v) for v in vec]},
                "witness_format": "matrix.kernel_vector",
                "format_version": "1",
                "role": "DEFEATS_CANDIDATE",
                "coverage": "EXHAUSTIVE",
                "arithmetic": "EXACT_RATIONAL",
                "detail": "non-zero kernel vector found",
            }
        )
        return response

    if predicate == "maximize_absolute_determinant":
        if requested_role != "SUPPORTS_CLAIM":
            return _rejected(
                [
                    "maximize_absolute_determinant supports only "
                    "SUPPORTS_CLAIM witnesses"
                ],
                start,
            )
        scope = claim.get("scope")
        if scope is None:
            return _rejected(
                ["maximize_absolute_determinant witness requires a scope"], start
            )
        scope_errors = _validate_scope(scope)
        if scope_errors:
            return _rejected(scope_errors, start)
        if _scope_total(scope) > MAX_SEARCHED_MATRICES:
            return _rejected(
                [
                    "scope exceeds witness search limit of "
                    f"{MAX_SEARCHED_MATRICES} candidates"
                ],
                start,
            )

        best_value = Fraction(-1)
        best_index = -1
        best_matrix: list[list[int]] = []
        for index, mat in _scope_iterator(scope):
            det = abs(_det_fraction(mat))
            if det > best_value:
                best_value = det
                best_index = index
                best_matrix = mat

        if best_index < 0:
            return _rejected(["scope contains no candidates"], start)

        response = _ok(start)
        response.update(
            {
                "status": "FOUND",
                "witness": {
                    "matrix": {
                        "rows": scope["rows"],
                        "cols": scope["cols"],
                        "entries": best_matrix,
                    },
                    "objective_value": _canonical_rational(best_value),
                    "index": best_index,
                },
                "witness_format": "matrix.maximizer",
                "format_version": "1",
                "role": "SUPPORTS_CLAIM",
                "coverage": "EXHAUSTIVE",
                "arithmetic": "EXACT_RATIONAL",
                "detail": f"maximizer with |det| = {best_value}",
            }
        )
        return response

    return _rejected(["unsupported matrix claim predicate for witness search"], start)


def find_witness_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Return matrix witness search in the generic oracle contract."""

    response = find_witness(request)
    if response["input"]["status"] != "ACCEPTED":
        raise ValueError("; ".join(response["input"]["errors"]))
    return {
        key: value
        for key, value in response.items()
        if key
        in {
            "status",
            "witness",
            "witness_format",
            "format_version",
            "role",
            "arithmetic",
            "coverage",
            "detail",
        }
    }


def materialize(request: dict[str, Any]) -> dict[str, Any]:
    """Materialize a complete bounded family for a matrix claim."""
    start = time.monotonic()
    try:
        selected = MatrixMaterializeRequest.model_validate(request)
    except ValidationError:
        return _rejected(
            ["matrix materialization request does not match its contract"], start
        )
    claim = selected.claim.model_dump(mode="json")

    claim_errors = validate_claim(claim)
    if claim_errors:
        return _rejected(claim_errors, start)

    if claim.get("predicate") != "maximize_absolute_determinant":
        return _rejected(
            ["matrix materialize supports maximize_absolute_determinant only"], start
        )

    scope = claim.get("scope")
    if scope is None:
        return _rejected(["missing scope"], start)
    scope_errors = _validate_scope(scope)
    if scope_errors:
        return _rejected(scope_errors, start)
    if _scope_total(scope) > MAX_SEARCHED_MATRICES:
        return _rejected(
            [
                "matrix materialization scope exceeds the bounded search limit "
                f"of {MAX_SEARCHED_MATRICES} candidates"
            ],
            start,
        )

    family: list[dict[str, Any]] = []
    for index, mat in _scope_iterator(scope):
        family.append(
            {
                "index": index,
                "candidate": {
                    "rows": scope["rows"],
                    "cols": scope["cols"],
                    "entries": mat,
                },
            }
        )

    response = _ok(start)
    response["family"] = family
    response["coverage"] = "EXHAUSTIVE"
    response["arithmetic"] = "EXACT_INTEGER"
    response["detail"] = f"all {_scope_total(scope)} labeled matrices in scope"
    return response


def reductions(request: dict[str, Any]) -> dict[str, Any]:
    """Propose candidate reductions that preserve the attacked predicate."""
    start = time.monotonic()
    selected = _matrix_reduction_request(request)
    target_kind = selected.target_kind
    target = selected.target.model_dump(mode="json")
    claim = selected.claim.model_dump(mode="json")

    claim_errors = validate_claim(claim)
    if claim_errors:
        return _rejected(claim_errors, start)

    if target_kind != "candidate":
        response = _ok(start)
        response["reductions"] = []
        response["detail"] = "matrix plugin only supports candidate reduction"
        return response

    cand_errors = _validate_candidate_for_claim(claim, target)
    if cand_errors:
        return _rejected(cand_errors, start)

    predicate = claim.get("predicate")
    matrix = _to_int_matrix(target["entries"])
    n = len(matrix)

    proposed: list[dict[str, Any]] = []

    if predicate == "is_nonsingular" and _is_singular(matrix):
        # Try deleting matching row and column.
        for i in range(n):
            reduced = [
                [matrix[r][c] for c in range(n) if c != i] for r in range(n) if r != i
            ]
            if reduced and _is_singular(reduced):
                vec = _kernel_vector(reduced)
                if vec is not None:
                    proposed.append(
                        {
                            "reduction_kind": "delete_row_column",
                            "index": i,
                            "objectives": {
                                "elements": (n - 1) * (n - 1),
                                "max_abs_entry": max(
                                    abs(x) for row in reduced for x in row
                                ),
                            },
                        }
                    )

        # Try zeroing a single entry.
        for i in range(n):
            for j in range(n):
                reduced = [row[:] for row in matrix]
                reduced[i][j] = 0
                if _is_singular(reduced):
                    vec = _kernel_vector(reduced)
                    if vec is not None:
                        proposed.append(
                            {
                                "reduction_kind": "zero_entry",
                                "row": i,
                                "col": j,
                                "objectives": {
                                    "elements": n * n,
                                    "max_abs_entry": max(
                                        abs(x) for row in reduced for x in row
                                    ),
                                },
                            }
                        )

    # maximize_absolute_determinant has no candidate reductions in v0.2.

    proposed.sort(
        key=lambda r: (r["objectives"]["elements"], r["objectives"]["max_abs_entry"])
    )

    response = _ok(start)
    response["reductions"] = proposed
    response["coverage"] = "BOUNDED"
    response["arithmetic"] = "EXACT_RATIONAL"
    response["detail"] = f"{len(proposed)} reduction(s) preserve singularity"
    return response


def reductions_capability(request: dict[str, Any]) -> dict[str, Any]:
    """Return complete reduced payloads for the generic shrinker."""

    selected = _matrix_reduction_request(request)
    target = selected.target.model_dump(mode="json")
    response = reductions(
        {
            "target_kind": selected.target_kind,
            "target": target,
            "claim": selected.claim.model_dump(mode="json"),
        }
    )
    if response["input"]["status"] != "ACCEPTED":
        raise ValueError("; ".join(response["input"]["errors"]))
    requested = set(selected.reducers)
    objective_names = tuple(selected.objectives)
    proposals: list[dict[str, Any]] = []
    for operation in response["reductions"]:
        reducer = operation["reduction_kind"]
        if requested and reducer not in requested:
            continue
        payload = deepcopy(target)
        matrix = _to_int_matrix(payload["entries"])
        if reducer == "delete_row_column":
            index = operation["index"]
            matrix = [
                [value for column, value in enumerate(row) if column != index]
                for row_index, row in enumerate(matrix)
                if row_index != index
            ]
            payload = {
                "rows": payload["rows"] - 1,
                "cols": payload["cols"] - 1,
                "entries": matrix,
            }
        elif reducer == "zero_entry":
            matrix[operation["row"]][operation["col"]] = 0
            payload["entries"] = matrix
        else:
            continue
        proposals.append(
            {
                "reducer": reducer,
                "payload": payload,
                "objectives": {
                    name: operation["objectives"][name]
                    for name in objective_names
                    if name in operation["objectives"]
                },
            }
        )
    current_matrix = _to_int_matrix(target.get("entries", []))
    current = {
        "elements": target.get("rows", 0) * target.get("cols", 0),
        "max_abs_entry": max(
            (abs(value) for row in current_matrix for value in row),
            default=0,
        ),
    }
    return {
        "response_version": "1",
        "current_objectives": {
            name: current[name] for name in objective_names if name in current
        },
        "reductions": proposals,
        "detail": response["detail"],
    }
