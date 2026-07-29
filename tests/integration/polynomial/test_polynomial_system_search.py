from pathlib import Path

import pytest

from jacobian.contracts.capabilities import CapabilityAssuranceLevel, CapabilityRequest
from jacobian.runtime import CheckerAuthorityMode, create_runtime

pytestmark = pytest.mark.usefixtures("initialized_runtime_store_with_references")


def _request(constant: int) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="polynomial.system.rational_solution.search",
        input={
            "system": {
                "variables": ["x"],
                "equations": [
                    {
                        "terms": [
                            {"coefficient": {"num": "1", "den": "1"}, "exponents": [1]},
                            {
                                "coefficient": {"num": str(constant), "den": "1"},
                                "exponents": [0],
                            },
                        ]
                    }
                ],
            },
            "max_abs_numerator": 1,
            "max_denominator": 1,
        },
    )


def test_rational_solution_search_returns_first_exact_candidate(tmp_path: Path) -> None:
    result = create_runtime(
        tmp_path, checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED
    ).capabilities.invoke(_request(1))
    assert result.output["found"] is True
    assert result.output["assignment"] == [{"num": "-1", "den": "1"}]
    assert result.output["examined_assignment_count"] == 1
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


def test_rational_solution_search_reports_completed_bounded_absence(
    tmp_path: Path,
) -> None:
    result = create_runtime(tmp_path).capabilities.invoke(_request(2))
    assert result.output["found"] is False
    assert result.output["examined_assignment_count"] == 3
    assert result.output["grid_assignment_count"] == 3
    assert result.output["verification"] == "UNVERIFIED"
