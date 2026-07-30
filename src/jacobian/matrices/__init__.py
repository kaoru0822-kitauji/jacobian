"""Matrix, linear algebra, and flint-backed exact operations."""

from jacobian.matrices.capabilities import (
    MatrixInstallation,
    install_matrix_capabilities,
)
from jacobian.matrices.determinant import (
    MatrixDeterminantCheckerInstallation,
    install_matrix_determinant_checker,
)
from jacobian.matrices.linear_capabilities import (
    LinearRationalInconsistencyCheckerInstallation,
    LinearRationalSolutionCheckerInstallation,
    install_linear_rational_inconsistency_checker,
    install_linear_rational_solution_checker,
)
from jacobian.matrices.normal_form import (
    MatrixNormalFormCheckerInstallation,
    install_matrix_normal_form_checker,
)
from jacobian.matrices.rank import (
    MatrixRankCheckerInstallation,
    install_matrix_rank_checker,
)

__all__ = [
    "LinearRationalInconsistencyCheckerInstallation",
    "LinearRationalSolutionCheckerInstallation",
    "MatrixDeterminantCheckerInstallation",
    "MatrixInstallation",
    "MatrixNormalFormCheckerInstallation",
    "MatrixRankCheckerInstallation",
    "install_linear_rational_inconsistency_checker",
    "install_linear_rational_solution_checker",
    "install_matrix_capabilities",
    "install_matrix_determinant_checker",
    "install_matrix_normal_form_checker",
    "install_matrix_rank_checker",
]
