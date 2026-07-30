"""Lean frontend services: declarations, exploration, proof edit, statements."""

from jacobian.lean_frontend.declarations import (
    LeanDeclarationService,
    installed_lean_declaration_service,
)
from jacobian.lean_frontend.exploration import (
    LeanExplorationInstallation,
    install_lean_exploration_capabilities,
)
from jacobian.lean_frontend.proof_edit import (
    LeanProofEditInstallation,
    install_lean_proof_edit_capability,
)
from jacobian.lean_frontend.service import LeanService
from jacobian.lean_frontend.statement import (
    LeanStatementInstallation,
    install_lean_statement_capabilities,
)

__all__ = [
    "LeanDeclarationService",
    "LeanExplorationInstallation",
    "LeanProofEditInstallation",
    "LeanService",
    "LeanStatementInstallation",
    "install_lean_exploration_capabilities",
    "install_lean_proof_edit_capability",
    "install_lean_statement_capabilities",
    "installed_lean_declaration_service",
]
