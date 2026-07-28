"""Hydrate verify adapters from an already-authorized store without reauth."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from jacobian.kernel import JacobianKernel


def _verify_ids(kernel: JacobianKernel) -> set[str]:
    return {
        entry.capability_id
        for entry in kernel.capabilities.catalog().capabilities
        if ".verify" in entry.capability_id
    }


def _audit_count(root: Path) -> int:
    connection = sqlite3.connect(root / "metadata.sqlite3")
    try:
        row = connection.execute("SELECT COUNT(*) FROM checker_audit").fetchone()
    finally:
        connection.close()
    assert row is not None
    return int(row[0])


def test_hydrate_authorized_matches_install_references_without_audit(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    seed = tmp_path_factory.mktemp("hydrate-seed")
    authorized = JacobianKernel(seed, install_references=True)
    expected = _verify_ids(authorized)
    baseline_audit = _audit_count(seed)
    del authorized

    attached = tmp_path_factory.mktemp("hydrate-attach")
    shutil.copytree(seed, attached, dirs_exist_ok=True)
    hydrated = JacobianKernel(attached, hydrate_authorized=True)

    assert _verify_ids(hydrated) == expected
    assert _audit_count(attached) == baseline_audit


def test_hydrate_authorized_on_empty_store_is_fail_closed(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, hydrate_authorized=True)

    assert _audit_count(tmp_path) == 0
    # Atomic / resource verify surfaces may still appear; domain checkers must not.
    assert "polynomial.result.verify" not in _verify_ids(kernel)
    assert "sat.model.verify" not in _verify_ids(kernel)
    assert "matrix.determinant.verify" not in _verify_ids(kernel)


def test_install_references_and_hydrate_are_mutually_exclusive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        JacobianKernel(tmp_path, install_references=True, hydrate_authorized=True)


def test_kernel_with_references_fixture_hydrates(
    kernel_with_references: JacobianKernel,
) -> None:
    ids = _verify_ids(kernel_with_references)
    assert "sat.model.verify" in ids
    assert "polynomial.result.verify" in ids
    assert "matrix.result.verify" in ids
