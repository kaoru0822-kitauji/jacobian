"""Catalog declarations for bounded principal Dirichlet characters."""

from __future__ import annotations

from jacobian.catalog._examples import example
from jacobian.catalog.models import MathTool, MathTools
from jacobian.math.number_theory.characters._models import (
    PrincipalDirichletCharacterRequest,
)
from jacobian.math.number_theory.characters._operations import (
    compute_principal_dirichlet_character,
)
from jacobian.math.number_theory.characters.values import PrincipalDirichletCharacter

TOOLS: MathTools = (
    MathTool(
        operation_id="dirichlet_character.principal.compute",
        title="Compute an exact principal Dirichlet character",
        description=(
            "Materialize the complete extension-by-zero table of the principal "
            "Dirichlet character modulo a bounded positive modulus. The returned "
            "canonical value composes directly with exact character evaluation."
        ),
        request_type=PrincipalDirichletCharacterRequest,
        result_type=PrincipalDirichletCharacter,
        run=compute_principal_dirichlet_character,
        tags=("number-theory", "dirichlet-character", "principal", "exact"),
        examples=(
            example(
                "principal_character_mod_12",
                "Compute the complete principal character modulo 12; the modulus must be positive and its full residue table must fit the 2,048-entry bound.",
                {"modulus": 12},
            ),
        ),
    ),
)

__all__ = ["TOOLS"]
