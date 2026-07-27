from __future__ import annotations

from pathlib import Path

from jacobian.contracts.matrix_operations import (
    IntegerMatrixRequest,
    RationalMatrixRequest,
    SquareRationalMatrixRequest,
)
from jacobian.contracts.polynomial_operations import (
    PolynomialDiscriminantRequest,
    PolynomialGcdRequest,
    PolynomialResultantRequest,
    PolynomialSquareFreeRequest,
)
from jacobian.contracts.results import ContractModel
from jacobian.exact_domain_checkers import install_exact_domain_checkers
from jacobian.operation_installation import InstalledDomainBundle
from jacobian.registry import CheckerRegistry


def _uri(character: str) -> str:
    return "artifact://sha256/" + character * 64


def _installed(
    request_models: tuple[type[ContractModel], ...],
    capability_ids: tuple[str, ...],
    *,
    character: str,
) -> InstalledDomainBundle:
    return InstalledDomainBundle(
        adapters=(),
        semantics_uri=_uri(character),
        input_schema_uris={
            model: _uri(str(index + 1)) for index, model in enumerate(request_models)
        },
        result_schema_uris={
            capability_id: _uri(chr(ord("a") + index))
            for index, capability_id in enumerate(capability_ids)
        },
        obligation_schema_uris={},
    )


def test_installer_authorizes_all_exact_domain_replays(tmp_path: Path) -> None:
    polynomial_ids = (
        "polynomial.compute.gcd",
        "polynomial.compute.resultant",
        "polynomial.compute.discriminant",
        "polynomial.compute.square_free_decomposition",
    )
    matrix_ids = (
        "matrix.normal_form.rref.compute",
        "matrix.nullspace.compute",
        "matrix.characteristic_polynomial.compute",
        "matrix.normal_form.smith.compute",
    )
    registry = CheckerRegistry(tmp_path / "checkers.sqlite3")

    installation = install_exact_domain_checkers(
        registry,
        polynomial=_installed(
            (
                PolynomialGcdRequest,
                PolynomialResultantRequest,
                PolynomialDiscriminantRequest,
                PolynomialSquareFreeRequest,
            ),
            polynomial_ids,
            character="e",
        ),
        matrix=_installed(
            (
                RationalMatrixRequest,
                SquareRationalMatrixRequest,
                IntegerMatrixRequest,
            ),
            matrix_ids,
            character="f",
        ),
        authorize=True,
    )

    assert set(installation.checker_ids) == set(polynomial_ids + matrix_ids)
    assert all(installation.checker_ids.values())
    for checker_id in installation.checker_ids.values():
        assert checker_id is not None
        registration = registry.require_active(checker_id)
        assert registration.entrypoint.startswith(
            "jacobian_checkers.exact_domain_operations:"
        )


def test_installer_preserves_operator_control(tmp_path: Path) -> None:
    registry = CheckerRegistry(tmp_path / "checkers.sqlite3")

    installation = install_exact_domain_checkers(
        registry,
        polynomial=_installed(
            (
                PolynomialGcdRequest,
                PolynomialResultantRequest,
                PolynomialDiscriminantRequest,
                PolynomialSquareFreeRequest,
            ),
            (
                "polynomial.compute.gcd",
                "polynomial.compute.resultant",
                "polynomial.compute.discriminant",
                "polynomial.compute.square_free_decomposition",
            ),
            character="e",
        ),
        matrix=_installed(
            (
                RationalMatrixRequest,
                SquareRationalMatrixRequest,
                IntegerMatrixRequest,
            ),
            (
                "matrix.normal_form.rref.compute",
                "matrix.nullspace.compute",
                "matrix.characteristic_polynomial.compute",
                "matrix.normal_form.smith.compute",
            ),
            character="f",
        ),
        authorize=False,
    )

    assert set(installation.checker_ids.values()) == {None}
